#include "third_party/catch2/catch.hpp"
#include "benchmark_engine.hpp"
#include "benchmark_timer.hpp"
#include "common/trace_parser.hpp"
#include "common/trace_oracle.hpp"

#include <string>
#include <vector>
#include <fstream>
#include <cstdio>

using namespace colliscope;

TEST_CASE("BenchmarkEngine - Flat Trace Replay Across 4 Algorithms", "[benchmark_engine]") {
    std::string flat_trace =
        "ENTER_SCOPE 0\n"
        "DECLARE sym_a 10 0\n"
        "DECLARE sym_b 20 0\n"
        "DECLARE sym_c 30 0\n"
        "REFERENCE sym_a 0\n"
        "REFERENCE sym_b 0\n"
        "REFERENCE sym_missing 0\n"
        "DECLARE sym_d 40 0\n"
        "REFERENCE sym_d 0\n"
        "REFERENCE sym_c 0\n"
        "EXIT_SCOPE 0\n";

    BenchmarkConfigOptions options;
    options.algorithms = {"chaining", "cuckoo", "hopscotch", "svc_hash"};
    options.repetitions = 3;
    options.warmup_trials = 1;

    auto result = BenchmarkEngine::benchmarkTraceString(flat_trace, "test_flat", options);

    REQUIRE(result.trace_file == "test_flat");
    REQUIRE_FALSE(result.is_nested_scope);
    REQUIRE(result.total_trace_commands == 11);
    REQUIRE(result.algorithm_summaries.size() == 4);

    for (const auto& alg_name : options.algorithms) {
        REQUIRE(result.algorithm_summaries.find(alg_name) != result.algorithm_summaries.end());
        const auto& summary = result.algorithm_summaries[alg_name];

        REQUIRE(summary.repetitions == 3);
        REQUIRE(summary.trials.size() == 3);

        // Every algorithm must achieve 100% agreement on 4 successful references and 1 failed reference
        REQUIRE(summary.successful_references == 4);
        REQUIRE(summary.failed_references == 1);

        // Throughput must be strictly positive
        REQUIRE(summary.mean_throughput_ops_sec > 0.0);

        // Timings must be recorded
        REQUIRE(summary.mean_total_time_ns > 0.0);

        // Check each trial's latency statistics and mathematical invariants
        for (const auto& trial : summary.trials) {
            REQUIRE(trial.total_operations == 11);
            REQUIRE(trial.insert_count == 4);
            REQUIRE(trial.lookup_count == 5);
            REQUIRE(trial.successful_references == 4);
            REQUIRE(trial.failed_references == 1);


            // Latency percentiles monotonicity invariant: min <= p50 <= p95 <= p99 <= max
            REQUIRE(trial.insert_latency.count == 4);
            REQUIRE(trial.insert_latency.min_ns <= trial.insert_latency.p50_ns);
            REQUIRE(trial.insert_latency.p50_ns <= trial.insert_latency.p95_ns);
            REQUIRE(trial.insert_latency.p95_ns <= trial.insert_latency.p99_ns);
            REQUIRE(trial.insert_latency.p99_ns <= trial.insert_latency.max_ns);
            REQUIRE(trial.insert_latency.p50_ns > 0.0); // No 0 ns p50 latency allowed

            REQUIRE(trial.lookup_latency.count == 5);
            REQUIRE(trial.lookup_latency.min_ns <= trial.lookup_latency.p50_ns);
            REQUIRE(trial.lookup_latency.p50_ns <= trial.lookup_latency.p95_ns);
            REQUIRE(trial.lookup_latency.p95_ns <= trial.lookup_latency.p99_ns);
            REQUIRE(trial.lookup_latency.p99_ns <= trial.lookup_latency.max_ns);
            REQUIRE(trial.lookup_latency.p50_ns > 0.0); // No 0 ns p50 latency allowed

            REQUIRE(trial.overall_latency.p50_ns > 0.0);

            REQUIRE(trial.memory_usage_bytes > 0);
            REQUIRE(trial.capacity > 0);
            REQUIRE(trial.num_elements <= 4);
            REQUIRE(trial.load_factor >= 0.0);
        }
    }
}

TEST_CASE("BenchmarkEngine - Nested Scoped Trace Execution & Oracle Agreement", "[benchmark_engine]") {
    std::string filepath = "workloads/traces/sample_lexical.trace";

    BenchmarkConfigOptions options;
    options.algorithms = {"chaining", "cuckoo", "hopscotch", "svc_hash"};
    options.repetitions = 2;
    options.warmup_trials = 1;
    options.scoped_baselines_on_nested = true;

    auto result = BenchmarkEngine::benchmarkTrace(filepath, options);

    REQUIRE(result.is_nested_scope);
    REQUIRE(result.total_trace_commands == 23);

    // All implementations (wrapped baselines + native SVC-Hash) must match Oracle outcomes:
    // 10 successful lookups, 2 failed lookups
    for (const auto& pair : result.algorithm_summaries) {
        const auto& s = pair.second;
        REQUIRE(s.successful_references == 10);
        REQUIRE(s.failed_references == 2);
        REQUIRE(s.mean_throughput_ops_sec > 0.0);

        for (const auto& trial : s.trials) {
            // Peak metrics must be preserved even after all nested scopes (and scope 0) have exited
            REQUIRE(trial.load_factor > 0.0);
            REQUIRE(trial.capacity > 0);
            REQUIRE(trial.num_elements > 0);
            REQUIRE(trial.memory_usage_bytes > sizeof(void*));
            REQUIRE(trial.insert_latency.p50_ns > 0.0);
            REQUIRE(trial.lookup_latency.p50_ns > 0.0);
        }
    }
}

