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

struct CuckooSlot {
    std::string key{""};
    SymbolValue value{};
    uint32_t scope_id{0};
    bool occupied{false};
};

class CuckooHashTable : public ISymbolTable {
public:
    static constexpr uint64_t DEFAULT_HASH_SEED_1 = 14695981039346656037ULL;
    static constexpr uint64_t DEFAULT_HASH_SEED_2 = 0x6c62272e07bb0142ULL;
    static constexpr size_t MAX_KICK_DEPTH = 500;
    static constexpr size_t DEFAULT_INITIAL_CAPACITY = 16;
    static constexpr size_t MAX_RETRY_LIMIT = 50;

    explicit CuckooHashTable(size_t initial_capacity = DEFAULT_INITIAL_CAPACITY);
    ~CuckooHashTable() override = default;

    // ISymbolTable API
    bool insert(const std::string& key, const SymbolValue& value, uint32_t scope_id) override;
    std::optional<SymbolValue> lookup(const std::string& key, uint32_t scope_id) override;
    void enterScope(uint32_t scope_id, uint32_t parent_scope_id) override;
    void exitScope(uint32_t scope_id) override;
    void reset() override;
    TableMetrics getMetrics() const override;
    std::string getAlgorithmName() const override { return "cuckoo"; }

    // Diagnostic accessors
    size_t getCapacity() const { return capacity_; }
    size_t getElementCount() const { return num_elements_; }
    uint64_t getRehashCount() const { return rehash_count_; }

    static uint64_t computeHash(const std::string& key, uint64_t seed);

private:
    void computeCandidatePositions(const std::string& key, size_t& pos1, size_t& pos2) const;
    bool insertInternal(const std::string& key, const SymbolValue& value, uint32_t scope_id, CuckooSlot* evicted_out = nullptr);
    void rehash(size_t new_capacity, const CuckooSlot* extra_slot = nullptr);

    size_t capacity_;
    size_t num_elements_{0};
    std::vector<CuckooSlot> slots_;

    uint64_t hash_seed_1_{DEFAULT_HASH_SEED_1};
    uint64_t hash_seed_2_{DEFAULT_HASH_SEED_2};

    // Telemetry & metrics tracking
    mutable uint64_t insertion_time_ns_{0};
    mutable uint64_t lookup_time_ns_{0};
    mutable uint64_t scope_exit_time_ns_{0};
    mutable uint64_t total_operations_{0};
    mutable uint64_t successful_lookups_{0};
    mutable uint64_t failed_lookups_{0};
    mutable uint64_t collision_count_{0};
    mutable uint64_t relocations_kicks_{0};
    mutable uint64_t rehash_count_{0};
    mutable uint64_t max_displacement_{0};
};

} // namespace colliscope
