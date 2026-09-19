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

struct HopscotchSlot {
    std::string key{""};
    SymbolValue value{};
    uint32_t scope_id{0};
    bool occupied{false};
    uint32_t hop_info{0}; // 32-bit neighborhood mask
};

class HopscotchHashTable : public ISymbolTable {
public:
    static constexpr uint64_t FNV_OFFSET_BASIS = 14695981039346656037ULL;
    static constexpr uint64_t FNV_PRIME = 1099511628211ULL;
    static constexpr uint32_t HOPSCOTCH_H = 32; // Neighborhood window size
    static constexpr size_t DEFAULT_INITIAL_CAPACITY = 32;
    static constexpr size_t MAX_RETRY_LIMIT = 50;

    explicit HopscotchHashTable(size_t initial_capacity = DEFAULT_INITIAL_CAPACITY);
    ~HopscotchHashTable() override = default;

    // ISymbolTable API
    bool insert(const std::string& key, const SymbolValue& value, uint32_t scope_id) override;
    std::optional<SymbolValue> lookup(const std::string& key, uint32_t scope_id) override;
    void enterScope(uint32_t scope_id, uint32_t parent_scope_id) override;
    void exitScope(uint32_t scope_id) override;
    void reset() override;
    TableMetrics getMetrics() const override;
    std::string getAlgorithmName() const override { return "hopscotch"; }

    // Diagnostic accessors
    size_t getCapacity() const { return capacity_; }
    size_t getElementCount() const { return num_elements_; }

    static uint64_t computeHash(const std::string& key);

private:
    bool insertInternal(const std::string& key, const SymbolValue& value, uint32_t scope_id);
    void rehash(size_t new_capacity);

    size_t capacity_;
    size_t num_elements_{0};
    std::vector<HopscotchSlot> slots_;

    // Telemetry & metrics tracking
    mutable uint64_t insertion_time_ns_{0};
    mutable uint64_t lookup_time_ns_{0};
    mutable uint64_t scope_exit_time_ns_{0};
    mutable uint64_t total_operations_{0};
    mutable uint64_t successful_lookups_{0};
    mutable uint64_t failed_lookups_{0};
    mutable uint64_t collision_count_{0};
    mutable uint64_t neighbourhood_movements_{0};
    mutable uint64_t key_comparisons_{0};
    mutable uint64_t rehash_count_{0};
};

} // namespace colliscope
