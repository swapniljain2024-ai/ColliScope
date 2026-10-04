#pragma once

#include <string>
#include <optional>
#include <cstdint>
#include <tuple>
#include "metrics.hpp"

namespace colliscope {

struct SymbolValue {
    int64_t type_id{1};
    uint32_t line_declared{0};
    std::string metadata{""};

    bool operator==(const SymbolValue& other) const {
        return std::tie(type_id, line_declared, metadata) ==
               std::tie(other.type_id, other.line_declared, other.metadata);
    }

    bool operator!=(const SymbolValue& other) const {
        return !(*this == other);
    }
};

/**
 * Common pure-virtual symbol table interface for all collision-resolution schemes.
 * 
 * In Flat benchmarks (Scope Dimension = Flat), enterScope/exitScope operate as no-ops.
 * In Nested benchmarks, SVC-Hash uses its native scope hierarchy, whereas baselines
 * use standard scoped-wrapper mechanisms as documented in docs/architecture.md.
 */
class ISymbolTable {
public:
    virtual ~ISymbolTable() = default;

    // Declarations & Lookups
    virtual bool insert(const std::string& key, const SymbolValue& value, uint32_t scope_id) = 0;
    virtual std::optional<SymbolValue> lookup(const std::string& key, uint32_t scope_id) = 0;

    // Scope Lifecycle Management
    virtual void enterScope(uint32_t scope_id, uint32_t parent_scope_id) = 0;
    virtual void exitScope(uint32_t scope_id) = 0;

    // Table State Management
    virtual void reset() = 0;

    // Telemetry and Identification
    virtual TableMetrics getMetrics() const = 0;
    virtual std::string getAlgorithmName() const = 0;

    // Timing Control (benchmark engine can disable redundant internal per-operation clocks)
    virtual void setTimingEnabled(bool /*enabled*/) {}
    virtual bool isTimingEnabled() const { return true; }

    // Direct O(1) state inspectors
    virtual size_t getElementCount() const { return getMetrics().num_elements; }
    virtual size_t getCapacity() const { return getMetrics().capacity; }
    virtual size_t getMemoryUsage() const { return getMetrics().memory_usage_bytes; }
};

} // namespace colliscope
