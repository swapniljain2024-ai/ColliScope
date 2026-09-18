#include "svc_hash/svc_hash_table.hpp"
#include <algorithm>
#include <iostream>

namespace colliscope {

uint64_t SvcHashTable::computeHash(const std::string& key, uint32_t scope_id, uint64_t offset_basis) {
    constexpr uint64_t FNV_PRIME = 1099511628211ULL;
    uint64_t hash = offset_basis;

    for (unsigned char c : key) {
        hash ^= static_cast<uint64_t>(c);
        hash *= FNV_PRIME;
    }

    for (int i = 0; i < 4; i++) {
        hash ^= static_cast<uint64_t>((scope_id >> (i * 8)) & 0xFF);
        hash *= FNV_PRIME;
    }

    return hash;
}

SvcHashTable::SvcHashTable(size_t initial_buckets)
    : num_buckets_(std::max<size_t>(4, initial_buckets)),
      buckets_(num_buckets_) {
    reset();
}

void SvcHashTable::reset() {
    num_buckets_ = std::max<size_t>(4, num_buckets_);
    buckets_ = std::vector<Bucket>(num_buckets_);
    for (size_t i = 0; i < STASH_SIZE; ++i) {
        stash_[i] = BucketEntry{};
    }

    occupied_count_ = 0;
    tombstone_count_ = 0;
    stash_count_ = 0;

    scope_registry_.clear();
    scope_stack_.clear();
    scope_entries_.clear();

    // Register root scope (scope 0)
    scope_registry_[0] = ScopeInfo{0, 0, true};
    scope_stack_.push_back(0);
    current_scope_id_ = 0;

    insertion_time_ns_ = 0;
    lookup_time_ns_ = 0;
    scope_exit_time_ns_ = 0;
    total_operations_ = 0;
    successful_lookups_ = 0;
    failed_lookups_ = 0;
    collision_count_ = 0;
    kick_count_ = 0;
    rebuild_count_ = 0;
}

bool SvcHashTable::isScopeActive(uint32_t scope_id) const {
    auto it = scope_registry_.find(scope_id);
    if (it == scope_registry_.end()) {
        return false;
    }
    return it->second.active;
}

void SvcHashTable::computeCandidateBuckets(const std::string& key, uint32_t scope_id, size_t& b1, size_t& b2) const {
    b1 = computeHash(key, scope_id, HASH_SEED_1) % num_buckets_;
    b2 = computeHash(key, scope_id, HASH_SEED_2) % num_buckets_;
    if (b2 == b1) {
        b2 = (b1 + 1) % num_buckets_;
    }
}

void SvcHashTable::enterScope(uint32_t scope_id, uint32_t parent_scope_id) {
    // If scope 0 is being initialized and registry is uninitialized
    if (scope_registry_.empty()) {
        scope_registry_[0] = ScopeInfo{0, 0, true};
        scope_stack_.push_back(0);
        current_scope_id_ = 0;
    }

    if (scope_id == 0 && parent_scope_id == 0 && scope_registry_.count(0) && scope_registry_[0].active) {
        // Root scope already active
        return;
    }

    // Scope Entry Contract Validation (v2.2.0):
    // 1. parent_scope_id MUST be active
    // 2. parent_scope_id MUST equal current_scope_id_
    // 3. scope_id MUST NOT already exist as active
    auto parent_it = scope_registry_.find(parent_scope_id);
    if (parent_it == scope_registry_.end() || !parent_it->second.active) {
        throw std::invalid_argument("SvcHashTable::enterScope rejected: parent scope " +
                                   std::to_string(parent_scope_id) + " is not active.");
    }

    if (parent_scope_id != current_scope_id_) {
        throw std::invalid_argument("SvcHashTable::enterScope rejected: parent scope " +
                                   std::to_string(parent_scope_id) + " is not current scope " +
                                   std::to_string(current_scope_id_));
    }

    auto existing_it = scope_registry_.find(scope_id);
    if (existing_it != scope_registry_.end() && existing_it->second.active) {
        throw std::invalid_argument("SvcHashTable::enterScope rejected: scope " +
                                   std::to_string(scope_id) + " is already active.");
    }

    scope_registry_[scope_id] = ScopeInfo{scope_id, parent_scope_id, true};
    scope_stack_.push_back(scope_id);
    current_scope_id_ = scope_id;
    scope_entries_[scope_id].clear();
}

void SvcHashTable::exitScope(uint32_t scope_id) {
    auto start_time = std::chrono::high_resolution_clock::now();
    total_operations_++;

    // Scope Exit Contract Validation (v2.2.0):
    // 1. scope_id MUST equal current_scope_id_
    // 2. scope_id MUST be active
    if (scope_id != current_scope_id_) {
        throw std::invalid_argument("SvcHashTable::exitScope rejected: scope " +
                                   std::to_string(scope_id) + " is not current scope " +
                                   std::to_string(current_scope_id_));
    }

    auto it = scope_registry_.find(scope_id);
    if (it == scope_registry_.end() || !it->second.active) {
        throw std::invalid_argument("SvcHashTable::exitScope rejected: scope " +
                                   std::to_string(scope_id) + " is not active.");
    }

    // Mark scope inactive
    it->second.active = false;

    // Tombstone all declarations recorded in this scope
    auto entry_log_it = scope_entries_.find(scope_id);
    if (entry_log_it != scope_entries_.end()) {
        for (const auto& key : entry_log_it->second) {
            size_t b1, b2;
            computeCandidateBuckets(key, scope_id, b1, b2);

            bool found_and_tombstoned = false;

            // Check bucket b1
            for (size_t s = 0; s < Bucket::BUCKET_SIZE; ++s) {
                auto& slot = buckets_[b1].entries[s];
                if (slot.occupied && !slot.tombstoned && slot.key == key && slot.scope_id == scope_id) {
                    slot.tombstoned = true;
                    tombstone_count_++;
                    found_and_tombstoned = true;
                    break;
                }
            }

            // Check bucket b2
            if (!found_and_tombstoned) {
                for (size_t s = 0; s < Bucket::BUCKET_SIZE; ++s) {
                    auto& slot = buckets_[b2].entries[s];
                    if (slot.occupied && !slot.tombstoned && slot.key == key && slot.scope_id == scope_id) {
                        slot.tombstoned = true;
                        tombstone_count_++;
                        found_and_tombstoned = true;
                        break;
                    }
                }
            }

            // Check stash
            if (!found_and_tombstoned) {
                for (size_t i = 0; i < STASH_SIZE; ++i) {
                    auto& slot = stash_[i];
                    if (slot.occupied && !slot.tombstoned && slot.key == key && slot.scope_id == scope_id) {
                        slot.tombstoned = true;
                        tombstone_count_++;
                        found_and_tombstoned = true;
                        break;
                    }
                }
            }
        }
        scope_entries_.erase(entry_log_it);
    }

    // Pop scope stack
    if (!scope_stack_.empty() && scope_stack_.back() == scope_id) {
        scope_stack_.pop_back();
    }
    current_scope_id_ = scope_stack_.empty() ? 0 : scope_stack_.back();

    auto end_time = std::chrono::high_resolution_clock::now();
    scope_exit_time_ns_ += std::chrono::duration_cast<std::chrono::nanoseconds>(end_time - start_time).count();

    checkAndRebuildIfNeeded();
}

std::optional<SymbolValue> SvcHashTable::lookup(const std::string& key, uint32_t scope_id) {
    auto start_time = std::chrono::high_resolution_clock::now();
    total_operations_++;

    uint32_t curr_scope = scope_id;
    bool visited_root = false;

    while (!visited_root) {
        auto reg_it = scope_registry_.find(curr_scope);
        if (reg_it == scope_registry_.end() || !reg_it->second.active) {
            // Scope not active or invalid
            break;
        }

        size_t b1, b2;
        computeCandidateBuckets(key, curr_scope, b1, b2);

        // 1. Probe candidate bucket 1
        for (size_t s = 0; s < Bucket::BUCKET_SIZE; ++s) {
            const auto& slot = buckets_[b1].entries[s];
            if (slot.occupied && !slot.tombstoned && slot.key == key && slot.scope_id == curr_scope) {
                auto end_time = std::chrono::high_resolution_clock::now();
                lookup_time_ns_ += std::chrono::duration_cast<std::chrono::nanoseconds>(end_time - start_time).count();
                successful_lookups_++;
                return slot.value;
            }
        }

        // 2. Probe candidate bucket 2
        for (size_t s = 0; s < Bucket::BUCKET_SIZE; ++s) {
            const auto& slot = buckets_[b2].entries[s];
            if (slot.occupied && !slot.tombstoned && slot.key == key && slot.scope_id == curr_scope) {
                auto end_time = std::chrono::high_resolution_clock::now();
                lookup_time_ns_ += std::chrono::duration_cast<std::chrono::nanoseconds>(end_time - start_time).count();
                successful_lookups_++;
                return slot.value;
            }
        }

        // 3. Probe stash for exact (key, curr_scope) match
        for (size_t i = 0; i < STASH_SIZE; ++i) {
            const auto& slot = stash_[i];
            if (slot.occupied && !slot.tombstoned && slot.key == key && slot.scope_id == curr_scope) {
                auto end_time = std::chrono::high_resolution_clock::now();
                lookup_time_ns_ += std::chrono::duration_cast<std::chrono::nanoseconds>(end_time - start_time).count();
                successful_lookups_++;
                return slot.value;
            }
        }

        // 4. Advance to parent scope
        if (curr_scope == 0 || reg_it->second.parent_id == curr_scope) {
            visited_root = true;
        } else {
            curr_scope = reg_it->second.parent_id;
        }
    }

    auto end_time = std::chrono::high_resolution_clock::now();
    lookup_time_ns_ += std::chrono::duration_cast<std::chrono::nanoseconds>(end_time - start_time).count();
    failed_lookups_++;
    return std::nullopt;
}

bool SvcHashTable::insert(const std::string& key, const SymbolValue& value, uint32_t scope_id) {
    auto start_time = std::chrono::high_resolution_clock::now();
    total_operations_++;

    auto reg_it = scope_registry_.find(scope_id);
    if (reg_it == scope_registry_.end() || !reg_it->second.active) {
        auto end_time = std::chrono::high_resolution_clock::now();
        insertion_time_ns_ += std::chrono::duration_cast<std::chrono::nanoseconds>(end_time - start_time).count();
        return false;
    }

    // Duplicate Declaration Contract Validation (v2.2.0):
    // Check if an active entry for (key, scope_id) already exists in buckets or stash.
    size_t b1, b2;
    computeCandidateBuckets(key, scope_id, b1, b2);

    for (size_t s = 0; s < Bucket::BUCKET_SIZE; ++s) {
        const auto& slot = buckets_[b1].entries[s];
        if (slot.occupied && !slot.tombstoned && slot.key == key && slot.scope_id == scope_id) {
            auto end_time = std::chrono::high_resolution_clock::now();
            insertion_time_ns_ += std::chrono::duration_cast<std::chrono::nanoseconds>(end_time - start_time).count();
            return false; // Duplicate prohibited
        }
    }

    for (size_t s = 0; s < Bucket::BUCKET_SIZE; ++s) {
        const auto& slot = buckets_[b2].entries[s];
        if (slot.occupied && !slot.tombstoned && slot.key == key && slot.scope_id == scope_id) {
            auto end_time = std::chrono::high_resolution_clock::now();
            insertion_time_ns_ += std::chrono::duration_cast<std::chrono::nanoseconds>(end_time - start_time).count();
            return false; // Duplicate prohibited
        }
    }

    for (size_t i = 0; i < STASH_SIZE; ++i) {
        const auto& slot = stash_[i];
        if (slot.occupied && !slot.tombstoned && slot.key == key && slot.scope_id == scope_id) {
            auto end_time = std::chrono::high_resolution_clock::now();
            insertion_time_ns_ += std::chrono::duration_cast<std::chrono::nanoseconds>(end_time - start_time).count();
            return false; // Duplicate prohibited
        }
    }

    // Check if a tombstoned entry for (key, scope_id) exists to overwrite
    bool tombstone_reused = false;
    for (size_t s = 0; s < Bucket::BUCKET_SIZE; ++s) {
        auto& slot = buckets_[b1].entries[s];
        if (slot.occupied && slot.tombstoned && slot.key == key && slot.scope_id == scope_id) {
            slot.value = value;
            slot.tombstoned = false;
            tombstone_count_--;
            tombstone_reused = true;
            break;
        }
    }

    if (!tombstone_reused) {
        for (size_t s = 0; s < Bucket::BUCKET_SIZE; ++s) {
            auto& slot = buckets_[b2].entries[s];
            if (slot.occupied && slot.tombstoned && slot.key == key && slot.scope_id == scope_id) {
                slot.value = value;
                slot.tombstoned = false;
                tombstone_count_--;
                tombstone_reused = true;
                break;
            }
        }
    }

    if (!tombstone_reused) {
        for (size_t i = 0; i < STASH_SIZE; ++i) {
            auto& slot = stash_[i];
            if (slot.occupied && slot.tombstoned && slot.key == key && slot.scope_id == scope_id) {
                slot.value = value;
                slot.tombstoned = false;
                tombstone_count_--;
                tombstone_reused = true;
                break;
            }
        }
    }

    if (!tombstone_reused) {
        bool inserted = insertInternal(key, value, scope_id);
        if (!inserted) {
            auto end_time = std::chrono::high_resolution_clock::now();
            insertion_time_ns_ += std::chrono::duration_cast<std::chrono::nanoseconds>(end_time - start_time).count();
            return false;
        }
    }

    scope_entries_[scope_id].push_back(key);

    auto end_time = std::chrono::high_resolution_clock::now();
    insertion_time_ns_ += std::chrono::duration_cast<std::chrono::nanoseconds>(end_time - start_time).count();

    checkAndRebuildIfNeeded();
    return true;
}

bool SvcHashTable::insertInternal(const std::string& key, const SymbolValue& value, uint32_t scope_id) {
    size_t b1, b2;
    computeCandidateBuckets(key, scope_id, b1, b2);

    // 1. Look for a vacant slot in bucket b1
    for (size_t s = 0; s < Bucket::BUCKET_SIZE; ++s) {
        auto& slot = buckets_[b1].entries[s];
        if (!slot.occupied) {
            slot = BucketEntry{key, value, scope_id, true, false};
            occupied_count_++;
            return true;
        }
    }

    // 2. Look for a vacant slot in bucket b2
    for (size_t s = 0; s < Bucket::BUCKET_SIZE; ++s) {
        auto& slot = buckets_[b2].entries[s];
        if (!slot.occupied) {
            slot = BucketEntry{key, value, scope_id, true, false};
            occupied_count_++;
            return true;
        }
    }

    // 3. Look for a tombstoned slot in bucket b1 or b2
    for (size_t s = 0; s < Bucket::BUCKET_SIZE; ++s) {
        auto& slot = buckets_[b1].entries[s];
        if (slot.tombstoned) {
            slot = BucketEntry{key, value, scope_id, true, false};
            tombstone_count_--;
            return true;
        }
    }

    for (size_t s = 0; s < Bucket::BUCKET_SIZE; ++s) {
        auto& slot = buckets_[b2].entries[s];
        if (slot.tombstoned) {
            slot = BucketEntry{key, value, scope_id, true, false};
            tombstone_count_--;
            return true;
        }
    }

    // 4. Initiate cuckoo kick chain
    BucketEntry curr_entry{key, value, scope_id, true, false};
    size_t curr_bucket = b1;

    for (size_t depth = 0; depth < MAX_KICK_DEPTH; ++depth) {
        kick_count_++;

        size_t victim_slot_idx = depth % Bucket::BUCKET_SIZE;
        BucketEntry victim = buckets_[curr_bucket].entries[victim_slot_idx];
        buckets_[curr_bucket].entries[victim_slot_idx] = curr_entry;

        size_t vb1, vb2;
        computeCandidateBuckets(victim.key, victim.scope_id, vb1, vb2);
        size_t alt_bucket = (curr_bucket == vb1) ? vb2 : vb1;

        // Try to place victim into alt_bucket
        for (size_t s = 0; s < Bucket::BUCKET_SIZE; ++s) {
            auto& slot = buckets_[alt_bucket].entries[s];
            if (!slot.occupied) {
                slot = victim;
                occupied_count_++;
                return true;
            }
            if (slot.tombstoned) {
                slot = victim;
                tombstone_count_--;
                return true;
            }
        }

        // Continue kicking
        curr_entry = victim;
        curr_bucket = alt_bucket;
    }

    // 5. Kick chain limit reached: place into stash
    for (size_t i = 0; i < STASH_SIZE; ++i) {
        if (!stash_[i].occupied) {
            stash_[i] = curr_entry;
            stash_count_++;
            occupied_count_++;
            return true;
        }
        if (stash_[i].tombstoned) {
            stash_[i] = curr_entry;
            tombstone_count_--;
            return true;
        }
    }

    // Stash is completely full: trigger table growth rebuild and re-insert
    rebuild(num_buckets_ * 2);
    return insertInternal(curr_entry.key, curr_entry.value, curr_entry.scope_id);
}

void SvcHashTable::rebuild(size_t new_num_buckets) {
    rebuild_count_++;

    // Collect all active, non-tombstoned entries
    std::vector<BucketEntry> active_entries;
    for (size_t b = 0; b < num_buckets_; ++b) {
        for (size_t s = 0; s < Bucket::BUCKET_SIZE; ++s) {
            const auto& slot = buckets_[b].entries[s];
            if (slot.occupied && !slot.tombstoned) {
                active_entries.push_back(slot);
            }
        }
    }

    for (size_t i = 0; i < STASH_SIZE; ++i) {
        if (stash_[i].occupied && !stash_[i].tombstoned) {
            active_entries.push_back(stash_[i]);
        }
    }

    num_buckets_ = std::max<size_t>(4, new_num_buckets);
    buckets_ = std::vector<Bucket>(num_buckets_);

    for (size_t i = 0; i < STASH_SIZE; ++i) {
        stash_[i] = BucketEntry{};
    }

    occupied_count_ = 0;
    tombstone_count_ = 0;
    stash_count_ = 0;

    for (const auto& entry : active_entries) {
        insertInternal(entry.key, entry.value, entry.scope_id);
    }
}

void SvcHashTable::checkAndRebuildIfNeeded() {
    size_t total_slots = num_buckets_ * Bucket::BUCKET_SIZE + STASH_SIZE;
    double load_factor = static_cast<double>(occupied_count_ - tombstone_count_) / total_slots;
    double tombstone_ratio = static_cast<double>(tombstone_count_) / total_slots;

    if (stash_count_ >= STASH_SIZE || load_factor > 0.90) {
        rebuild(num_buckets_ * 2);
    } else if (tombstone_ratio > 0.25) {
        rebuild(num_buckets_); // Compaction rebuild
    }
}

TableMetrics SvcHashTable::getMetrics() const {
    TableMetrics m;
    m.algorithm_name = getAlgorithmName();
    m.num_elements = occupied_count_ - tombstone_count_;
    size_t total_capacity = num_buckets_ * Bucket::BUCKET_SIZE + STASH_SIZE;
    m.capacity = total_capacity;
    m.load_factor = total_capacity > 0 ? static_cast<double>(m.num_elements) / total_capacity : 0.0;
    m.insertion_time_ns = insertion_time_ns_;
    m.lookup_time_ns = lookup_time_ns_;
    m.scope_exit_time_ns = scope_exit_time_ns_;
    m.total_operations = total_operations_;

    uint64_t total_time = insertion_time_ns_ + lookup_time_ns_ + scope_exit_time_ns_;
    if (total_time > 0) {
        m.throughput_ops_sec = (static_cast<double>(total_operations_) / total_time) * 1e9;
    }

    m.memory_usage_bytes = sizeof(SvcHashTable) +
                           num_buckets_ * sizeof(Bucket) +
                           scope_registry_.size() * sizeof(ScopeInfo) +
                           scope_stack_.capacity() * sizeof(uint32_t);
    m.collision_count = kick_count_;
    m.successful_lookups = successful_lookups_;
    m.failed_lookups = failed_lookups_;

    m.custom_metrics["svc_kicks"] = static_cast<double>(kick_count_);
    m.custom_metrics["svc_rebuilds"] = static_cast<double>(rebuild_count_);
    m.custom_metrics["svc_stash_count"] = static_cast<double>(stash_count_);
    m.custom_metrics["svc_tombstones"] = static_cast<double>(tombstone_count_);
    m.custom_metrics["svc_bucket_count"] = static_cast<double>(num_buckets_);

    return m;
}

} // namespace colliscope
