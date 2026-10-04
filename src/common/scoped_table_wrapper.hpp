#pragma once

#include <string>
#include <vector>
#include <unordered_map>
#include <memory>
#include <optional>
#include <chrono>

#include "common/symbol_table.hpp"
#include "common/metrics.hpp"

namespace colliscope {

/**
 * ScopedTableWrapper: Implements the canonical compiler symbol table pattern
 * (Strategy A - Scoped Table Hierarchy from docs/architecture.md Section 3).
 * 
 * Wraps any flat ISymbolTable implementation (Separate Chaining, Plain Cuckoo,
 * Hopscotch Hashing) into a scope-aware table hierarchy without altering or
 * contaminating the underlying flat collision-resolution algorithm.
 * 
 * Each active lexical scope possesses its own dedicated flat hash table.
 * Lookup traverses the scope ancestor chain from target scope up to global scope (0).
 * Scope exit invalidates and discards the table instance for that scope.
 */
template <typename BaseTable>
class ScopedTableWrapper : public ISymbolTable {
public:
    explicit ScopedTableWrapper(size_t table_initial_capacity = 16)
        : table_initial_capacity_(table_initial_capacity) {
        BaseTable dummy(table_initial_capacity);
        base_algorithm_name_ = dummy.getAlgorithmName();
        reset();
    }

    ~ScopedTableWrapper() override = default;

    void reset() override {
        tables_.clear();
        scope_parents_.clear();
        active_scopes_.clear();

        // Scope 0 (global) always exists
        tables_[0] = std::make_unique<BaseTable>(table_initial_capacity_);
        tables_[0]->setTimingEnabled(timing_enabled_);
        scope_parents_[0] = 0;
        active_scopes_[0] = true;

        current_elements_ = 0;
        current_capacity_ = tables_[0]->getCapacity();
        current_memory_bytes_ = sizeof(*this) + tables_[0]->getMemoryUsage();

        peak_elements_ = 0;
        peak_capacity_ = current_capacity_;
        peak_memory_bytes_ = current_memory_bytes_;
        peak_load_factor_ = 0.0;

        cumulative_collisions_ = 0;
        cumulative_custom_metrics_.clear();

        insertion_time_ns_ = 0;
        lookup_time_ns_ = 0;
        scope_exit_time_ns_ = 0;
        total_operations_ = 0;
        successful_lookups_ = 0;
        failed_lookups_ = 0;
    }

    // Timing Control
    void setTimingEnabled(bool enabled) override {
        timing_enabled_ = enabled;
        for (auto& pair : tables_) {
            pair.second->setTimingEnabled(enabled);
        }
    }
    bool isTimingEnabled() const override { return timing_enabled_; }

    size_t getElementCount() const override { return peak_elements_; }
    size_t getCapacity() const override { return peak_capacity_; }
    size_t getMemoryUsage() const override { return peak_memory_bytes_; }

    void enterScope(uint32_t scope_id, uint32_t parent_scope_id) override {
        total_operations_++;
        scope_parents_[scope_id] = parent_scope_id;
        active_scopes_[scope_id] = true;

        if (tables_.find(scope_id) == tables_.end()) {
            auto new_table = std::make_unique<BaseTable>(table_initial_capacity_);
            new_table->setTimingEnabled(timing_enabled_);
            current_capacity_ += new_table->getCapacity();
            current_memory_bytes_ += new_table->getMemoryUsage();
            tables_[scope_id] = std::move(new_table);
        } else {
            size_t old_elems = tables_[scope_id]->getElementCount();
            size_t old_cap = tables_[scope_id]->getCapacity();
            size_t old_mem = tables_[scope_id]->getMemoryUsage();
            tables_[scope_id]->reset();
            tables_[scope_id]->setTimingEnabled(timing_enabled_);
            current_elements_ = (current_elements_ >= old_elems) ? (current_elements_ - old_elems) : 0;
            current_capacity_ = (current_capacity_ >= old_cap) ? (current_capacity_ - old_cap + tables_[scope_id]->getCapacity()) : tables_[scope_id]->getCapacity();
            current_memory_bytes_ = (current_memory_bytes_ >= old_mem) ? (current_memory_bytes_ - old_mem + tables_[scope_id]->getMemoryUsage()) : (sizeof(*this) + tables_[scope_id]->getMemoryUsage());
        }

        peak_capacity_ = std::max(peak_capacity_, current_capacity_);
        peak_memory_bytes_ = std::max(peak_memory_bytes_, current_memory_bytes_);
    }

