#include "chaining_table.hpp"

namespace colliscope {

uint64_t ChainingHashTable::computeHash(const std::string& key) {
    uint64_t hash = FNV_OFFSET_BASIS;
    for (unsigned char c : key) {
        hash ^= static_cast<uint64_t>(c);
        hash *= FNV_PRIME;
    }
    return hash;
}

ChainingHashTable::ChainingHashTable(size_t initial_buckets)
    : num_buckets_(std::max<size_t>(4, initial_buckets)),
      buckets_(num_buckets_) {
    reset();
}

void ChainingHashTable::reset() {
    num_buckets_ = std::max<size_t>(4, num_buckets_);
    buckets_ = std::vector<std::vector<ChainNode>>(num_buckets_);
    num_elements_ = 0;

    insertion_time_ns_ = 0;
    lookup_time_ns_ = 0;
    scope_exit_time_ns_ = 0;
    total_operations_ = 0;
    successful_lookups_ = 0;
    failed_lookups_ = 0;
    collision_count_ = 0;
    key_comparisons_ = 0;
    traversal_length_ = 0;
}

void ChainingHashTable::checkAndRehash() {
    double current_lf = static_cast<double>(num_elements_) / static_cast<double>(num_buckets_);
    if (current_lf <= MAX_LOAD_FACTOR) {
        return;
    }

    size_t new_buckets = num_buckets_ * 2;
    std::vector<std::vector<ChainNode>> new_table(new_buckets);

    for (const auto& chain : buckets_) {
        for (const auto& node : chain) {
            size_t idx = computeHash(node.key) % new_buckets;
            new_table[idx].push_back(node);
        }
    }

    buckets_ = std::move(new_table);
    num_buckets_ = new_buckets;
}

bool ChainingHashTable::insert(const std::string& key, const SymbolValue& value, uint32_t scope_id) {
    auto start = std::chrono::high_resolution_clock::now();
    total_operations_++;

    size_t bucket_idx = computeHash(key) % num_buckets_;
    auto& chain = buckets_[bucket_idx];

    if (!chain.empty()) {
        collision_count_++;
    }

    for (auto& node : chain) {
        traversal_length_++;
        key_comparisons_++;
        if (node.key == key) {
            // Update existing entry
            node.value = value;
            node.scope_id = scope_id;
            auto end = std::chrono::high_resolution_clock::now();
            insertion_time_ns_ += std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
            return true;
        }
    }

    // Insert new entry
    chain.push_back(ChainNode{key, value, scope_id});
    num_elements_++;

    checkAndRehash();

    auto end = std::chrono::high_resolution_clock::now();
    insertion_time_ns_ += std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
    return true;
}

std::optional<SymbolValue> ChainingHashTable::lookup(const std::string& key, uint32_t /*scope_id*/) {
    auto start = std::chrono::high_resolution_clock::now();
    total_operations_++;

    size_t bucket_idx = computeHash(key) % num_buckets_;
    const auto& chain = buckets_[bucket_idx];

    for (const auto& node : chain) {
        traversal_length_++;
        key_comparisons_++;
        if (node.key == key) {
            successful_lookups_++;
            auto end = std::chrono::high_resolution_clock::now();
            lookup_time_ns_ += std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
            return node.value;
        }
    }

    failed_lookups_++;
    auto end = std::chrono::high_resolution_clock::now();
    lookup_time_ns_ += std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
    return std::nullopt;
}

void ChainingHashTable::enterScope(uint32_t /*scope_id*/, uint32_t /*parent_scope_id*/) {
    // Zero-cost inline no-op for non-scope-aware baseline
}

void ChainingHashTable::exitScope(uint32_t /*scope_id*/) {
    // Zero-cost inline no-op for non-scope-aware baseline
}

TableMetrics ChainingHashTable::getMetrics() const {
    TableMetrics m;
    m.algorithm_name = getAlgorithmName();
    m.num_elements = num_elements_;
    m.capacity = num_buckets_;
    m.load_factor = (num_buckets_ > 0) ? (static_cast<double>(num_elements_) / static_cast<double>(num_buckets_)) : 0.0;
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

    // Memory calculation
    size_t mem = sizeof(*this) + buckets_.capacity() * sizeof(std::vector<ChainNode>);
    size_t max_chain = 0;
    size_t non_empty_buckets = 0;

    for (const auto& chain : buckets_) {
        mem += chain.capacity() * sizeof(ChainNode);
        if (!chain.empty()) {
            non_empty_buckets++;
            max_chain = std::max(max_chain, chain.size());
        }
    }

    m.memory_usage_bytes = mem;
    m.collision_count = collision_count_;
    m.successful_lookups = successful_lookups_;
    m.failed_lookups = failed_lookups_;

    // Metric schema alignment matching manual requirements exactly:
    m.custom_metrics["chain_length_max"] = static_cast<double>(max_chain);
    m.custom_metrics["chain_length_avg"] = (non_empty_buckets > 0) ? (static_cast<double>(num_elements_) / static_cast<double>(non_empty_buckets)) : 0.0;
    m.custom_metrics["key_comparisons"] = static_cast<double>(key_comparisons_);
    m.custom_metrics["traversal_length"] = static_cast<double>(traversal_length_);

    return m;
}

} // namespace colliscope
