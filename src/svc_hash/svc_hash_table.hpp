#pragma once

#include <string>
#include <vector>
#include <unordered_map>
#include <optional>
#include <cstdint>
#include <cstddef>
#include <chrono>
#include <stdexcept>

#include "common/symbol_table.hpp"
#include "common/metrics.hpp"

namespace colliscope {

struct BucketEntry {
    std::string key{""};
    SymbolValue value{};
    uint32_t scope_id{0};
    bool occupied{false};
    bool tombstoned{false};
};

struct Bucket {
    static constexpr size_t BUCKET_SIZE = 4;
    BucketEntry entries[BUCKET_SIZE];
};

struct ScopeInfo {
    uint32_t scope_id{0};
    uint32_t parent_id{0};
    bool active{true};
};

class SvcHashTable : public ISymbolTable {
public:
    static constexpr uint64_t HASH_SEED_1 = 14695981039346656037ULL;
    static constexpr uint64_t HASH_SEED_2 = 0x6c62272e07bb0142ULL;
    static constexpr size_t STASH_SIZE = 8;
    static constexpr size_t MAX_KICK_DEPTH = 500;
    static constexpr size_t DEFAULT_INITIAL_BUCKETS = 16;

    explicit SvcHashTable(size_t initial_buckets = DEFAULT_INITIAL_BUCKETS);
    ~SvcHashTable() override = default;

    // ISymbolTable API
    bool insert(const std::string& key, const SymbolValue& value, uint32_t scope_id) override;
    std::optional<SymbolValue> lookup(const std::string& key, uint32_t scope_id) override;
    void enterScope(uint32_t scope_id, uint32_t parent_scope_id) override;
    void exitScope(uint32_t scope_id) override;
    void reset() override;
    TableMetrics getMetrics() const override;
    std::string getAlgorithmName() const override { return "svc_hash"; }

    // Helper diagnostics & inspection
    size_t getBucketCount() const { return num_buckets_; }
    size_t getOccupiedCount() const { return occupied_count_; }
    size_t getTombstoneCount() const { return tombstone_count_; }
    size_t getStashCount() const { return stash_count_; }
    uint32_t getCurrentScopeId() const { return current_scope_id_; }
    bool isScopeActive(uint32_t scope_id) const;

    static uint64_t computeHash(const std::string& key, uint32_t scope_id, uint64_t offset_basis);

private:
    void computeCandidateBuckets(const std::string& key, uint32_t scope_id, size_t& b1, size_t& b2) const;
    bool insertInternal(const std::string& key, const SymbolValue& value, uint32_t scope_id);
    void rebuild(size_t new_num_buckets);
    void checkAndRebuildIfNeeded();

    size_t num_buckets_;
    std::vector<Bucket> buckets_;
    BucketEntry stash_[STASH_SIZE];

    size_t occupied_count_{0};
    size_t tombstone_count_{0};
    size_t stash_count_{0};

    uint32_t current_scope_id_{0};
    std::vector<uint32_t> scope_stack_;
    std::unordered_map<uint32_t, ScopeInfo> scope_registry_;
    std::unordered_map<uint32_t, std::vector<std::string>> scope_entries_;

    // Telemetry & metrics tracking
    mutable uint64_t insertion_time_ns_{0};
    mutable uint64_t lookup_time_ns_{0};
    mutable uint64_t scope_exit_time_ns_{0};
    mutable uint64_t total_operations_{0};
    mutable uint64_t successful_lookups_{0};
    mutable uint64_t failed_lookups_{0};
    mutable uint64_t collision_count_{0};
    mutable uint64_t kick_count_{0};
    mutable uint64_t rebuild_count_{0};
};

} // namespace colliscope