    void exitScope(uint32_t scope_id) override {
        auto start = timing_enabled_ ? std::chrono::high_resolution_clock::now() : std::chrono::high_resolution_clock::time_point{};
        total_operations_++;

        active_scopes_[scope_id] = false;

        auto it = tables_.find(scope_id);
        if (it != tables_.end()) {
            TableMetrics sub = it->second->getMetrics();
            current_elements_ = (current_elements_ >= sub.num_elements) ? (current_elements_ - sub.num_elements) : 0;
            current_capacity_ = (current_capacity_ >= sub.capacity) ? (current_capacity_ - sub.capacity) : 0;
            current_memory_bytes_ = (current_memory_bytes_ >= sub.memory_usage_bytes) ? (current_memory_bytes_ - sub.memory_usage_bytes) : sizeof(*this);

            cumulative_collisions_ += sub.collision_count;
            for (const auto& cm : sub.custom_metrics) {
                cumulative_custom_metrics_[cm.first] += cm.second;
            }

            tables_.erase(it);
        }

        if (timing_enabled_) {
            auto end = std::chrono::high_resolution_clock::now();
            scope_exit_time_ns_ += std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
        }
    }

    bool insert(const std::string& key, const SymbolValue& value, uint32_t scope_id) override {
        auto start = timing_enabled_ ? std::chrono::high_resolution_clock::now() : std::chrono::high_resolution_clock::time_point{};
        total_operations_++;

        if (tables_.find(scope_id) == tables_.end()) {
            auto new_table = std::make_unique<BaseTable>(table_initial_capacity_);
            new_table->setTimingEnabled(timing_enabled_);
            current_capacity_ += new_table->getCapacity();
            current_memory_bytes_ += new_table->getMemoryUsage();
            tables_[scope_id] = std::move(new_table);
            active_scopes_[scope_id] = true;
            if (scope_parents_.find(scope_id) == scope_parents_.end()) {
                scope_parents_[scope_id] = 0;
            }
        }

        size_t old_elems = tables_[scope_id]->getElementCount();
        size_t old_cap = tables_[scope_id]->getCapacity();
        size_t old_mem = tables_[scope_id]->getMemoryUsage();

        bool ok = tables_[scope_id]->insert(key, value, scope_id);

        size_t new_elems = tables_[scope_id]->getElementCount();
        size_t new_cap = tables_[scope_id]->getCapacity();
        size_t new_mem = tables_[scope_id]->getMemoryUsage();

        current_elements_ += (new_elems - old_elems);
        if (new_cap > old_cap) {
            current_capacity_ += (new_cap - old_cap);
        }
        if (new_mem > old_mem) {
            current_memory_bytes_ += (new_mem - old_mem);
        }

        peak_elements_ = std::max(peak_elements_, current_elements_);
        peak_capacity_ = std::max(peak_capacity_, current_capacity_);
        peak_memory_bytes_ = std::max(peak_memory_bytes_, current_memory_bytes_);

        if (current_capacity_ > 0) {
            double current_lf = static_cast<double>(current_elements_) / static_cast<double>(current_capacity_);
            peak_load_factor_ = std::max(peak_load_factor_, current_lf);
        }

        if (timing_enabled_) {
            auto end = std::chrono::high_resolution_clock::now();
            insertion_time_ns_ += std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
        }
        return ok;
    }

    std::optional<SymbolValue> lookup(const std::string& key, uint32_t scope_id) override {
        auto start = timing_enabled_ ? std::chrono::high_resolution_clock::now() : std::chrono::high_resolution_clock::time_point{};
        total_operations_++;

        uint32_t curr = scope_id;
        while (true) {
            auto it = tables_.find(curr);
            if (it != tables_.end() && active_scopes_[curr]) {
                auto res = it->second->lookup(key, curr);
                if (res.has_value()) {
                    successful_lookups_++;
                    if (timing_enabled_) {
                        auto end = std::chrono::high_resolution_clock::now();
                        lookup_time_ns_ += std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
                    }
                    return res;
                }
            }

            if (curr == 0) {
                break;
            }
            auto p_it = scope_parents_.find(curr);
            curr = (p_it != scope_parents_.end()) ? p_it->second : 0;
        }

        failed_lookups_++;
        if (timing_enabled_) {
            auto end = std::chrono::high_resolution_clock::now();
            lookup_time_ns_ += std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
        }
        return std::nullopt;
    }

