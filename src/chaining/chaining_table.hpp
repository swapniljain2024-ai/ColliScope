#pragma once

#include <string>
#include <vector>
#include <optional>
#include <cstdint>
#include <cstddef>
#include <chrono>
#include <algorithm>

#include "common/symbol_table.hpp"
#include "common/metrics.hpp"

namespace colliscope {

struct ChainNode {
    std::string key{""};
    SymbolValue value{};
    uint32_t scope_id{0};
};

class ChainingHashTable : public ISymbolTable {
public:
    static constexpr uint64_t FNV_OFFSET_BASIS = 14695981039346656037ULL;
    static constexpr uint64_t FNV_PRIME = 1099511628211ULL;
    static constexpr size_t DEFAULT_INITIAL_BUCKETS = 16;
    static constexpr double MAX_LOAD_FACTOR = 1.0;

    explicit ChainingHashTable(size_t initial_buckets = DEFAULT_INITIAL_BUCKETS);
    ~ChainingHashTable() override = default;

    // ISymbolTable API
    bool insert(const std::string& key, const SymbolValue& value, uint32_t scope_id) override;
    std::optional<SymbolValue> lookup(const std::string& key, uint32_t scope_id) override;
    void enterScope(uint32_t scope_id, uint32_t parent_scope_id) override;
    void exitScope(uint32_t scope_id) override;
    void reset() override;
    TableMetrics getMetrics() const override;
    std::string getAlgorithmName() const override { return "chaining"; }

    // Diagnostic accessors
    size_t getBucketCount() const { return num_buckets_; }
    size_t getElementCount() const { return num_elements_; }

    static uint64_t computeHash(const std::string& key);

private:
    void checkAndRehash();

    size_t num_buckets_;
    size_t num_elements_{0};
    std::vector<std::vector<ChainNode>> buckets_;

    // Telemetry & metrics tracking
    mutable uint64_t insertion_time_ns_{0};
    mutable uint64_t lookup_time_ns_{0};
    mutable uint64_t scope_exit_time_ns_{0};
    mutable uint64_t total_operations_{0};
    mutable uint64_t successful_lookups_{0};
    mutable uint64_t failed_lookups_{0};
    mutable uint64_t collision_count_{0};
    mutable uint64_t key_comparisons_{0};
    mutable uint64_t traversal_length_{0};
};

} // namespace colliscope
