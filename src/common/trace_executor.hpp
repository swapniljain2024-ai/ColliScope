#pragma once

#include <vector>
#include <string>
#include <optional>
#include <cstdint>
#include <chrono>
#include <stdexcept>

#include "common/symbol_table.hpp"
#include "common/trace_parser.hpp"
#include "common/metrics.hpp"
#include "common/third_party/json.hpp"

namespace colliscope {

struct ExecutionResult {
    std::string algorithm_name{""};
    size_t total_commands{0};
    size_t declare_count{0};
    size_t reference_count{0};
    size_t enter_scope_count{0};
    size_t exit_scope_count{0};
    size_t successful_references{0};
    size_t failed_references{0};

    // Ordered list of lookup results for each REFERENCE command
    std::vector<std::optional<SymbolValue>> reference_results;

    uint64_t total_execution_time_ns{0};
    TableMetrics final_metrics;

    bool matchesLogicalResults(const ExecutionResult& other) const {
        if (reference_results.size() != other.reference_results.size()) {
            return false;
        }
        for (size_t i = 0; i < reference_results.size(); ++i) {
            if (reference_results[i] != other.reference_results[i]) {
                return false;
            }
        }
        return true;
    }

    nlohmann::json toJson() const {
        nlohmann::json j;
        j["algorithm_name"] = algorithm_name;
        j["total_commands"] = total_commands;
        j["declare_count"] = declare_count;
        j["reference_count"] = reference_count;
        j["enter_scope_count"] = enter_scope_count;
        j["exit_scope_count"] = exit_scope_count;
        j["successful_references"] = successful_references;
        j["failed_references"] = failed_references;
        j["total_execution_time_ns"] = total_execution_time_ns;

        nlohmann::json ref_arr = nlohmann::json::array();
        for (const auto& opt_val : reference_results) {
            if (opt_val.has_value()) {
                ref_arr.push_back({
                    {"found", true},
                    {"type_id", opt_val->type_id},
                    {"line_declared", opt_val->line_declared},
                    {"metadata", opt_val->metadata}
                });
            } else {
                ref_arr.push_back({{"found", false}});
            }
        }
        j["reference_results"] = ref_arr;
        j["final_metrics"] = final_metrics.toJson();
        return j;
    }
};

class TraceExecutor {
public:
    /**
     * Replays an ordered sequence of trace commands deterministically against any ISymbolTable.
     * Enforces logical fairness by applying the exact same sequence of logical trace operations
     * to every table implementation.
     */
    static ExecutionResult execute(const std::vector<TraceCommand>& commands, ISymbolTable& table) {
        ExecutionResult result;
        result.algorithm_name = table.getAlgorithmName();

        std::vector<uint32_t> scope_stack;
        scope_stack.push_back(0); // Scope 0 (root) is active initially

        auto start_time = std::chrono::high_resolution_clock::now();

        for (const auto& cmd : commands) {
            result.total_commands++;
            uint32_t current_scope = scope_stack.empty() ? 0 : scope_stack.back();

            switch (cmd.op) {
                case TraceOp::ENTER_SCOPE: {
                    result.enter_scope_count++;
                    uint32_t effective_parent = cmd.parent_scope_id.value_or(current_scope);
                    table.enterScope(cmd.scope_id, effective_parent);
                    scope_stack.push_back(cmd.scope_id);
                    break;
                }

                case TraceOp::EXIT_SCOPE: {
                    result.exit_scope_count++;
                    table.exitScope(cmd.scope_id);
                    if (!scope_stack.empty() && scope_stack.back() == cmd.scope_id) {
                        scope_stack.pop_back();
                    }
                    break;
                }

                case TraceOp::DECLARE: {
                    result.declare_count++;
                    uint32_t target_scope = cmd.has_explicit_scope ? cmd.scope_id : current_scope;
                    SymbolValue val{cmd.type_id, cmd.line_number, ""};
                    table.insert(cmd.identifier, val, target_scope);
                    break;
                }

                case TraceOp::REFERENCE: {
                    result.reference_count++;
                    uint32_t target_scope = cmd.has_explicit_scope ? cmd.scope_id : current_scope;
                    auto lookup_res = table.lookup(cmd.identifier, target_scope);
                    result.reference_results.push_back(lookup_res);

                    if (lookup_res.has_value()) {
                        result.successful_references++;
                    } else {
                        result.failed_references++;
                    }
                    break;
                }
            }
        }

        auto end_time = std::chrono::high_resolution_clock::now();
        result.total_execution_time_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(end_time - start_time).count();
        result.final_metrics = table.getMetrics();

        return result;
    }
};

} // namespace colliscope