    TableMetrics getMetrics() const override {
        TableMetrics aggregated;
        aggregated.algorithm_name = "scoped_" + base_algorithm_name_;
        aggregated.insertion_time_ns = insertion_time_ns_;
        aggregated.lookup_time_ns = lookup_time_ns_;
        aggregated.scope_exit_time_ns = scope_exit_time_ns_;
        aggregated.total_operations = total_operations_;
        aggregated.successful_lookups = successful_lookups_;
        aggregated.failed_lookups = failed_lookups_;

        uint64_t total_time = insertion_time_ns_ + lookup_time_ns_ + scope_exit_time_ns_;
        if (total_time > 0) {
            aggregated.throughput_ops_sec = (static_cast<double>(total_operations_) / static_cast<double>(total_time)) * 1e9;
        }

        // Aggregate across currently active scope tables
        uint64_t active_elements = 0;
        uint64_t active_capacity = 0;
        uint64_t active_memory = sizeof(*this);
        uint64_t active_collisions = 0;

        for (const auto& pair : tables_) {
            TableMetrics sub = pair.second->getMetrics();
            active_elements += sub.num_elements;
            active_capacity += sub.capacity;
            active_memory += sub.memory_usage_bytes;
            active_collisions += sub.collision_count;

            for (const auto& cm : sub.custom_metrics) {
                aggregated.custom_metrics[cm.first] += cm.second;
            }
        }

        // Merge cumulative custom metrics from exited tables
        for (const auto& cm : cumulative_custom_metrics_) {
            aggregated.custom_metrics[cm.first] += cm.second;
        }

        // Fix for ScopedTableWrapper metrics (Audit Item 3):
        // Report meaningful peak metrics when scopes have exited, and store explicit peak metrics
        aggregated.num_elements = (active_elements > 0) ? active_elements : peak_elements_;
        aggregated.capacity = (active_capacity > 0) ? active_capacity : peak_capacity_;
        aggregated.load_factor = (peak_load_factor_ > 0.0) ? peak_load_factor_ : 
                                 ((aggregated.capacity > 0) ? (static_cast<double>(aggregated.num_elements) / static_cast<double>(aggregated.capacity)) : 0.0);
        aggregated.memory_usage_bytes = (active_memory > sizeof(*this)) ? active_memory : peak_memory_bytes_;
        aggregated.collision_count = active_collisions + cumulative_collisions_;

        aggregated.custom_metrics["peak_elements"] = static_cast<double>(peak_elements_);
        aggregated.custom_metrics["peak_capacity"] = static_cast<double>(peak_capacity_);
        aggregated.custom_metrics["peak_load_factor"] = peak_load_factor_;
        aggregated.custom_metrics["peak_memory_bytes"] = static_cast<double>(peak_memory_bytes_);
        aggregated.custom_metrics["active_scope_tables"] = static_cast<double>(tables_.size());

        return aggregated;
    }

    std::string getAlgorithmName() const override {
        return "scoped_" + base_algorithm_name_;
    }

private:
    std::string base_algorithm_name_{"unknown"};
    size_t table_initial_capacity_;
    std::unordered_map<uint32_t, std::unique_ptr<BaseTable>> tables_;
    std::unordered_map<uint32_t, uint32_t> scope_parents_;
    std::unordered_map<uint32_t, bool> active_scopes_;
    bool timing_enabled_{true};

    // Peak and cumulative telemetry across scope lifecycles
    mutable size_t current_elements_{0};
    mutable size_t current_capacity_{0};
    mutable size_t current_memory_bytes_{0};

    mutable size_t peak_elements_{0};
    mutable size_t peak_capacity_{0};
    mutable size_t peak_memory_bytes_{sizeof(ScopedTableWrapper)};
    mutable double peak_load_factor_{0.0};

    mutable uint64_t cumulative_collisions_{0};
    mutable std::map<std::string, double> cumulative_custom_metrics_;

    mutable uint64_t insertion_time_ns_{0};
    mutable uint64_t lookup_time_ns_{0};
    mutable uint64_t scope_exit_time_ns_{0};
    mutable uint64_t total_operations_{0};
    mutable uint64_t successful_lookups_{0};
    mutable uint64_t failed_lookups_{0};
};

} // namespace colliscope
