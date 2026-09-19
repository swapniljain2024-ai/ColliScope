#include "hopscotch_table.hpp"
#include <stdexcept>

namespace colliscope {

uint64_t HopscotchHashTable::computeHash(const std::string& key) {
    uint64_t hash = FNV_OFFSET_BASIS;
    for (unsigned char c : key) {
        hash ^= static_cast<uint64_t>(c);
        hash *= FNV_PRIME;
    }
    return hash;
}

HopscotchHashTable::HopscotchHashTable(size_t initial_capacity)
    : capacity_(std::max<size_t>(HOPSCOTCH_H, initial_capacity)),
      slots_(capacity_) {
    reset();
}

void HopscotchHashTable::reset() {
    capacity_ = std::max<size_t>(HOPSCOTCH_H, capacity_);
    slots_ = std::vector<HopscotchSlot>(capacity_);
    num_elements_ = 0;

    insertion_time_ns_ = 0;
    lookup_time_ns_ = 0;
    scope_exit_time_ns_ = 0;
    total_operations_ = 0;
    successful_lookups_ = 0;
    failed_lookups_ = 0;
    collision_count_ = 0;
    neighbourhood_movements_ = 0;
    key_comparisons_ = 0;
    rehash_count_ = 0;
}

void HopscotchHashTable::rehash(size_t new_capacity) {
    rehash_count_++;
    size_t target_capacity = std::max<size_t>(capacity_ * 2, new_capacity);

    for (size_t attempt = 0; attempt < MAX_RETRY_LIMIT; ++attempt) {
        std::vector<HopscotchSlot> old_slots = slots_;
        capacity_ = target_capacity;
        slots_ = std::vector<HopscotchSlot>(capacity_);
        num_elements_ = 0;

        bool rehash_success = true;
        for (const auto& slot : old_slots) {
            if (slot.occupied) {
                if (!insertInternal(slot.key, slot.value, slot.scope_id)) {
                    rehash_success = false;
                    break;
                }
            }
        }

        if (rehash_success) {
            return;
        }

        target_capacity *= 2;
    }

    throw std::runtime_error("HopscotchHashTable::rehash failed: exceeded maximum retry limit (" +
                             std::to_string(MAX_RETRY_LIMIT) + ")");
}

bool HopscotchHashTable::insertInternal(const std::string& key, const SymbolValue& value, uint32_t scope_id) {
    size_t home = computeHash(key) % capacity_;

    // Check if key already exists within home bucket's neighborhood
    uint32_t mask = slots_[home].hop_info;
    for (uint32_t i = 0; i < HOPSCOTCH_H; ++i) {
        if (mask & (1U << i)) {
            size_t idx = (home + i) % capacity_;
            key_comparisons_++;
            if (slots_[idx].occupied && slots_[idx].key == key) {
                slots_[idx].value = value;
                slots_[idx].scope_id = scope_id;
                return true;
            }
        }
    }

    // Hopscotch array scan for nearest empty slot
    size_t free_idx = capacity_;
    for (size_t delta = 0; delta < capacity_; ++delta) {
        size_t idx = (home + delta) % capacity_;
        if (!slots_[idx].occupied) {
            free_idx = idx;
            break;
        }
    }

    if (free_idx == capacity_) {
        // Table is full
        return false;
    }

    if (home != free_idx) {
        collision_count_++;
    }

    // Move empty slot closer to home bucket until distance < HOPSCOTCH_H
    while (true) {
        size_t dist = (free_idx >= home) ? (free_idx - home) : (free_idx + capacity_ - home);
        if (dist < HOPSCOTCH_H) {
            // Empty slot is within neighborhood range of home bucket
            slots_[free_idx] = HopscotchSlot{key, value, scope_id, true, 0};
            slots_[home].hop_info |= (1U << dist);
            num_elements_++;
            return true;
        }

        // Search backward from free_idx to find a slot 'y' that can be shifted to free_idx
        bool candidate_found = false;

        for (uint32_t i = HOPSCOTCH_H - 1; i > 0; --i) {
            size_t y = (free_idx >= i) ? (free_idx - i) : (free_idx + capacity_ - i);
            if (!slots_[y].occupied) {
                continue;
            }

            size_t y_home = computeHash(slots_[y].key) % capacity_;
            size_t y_dist_to_free = (free_idx >= y_home) ? (free_idx - y_home) : (free_idx + capacity_ - y_home);

            if (y_dist_to_free < HOPSCOTCH_H) {
                // Found entry y that can be moved to free_idx
                size_t old_y_dist = (y >= y_home) ? (y - y_home) : (y + capacity_ - y_home);

                // Update y_home's neighborhood mask
                slots_[y_home].hop_info &= ~(1U << old_y_dist);
                slots_[y_home].hop_info |= (1U << y_dist_to_free);

                // Perform neighborhood movement shift
                slots_[free_idx] = slots_[y];
                slots_[y] = HopscotchSlot{};

                neighbourhood_movements_++;
                free_idx = y;
                candidate_found = true;
                break;
            }
        }

        if (!candidate_found) {
            // Cannot shift empty slot into neighborhood -> insertion requires rehash
            return false;
        }
    }
}

bool HopscotchHashTable::insert(const std::string& key, const SymbolValue& value, uint32_t scope_id) {
    auto start = std::chrono::high_resolution_clock::now();
    total_operations_++;

    if (!insertInternal(key, value, scope_id)) {
        rehash(capacity_ * 2);
        bool retry_success = insertInternal(key, value, scope_id);
        if (!retry_success) {
            rehash(capacity_ * 2);
            insertInternal(key, value, scope_id);
        }
    }

    auto end = std::chrono::high_resolution_clock::now();
    insertion_time_ns_ += std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
    return true;
}

std::optional<SymbolValue> HopscotchHashTable::lookup(const std::string& key, uint32_t /*scope_id*/) {
    auto start = std::chrono::high_resolution_clock::now();
    total_operations_++;

    size_t home = computeHash(key) % capacity_;
    uint32_t mask = slots_[home].hop_info;

    for (uint32_t i = 0; i < HOPSCOTCH_H; ++i) {
        if (mask & (1U << i)) {
            size_t idx = (home + i) % capacity_;
            key_comparisons_++;
            if (slots_[idx].occupied && slots_[idx].key == key) {
                successful_lookups_++;
                auto end = std::chrono::high_resolution_clock::now();
                lookup_time_ns_ += std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
                return slots_[idx].value;
            }
        }
    }

    failed_lookups_++;
    auto end = std::chrono::high_resolution_clock::now();
    lookup_time_ns_ += std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
    return std::nullopt;
}

void HopscotchHashTable::enterScope(uint32_t /*scope_id*/, uint32_t /*parent_scope_id*/) {
    // Zero-cost inline no-op for non-scope-aware baseline
}

void HopscotchHashTable::exitScope(uint32_t /*scope_id*/) {
    // Zero-cost inline no-op for non-scope-aware baseline
}

TableMetrics HopscotchHashTable::getMetrics() const {
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

    m.memory_usage_bytes = sizeof(*this) + slots_.capacity() * sizeof(HopscotchSlot);
    m.collision_count = collision_count_;
    m.successful_lookups = successful_lookups_;
    m.failed_lookups = failed_lookups_;

    // Metric schema alignment matching manual requirements exactly:
    m.custom_metrics["neighbourhood_movements"] = static_cast<double>(neighbourhood_movements_);
    m.custom_metrics["key_comparisons"] = static_cast<double>(key_comparisons_);

    return m;
}

} // namespace colliscope
