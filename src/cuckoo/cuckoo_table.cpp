#include "cuckoo_table.hpp"
#include <stdexcept>

namespace colliscope {

uint64_t CuckooHashTable::computeHash(const std::string& key, uint64_t seed) {
    constexpr uint64_t FNV_PRIME = 1099511628211ULL;
    uint64_t hash = seed;
    for (unsigned char c : key) {
        hash ^= static_cast<uint64_t>(c);
        hash *= FNV_PRIME;
    }
    return hash;
}

CuckooHashTable::CuckooHashTable(size_t initial_capacity)
    : capacity_(std::max<size_t>(4, initial_capacity)),
      slots_(capacity_) {
    reset();
}

void CuckooHashTable::reset() {
    capacity_ = std::max<size_t>(4, capacity_);
    slots_ = std::vector<CuckooSlot>(capacity_);
    num_elements_ = 0;
    hash_seed_1_ = DEFAULT_HASH_SEED_1;
    hash_seed_2_ = DEFAULT_HASH_SEED_2;

    insertion_time_ns_ = 0;
    lookup_time_ns_ = 0;
    scope_exit_time_ns_ = 0;
    total_operations_ = 0;
    successful_lookups_ = 0;
    failed_lookups_ = 0;
    collision_count_ = 0;
    relocations_kicks_ = 0;
    rehash_count_ = 0;
    max_displacement_ = 0;
}

void CuckooHashTable::computeCandidatePositions(const std::string& key, size_t& pos1, size_t& pos2) const {
    pos1 = computeHash(key, hash_seed_1_) % capacity_;
    pos2 = computeHash(key, hash_seed_2_) % capacity_;
    if (pos2 == pos1) {
        pos2 = (pos1 + 1) % capacity_;
    }
}

void CuckooHashTable::rehash(size_t new_capacity, const CuckooSlot* extra_slot) {
    rehash_count_++;
    size_t target_capacity = std::max<size_t>(capacity_ * 2, new_capacity);

    for (size_t attempt = 0; attempt < MAX_RETRY_LIMIT; ++attempt) {
        std::vector<CuckooSlot> items_to_rehash;
        items_to_rehash.reserve(num_elements_ + 1);

        for (const auto& slot : slots_) {
            if (slot.occupied) {
                items_to_rehash.push_back(slot);
            }
        }
        if (extra_slot && extra_slot->occupied) {
            items_to_rehash.push_back(*extra_slot);
        }

        capacity_ = target_capacity;
        slots_ = std::vector<CuckooSlot>(capacity_);
        num_elements_ = 0;

        // Update seeds deterministically on rehash
        hash_seed_1_ = hash_seed_1_ * 0x9e3779b97f4a7c15ULL + 1;
        hash_seed_2_ = hash_seed_2_ * 0x9e3779b97f4a7c15ULL + 13;

        bool rehash_success = true;
        for (const auto& item : items_to_rehash) {
            if (!insertInternal(item.key, item.value, item.scope_id, nullptr)) {
                rehash_success = false;
                break;
            }
        }

        if (rehash_success) {
            return;
        }

        target_capacity *= 2;
    }

    throw std::runtime_error("CuckooHashTable::rehash failed: exceeded maximum retry limit (" +
                             std::to_string(MAX_RETRY_LIMIT) + ")");
}

bool CuckooHashTable::insertInternal(const std::string& key, const SymbolValue& value, uint32_t scope_id, CuckooSlot* evicted_out) {
    size_t pos1, pos2;
    computeCandidatePositions(key, pos1, pos2);

    // If key exists, update value
    if (slots_[pos1].occupied && slots_[pos1].key == key) {
        slots_[pos1].value = value;
        slots_[pos1].scope_id = scope_id;
        return true;
    }
    if (slots_[pos2].occupied && slots_[pos2].key == key) {
        slots_[pos2].value = value;
        slots_[pos2].scope_id = scope_id;
        return true;
    }

    // Try placing directly in empty candidate slot
    if (!slots_[pos1].occupied) {
        slots_[pos1] = CuckooSlot{key, value, scope_id, true};
        num_elements_++;
        return true;
    }
    if (!slots_[pos2].occupied) {
        slots_[pos2] = CuckooSlot{key, value, scope_id, true};
        num_elements_++;
        return true;
    }

    // Both positions occupied -> displacement/eviction chain
    collision_count_++;
    CuckooSlot curr{key, value, scope_id, true};
    size_t curr_pos = pos1;

    for (size_t kick = 0; kick < MAX_KICK_DEPTH; ++kick) {
        relocations_kicks_++;
        max_displacement_ = std::max(max_displacement_, static_cast<uint64_t>(kick + 1));

        std::swap(curr, slots_[curr_pos]);

        // Find alternate location for evicted slot
        size_t alt1, alt2;
        computeCandidatePositions(curr.key, alt1, alt2);
        size_t next_pos = (curr_pos == alt1) ? alt2 : alt1;

        if (!slots_[next_pos].occupied) {
            slots_[next_pos] = curr;
            num_elements_++;
            return true;
        }

        curr_pos = next_pos;
    }

    // Exceeded MAX_KICK_DEPTH -> cycle detected -> return evicted entry to caller for rehash recovery
    if (evicted_out) {
        *evicted_out = curr;
    }
    return false;
}

bool CuckooHashTable::insert(const std::string& key, const SymbolValue& value, uint32_t scope_id) {
    auto start = std::chrono::high_resolution_clock::now();
    total_operations_++;

    CuckooSlot evicted;
    if (!insertInternal(key, value, scope_id, &evicted)) {
        // Kick limit reached -> rebuild with increased capacity, updated seeds, and the unplaced evicted entry
        rehash(capacity_ * 2, &evicted);
    }

    auto end = std::chrono::high_resolution_clock::now();
    insertion_time_ns_ += std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
    return true;
}

std::optional<SymbolValue> CuckooHashTable::lookup(const std::string& key, uint32_t /*scope_id*/) {
    auto start = std::chrono::high_resolution_clock::now();
    total_operations_++;

    size_t pos1, pos2;
    computeCandidatePositions(key, pos1, pos2);

    if (slots_[pos1].occupied && slots_[pos1].key == key) {
        successful_lookups_++;
        auto end = std::chrono::high_resolution_clock::now();
        lookup_time_ns_ += std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
        return slots_[pos1].value;
    }

    if (slots_[pos2].occupied && slots_[pos2].key == key) {
        successful_lookups_++;
        auto end = std::chrono::high_resolution_clock::now();
        lookup_time_ns_ += std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
        return slots_[pos2].value;
    }

    failed_lookups_++;
    auto end = std::chrono::high_resolution_clock::now();
    lookup_time_ns_ += std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
    return std::nullopt;
}

void CuckooHashTable::enterScope(uint32_t /*scope_id*/, uint32_t /*parent_scope_id*/) {
    // Zero-cost inline no-op for non-scope-aware baseline
}

void CuckooHashTable::exitScope(uint32_t /*scope_id*/) {
    // Zero-cost inline no-op for non-scope-aware baseline
}

TableMetrics CuckooHashTable::getMetrics() const {
    TableMetrics m;
    m.algorithm_name = getAlgorithmName();
    m.num_elements = num_elements_;
    m.capacity = capacity_;
    m.load_factor = (capacity_ > 0) ? (static_cast<double>(num_elements_) / static_cast<double>(capacity_)) : 0.0;
    m.insertion_time_ns = insertion_time_ns_;
    m.lookup_time_ns = lookup_time_ns_;
    m.scope_exit_time_ns = scope_exit_time_ns_;
    m.total_operations = total_operations_;

    uint64_t total_time_ns = insertion_time_ns_ + lookup_time_ns_ + scope_exit_time_ns_;
    if (total_time_ns > 0) {
        m.throughput_ops_sec = (static_cast<double>(total_operations_) / static_cast<double>(total_time_ns)) * 1e9;
    } else {
        m.throughput_ops_sec = 0.0;
    }

    m.memory_usage_bytes = sizeof(*this) + slots_.capacity() * sizeof(CuckooSlot);
    m.collision_count = collision_count_;
    m.successful_lookups = successful_lookups_;
    m.failed_lookups = failed_lookups_;

    // Metric schema alignment matching manual requirements exactly:
    m.custom_metrics["relocations_kicks"] = static_cast<double>(relocations_kicks_);
    m.custom_metrics["rehashes"] = static_cast<double>(rehash_count_);
    m.custom_metrics["max_displacement"] = static_cast<double>(max_displacement_);

    return m;
}

} // namespace colliscope