TEST_CASE("BenchmarkEngine - JSON and CSV Export Validation", "[benchmark_engine]") {
    std::string flat_trace =
        "ENTER_SCOPE 0\n"
        "DECLARE x 1 0\n"
        "REFERENCE x 0\n"
        "EXIT_SCOPE 0\n";

    BenchmarkConfigOptions options;
    options.algorithms = {"chaining", "svc_hash"};
    options.repetitions = 2;
    options.warmup_trials = 0;

    auto res = BenchmarkEngine::benchmarkTraceString(flat_trace, "export_test", options);
    std::vector<TraceBenchmarkRunResult> run_list = {res};

    std::string json_path = "results/test_export.json";
    std::string csv_path = "results/test_export.csv";

    BenchmarkEngine::exportToJson(json_path, run_list);
    BenchmarkEngine::exportToCsv(csv_path, run_list);

    // Verify JSON file
    std::ifstream jf(json_path);
    REQUIRE(jf.is_open());
    nlohmann::json parsed_json;
    jf >> parsed_json;
    REQUIRE(parsed_json.contains("benchmark_version"));
    REQUIRE(parsed_json.contains("runs"));
    REQUIRE(parsed_json["runs"].size() == 1);
    REQUIRE(parsed_json["runs"][0]["algorithms"].contains("chaining"));
    REQUIRE(parsed_json["runs"][0]["algorithms"].contains("svc_hash"));
    jf.close();

    // Verify CSV file
    std::ifstream cf(csv_path);
    REQUIRE(cf.is_open());
    std::string header;
    std::getline(cf, header);
    REQUIRE(header.find("algorithm_name") != std::string::npos);
    REQUIRE(header.find("throughput_ops_sec") != std::string::npos);
    REQUIRE(header.find("insert_p50_ns") != std::string::npos);
    REQUIRE(header.find("lookup_p50_ns") != std::string::npos);

    // Must have at least 4 data rows (2 algorithms x 2 repetitions)
    size_t row_count = 0;
    std::string row;
    while (std::getline(cf, row)) {
        if (!row.empty()) {
            row_count++;
        }
    }
    REQUIRE(row_count == 4);
    cf.close();

    // Clean up test files
    std::remove(json_path.c_str());
    std::remove(csv_path.c_str());
}

TEST_CASE("HighPrecisionTimer - Monotonicity and Empirical Resolution", "[timer]") {
    REQUIRE(HighPrecisionTimer::getFrequency() > 0.0);
    uint64_t t1 = HighPrecisionTimer::nowTicks();
    uint64_t t2 = HighPrecisionTimer::nowTicks();
    REQUIRE(t2 >= t1);

    double empirical_res_ns = HighPrecisionTimer::measureEmpiricalResolutionNs();
    REQUIRE(empirical_res_ns > 0.0);
    REQUIRE(empirical_res_ns < 1000000.0); // Must be sub-millisecond
}

TEST_CASE("ScopedTableWrapper - Peak Metrics Preservation After Scope Exits", "[scoped_wrapper]") {
    ScopedTableWrapper<ChainingHashTable> wrapper(16);

    wrapper.enterScope(0, 0);
    wrapper.insert("global_var", SymbolValue{1, 10, ""}, 0);

    wrapper.enterScope(1, 0);
    wrapper.insert("local_1", SymbolValue{2, 20, ""}, 1);
    wrapper.insert("local_2", SymbolValue{3, 30, ""}, 1);

    // Peak elements should be 3
    TableMetrics mid_metrics = wrapper.getMetrics();
    REQUIRE(mid_metrics.num_elements == 3);
    REQUIRE(mid_metrics.load_factor > 0.0);
    double peak_lf_mid = mid_metrics.custom_metrics["peak_load_factor"];
    REQUIRE(peak_lf_mid > 0.0);

    // Exit scope 1
    wrapper.exitScope(1);

    // Active elements is now 1, but peak elements is 3
    TableMetrics post_exit1 = wrapper.getMetrics();
    REQUIRE(post_exit1.custom_metrics["peak_elements"] == 3.0);
    REQUIRE(post_exit1.custom_metrics["peak_load_factor"] >= peak_lf_mid);

    // Exit scope 0 (all tables destroyed)
    wrapper.exitScope(0);

    // After all scopes exit, metrics should report peak values rather than 0
    TableMetrics post_exit0 = wrapper.getMetrics();
    REQUIRE(post_exit0.num_elements == 3); // Reports peak elements
    REQUIRE(post_exit0.capacity > 0);     // Reports peak capacity
    REQUIRE(post_exit0.load_factor > 0.0); // Meaningful peak load factor
    REQUIRE(post_exit0.memory_usage_bytes > sizeof(void*)); // Meaningful peak memory
}
