#pragma once

#include <string>
#include <vector>
#include <memory>
#include <map>
#include <functional>
#include <iostream>

#include "common/symbol_table.hpp"
#include "common/trace_parser.hpp"
#include "common/scoped_table_wrapper.hpp"
#include "chaining_table.hpp"
#include "cuckoo_table.hpp"
#include "hopscotch_table.hpp"
#include "svc_hash/svc_hash_table.hpp"
#include "benchmark_metrics.hpp"

namespace colliscope {

struct BenchmarkConfigOptions {
    std::vector<std::string> algorithms{"chaining", "cuckoo", "hopscotch", "svc_hash"};
    size_t repetitions{5};
    size_t warmup_trials{1};
    bool scoped_baselines_on_nested{true};
    size_t initial_capacity{16};
};

struct TraceBenchmarkRunResult {
    std::string trace_file;
    bool is_nested_scope{false};
    size_t total_trace_commands{0};
    std::map<std::string, AlgorithmBenchmarkSummary> algorithm_summaries;
    std::vector<BenchmarkTrialResult> all_trials;

    nlohmann::json toJson() const {
        nlohmann::json j;
        j["trace_file"] = trace_file;
        j["is_nested_scope"] = is_nested_scope;
        j["total_trace_commands"] = total_trace_commands;
        nlohmann::json alg_map;
        for (const auto& pair : algorithm_summaries) {
            alg_map[pair.first] = pair.second.toJson();
        }
        j["algorithms"] = alg_map;
        return j;
    }
};

class BenchmarkEngine {
public:
    BenchmarkEngine() = default;

    /**
     * Executes a single trial of the trace commands against the specified table.
     * Records amortized batch latency per operation (ns) and computes latency percentiles.
     * Note: Sub-tick operations (< 100 ns) are measured via run-based batches (up to 16 ops)
     * and post-trial amortization across verified wall time. These statistics represent
     * amortized batch latency per operation, not individually measured per-operation hardware latency.
     */
    static BenchmarkTrialResult runTrial(
        const std::vector<TraceCommand>& commands,
        ISymbolTable& table,
        const std::string& trace_name,
        uint32_t trial_index,
        bool is_warmup
    );

    /**
     * Replays trace commands against all requested algorithms under identical conditions.
     */
    static TraceBenchmarkRunResult benchmarkTrace(
        const std::string& trace_filepath,
        const BenchmarkConfigOptions& options = BenchmarkConfigOptions()
    );

    /**
     * Replays trace commands directly from string content.
     */
    static TraceBenchmarkRunResult benchmarkTraceString(
        const std::string& trace_content,
        const std::string& trace_name,
        const BenchmarkConfigOptions& options = BenchmarkConfigOptions()
    );

    /**
     * Instantiates an ISymbolTable corresponding to the algorithm name, applying
     * ScopedTableWrapper for baselines on nested traces if requested.
     */
    static std::unique_ptr<ISymbolTable> createTable(
        const std::string& algorithm_name,
        bool is_nested_trace,
        bool use_scoped_wrapper,
        size_t initial_capacity = 16
    );

    /**
     * Exports a collection of trace benchmark results to a formatted JSON file.
     */
    static void exportToJson(
        const std::string& filepath,
        const std::vector<TraceBenchmarkRunResult>& results
    );

    /**
     * Exports all trial rows to a standard CSV file for statistical analysis.
     */
    static void exportToCsv(
        const std::string& filepath,
        const std::vector<TraceBenchmarkRunResult>& results
    );
};

} // namespace colliscope
