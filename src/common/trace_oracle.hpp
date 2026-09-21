#pragma once

#include <string>
#include <unordered_map>
#include <vector>
#include <optional>
#include <cstdint>
#include <stdexcept>
#include <chrono>

#include "common/symbol_table.hpp"
#include "common/metrics.hpp"

namespace colliscope {

/**
 * Independent Semantic Correctness Oracle for Scoped Symbol Tables.
 *
 * Serves as the ground-truth reference model for compiler symbol-table semantics.
 * Built as an explicit lexical scope tree using standard library maps, completely
 * decoupled from production collision-resolution implementations (Chaining, Cuckoo,
 * Hopscotch, and SVC-Hash).
 */
class TraceOracle : public ISymbolTable {
public:
    struct ScopeNode {
        uint32_t scope_id{0};
        uint32_t parent_id{0};
        bool active{true};
        std::unordered_map<std::string, SymbolValue> symbols;
    };

    TraceOracle() {
        reset();
    }

    ~TraceOracle() override = default;

    // ISymbolTable API
    bool insert(const std::string& key, const SymbolValue& value, uint32_t scope_id) override {
        auto start = std::chrono::high_resolution_clock::now();
        total_operations_++;

        auto it = scopes_.find(scope_id);
        if (it == scopes_.end() || !it->second.active) {
            auto end = std::chrono::high_resolution_clock::now();
            insertion_time_ns_ += std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
            return false;
        }

        it->second.symbols[key] = value;
        num_elements_ = countTotalElements();

        auto end = std::chrono::high_resolution_clock::now();
        insertion_time_ns_ += std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
        return true;
    }

    std::optional<SymbolValue> lookup(const std::string& key, uint32_t scope_id) override {
        auto start = std::chrono::high_resolution_clock::now();
        total_operations_++;

        // Lexical scope resolution: walks the active scope's parent chain toward
        // the root and resolves the first active declaration found, implementing shadowing.
        uint32_t curr = scope_id;
        while (true) {
            auto it = scopes_.find(curr);
            if (it == scopes_.end() || !it->second.active) {
                break;
            }

            auto sym_it = it->second.symbols.find(key);
            if (sym_it != it->second.symbols.end()) {
                successful_lookups_++;
                auto end = std::chrono::high_resolution_clock::now();
                lookup_time_ns_ += std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
                return sym_it->second;
            }

            if (curr == 0 || it->second.parent_id == curr) {
                break;
            }
            curr = it->second.parent_id;
        }

        failed_lookups_++;
        auto end = std::chrono::high_resolution_clock::now();
        lookup_time_ns_ += std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
        return std::nullopt;
    }

    void enterScope(uint32_t scope_id, uint32_t parent_scope_id) override {
        total_operations_++;

        if (scope_id == 0 && parent_scope_id == 0 && scopes_.count(0) && scopes_[0].active) {
            // Root scope already active
            return;
        }

        // Scope Entry Validation:
        // 1. Parent scope must exist and be currently active
        auto parent_it = scopes_.find(parent_scope_id);
        if (parent_it == scopes_.end() || !parent_it->second.active) {
            throw std::runtime_error("TraceOracle::enterScope rejected: parent scope " +
                                     std::to_string(parent_scope_id) + " is not active");
        }

        // 2. Parent scope must equal currently active scope (standard stack discipline)
        if (parent_scope_id != current_scope_id_) {
            throw std::runtime_error("TraceOracle::enterScope rejected: parent scope " +
                                     std::to_string(parent_scope_id) + " is not current scope " +
                                     std::to_string(current_scope_id_));
        }

        // 3. New scope_id must not already be active
        auto existing_it = scopes_.find(scope_id);
        if (existing_it != scopes_.end() && existing_it->second.active) {
            throw std::runtime_error("TraceOracle::enterScope rejected: scope " +
                                     std::to_string(scope_id) + " is already active");
        }

        scopes_[scope_id] = ScopeNode{scope_id, parent_scope_id, true, {}};
        scope_stack_.push_back(scope_id);
        current_scope_id_ = scope_id;
    }

    void exitScope(uint32_t scope_id) override {
        auto start = std::chrono::high_resolution_clock::now();
        total_operations_++;

        // Scope Exit Validation:
        // 1. Scope must be currently active scope at top of stack
        if (scope_id != current_scope_id_) {
            throw std::runtime_error("TraceOracle::exitScope rejected: scope " +
                                     std::to_string(scope_id) + " is not current scope " +
                                     std::to_string(current_scope_id_));
        }

        // 2. Scope must exist and be active
        auto it = scopes_.find(scope_id);
        if (it == scopes_.end() || !it->second.active) {
            throw std::runtime_error("TraceOracle::exitScope rejected: scope " +
                                     std::to_string(scope_id) + " is not active");
        }

        // Deactivate scope
        it->second.active = false;

        if (!scope_stack_.empty() && scope_stack_.back() == scope_id) {
            scope_stack_.pop_back();
        }
        current_scope_id_ = scope_stack_.empty() ? 0 : scope_stack_.back();
        num_elements_ = countTotalElements();

        auto end = std::chrono::high_resolution_clock::now();
        scope_exit_time_ns_ += std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
    }

    void reset() override {
        scopes_.clear();
        scope_stack_.clear();

        // Register root global scope 0
        scopes_[0] = ScopeNode{0, 0, true, {}};
        scope_stack_.push_back(0);
        current_scope_id_ = 0;

        num_elements_ = 0;
        insertion_time_ns_ = 0;
        lookup_time_ns_ = 0;
        scope_exit_time_ns_ = 0;
        total_operations_ = 0;
        successful_lookups_ = 0;
        failed_lookups_ = 0;
    }

    TableMetrics getMetrics() const override {
        TableMetrics m;
        m.algorithm_name = getAlgorithmName();
        m.num_elements = num_elements_;
        m.capacity = scopes_.size();
        m.load_factor = (scopes_.size() > 0) ? (static_cast<double>(num_elements_) / static_cast<double>(scopes_.size())) : 0.0;
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

        m.memory_usage_bytes = sizeof(*this);
        for (const auto& kv : scopes_) {
            m.memory_usage_bytes += sizeof(ScopeNode) + kv.second.symbols.size() * (sizeof(std::string) + sizeof(SymbolValue));
        }
        m.collision_count = 0;
        m.successful_lookups = successful_lookups_;
        m.failed_lookups = failed_lookups_;

        return m;
    }

    std::string getAlgorithmName() const override {
        return "oracle";
    }

    // Diagnostics
    uint32_t getCurrentScopeId() const { return current_scope_id_; }
    bool isScopeActive(uint32_t scope_id) const {
        auto it = scopes_.find(scope_id);
        return (it != scopes_.end()) && it->second.active;
    }
    size_t getActiveScopeDepth() const { return scope_stack_.size(); }

private:
    size_t countTotalElements() const {
        size_t count = 0;
        for (const auto& kv : scopes_) {
            if (kv.second.active) {
                count += kv.second.symbols.size();
            }
        }
        return count;
    }

    std::unordered_map<uint32_t, ScopeNode> scopes_;
    std::vector<uint32_t> scope_stack_;
    uint32_t current_scope_id_{0};
    size_t num_elements_{0};

    mutable uint64_t insertion_time_ns_{0};
    mutable uint64_t lookup_time_ns_{0};
    mutable uint64_t scope_exit_time_ns_{0};
    mutable uint64_t total_operations_{0};
    mutable uint64_t successful_lookups_{0};
    mutable uint64_t failed_lookups_{0};
};

} // namespace colliscope
