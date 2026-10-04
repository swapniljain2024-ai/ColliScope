#include "benchmark_engine.hpp"
#include "benchmark_timer.hpp"

#include <chrono>
#include <fstream>
#include <stdexcept>
#include <algorithm>
#include <cmath>

namespace colliscope {

std::unique_ptr<ISymbolTable> BenchmarkEngine::createTable(
    const std::string& algorithm_name,
    bool is_nested_trace,
    bool use_scoped_wrapper,
    size_t initial_capacity
) {
    std::string name = algorithm_name;
    std::transform(name.begin(), name.end(), name.begin(), ::tolower);

    if (name == "chaining" || name == "separate_chaining") {
        if (is_nested_trace && use_scoped_wrapper) {
            return std::make_unique<ScopedTableWrapper<ChainingHashTable>>(initial_capacity);
        }
        return std::make_unique<ChainingHashTable>(initial_capacity);
    } else if (name == "cuckoo" || name == "cuckoo_hashing") {
        if (is_nested_trace && use_scoped_wrapper) {
            return std::make_unique<ScopedTableWrapper<CuckooHashTable>>(initial_capacity);
        }
        return std::make_unique<CuckooHashTable>(initial_capacity);
    } else if (name == "hopscotch" || name == "hopscotch_hashing") {
        size_t hop_cap = std::max<size_t>(32, initial_capacity);
        if (is_nested_trace && use_scoped_wrapper) {
            return std::make_unique<ScopedTableWrapper<HopscotchHashTable>>(hop_cap);
        }
        return std::make_unique<HopscotchHashTable>(hop_cap);
    } else if (name == "svc_hash" || name == "svc") {
        return std::make_unique<SvcHashTable>(initial_capacity);
    } else if (name == "scoped_chaining") {
        return std::make_unique<ScopedTableWrapper<ChainingHashTable>>(initial_capacity);
    } else if (name == "scoped_cuckoo") {
        return std::make_unique<ScopedTableWrapper<CuckooHashTable>>(initial_capacity);
    } else if (name == "scoped_hopscotch") {
        return std::make_unique<ScopedTableWrapper<HopscotchHashTable>>(std::max<size_t>(32, initial_capacity));
    }

    throw std::invalid_argument("Unknown algorithm: " + algorithm_name);
}

BenchmarkTrialResult BenchmarkEngine::runTrial(
    const std::vector<TraceCommand>& commands,
    ISymbolTable& table,
    const std::string& trace_name,
    uint32_t trial_index,
    bool is_warmup
) {
    table.setTimingEnabled(false);

    BenchmarkTrialResult trial;
    trial.algorithm_name = table.getAlgorithmName();
    trial.trace_name = trace_name;
    trial.trial_index = trial_index;
    trial.is_warmup = is_warmup;

    if (commands.empty()) {
        return trial;
    }

    // 1. External Wall-Clock Measurement via HighPrecisionTimer (QPC monotonic clock)
    // For fast micro-traces (< 100 ticks), loop trace execution to amortize timer quantization error.
    uint64_t accumulated_wall_ticks = 0;
    size_t wall_iterations = 0;

    while (accumulated_wall_ticks < 100 && wall_iterations < 1000) {
        table.reset();
        std::vector<uint32_t> temp_stack = {0};
        uint64_t t0 = HighPrecisionTimer::nowTicks();
        for (const auto& cmd : commands) {
            uint32_t curr = temp_stack.empty() ? 0 : temp_stack.back();
            switch (cmd.op) {
                case TraceOp::ENTER_SCOPE: {
                    uint32_t parent = cmd.parent_scope_id.value_or(curr);
                    table.enterScope(cmd.scope_id, parent);
                    temp_stack.push_back(cmd.scope_id);
                    break;
                }
                case TraceOp::EXIT_SCOPE: {
                    table.exitScope(cmd.scope_id);
                    if (!temp_stack.empty() && temp_stack.back() == cmd.scope_id) {
                        temp_stack.pop_back();
                    }
                    break;
                }
                case TraceOp::DECLARE: {
                    uint32_t target = cmd.has_explicit_scope ? cmd.scope_id : curr;
                    table.insert(cmd.identifier, SymbolValue{cmd.type_id, cmd.line_number, ""}, target);
                    break;
                }
                case TraceOp::REFERENCE: {
                    uint32_t target = cmd.has_explicit_scope ? cmd.scope_id : curr;
                    table.lookup(cmd.identifier, target);
                    break;
                }
            }
        }
        uint64_t t1 = HighPrecisionTimer::nowTicks();
        accumulated_wall_ticks += (t1 - t0);
        wall_iterations++;
        if (accumulated_wall_ticks >= 100) break;
    }

    double total_wall_ns = (accumulated_wall_ticks > 0 && wall_iterations > 0)
        ? (HighPrecisionTimer::ticksToNanoseconds(accumulated_wall_ticks) / static_cast<double>(wall_iterations))
        : HighPrecisionTimer::measureEmpiricalResolutionNs();

    trial.total_time_ns = static_cast<uint64_t>(std::round(total_wall_ns));
    if (trial.total_time_ns == 0) {
        trial.total_time_ns = static_cast<uint64_t>(std::ceil(HighPrecisionTimer::measureEmpiricalResolutionNs()));
    }

    // 2. Instrumented Pass with Run-Based Batched Latency Sampling
    // Measures amortized batch latency per operation. Consecutive homogeneous operations are
    // grouped into batches (up to MAX_BATCH_SIZE = 16) and sub-tick batches (< 100 ns) are
    // calibrated via post-trial amortization across verified wall time. These values represent
    // amortized batch latency per operation, not individually measured per-operation hardware latency.
    table.reset();
    std::vector<uint32_t> scope_stack = {0};

    std::vector<double> insert_latencies;
    std::vector<double> lookup_latencies;
    std::vector<double> all_latencies;

    insert_latencies.reserve(commands.size());
    lookup_latencies.reserve(commands.size());
    all_latencies.reserve(commands.size());

    const size_t MAX_BATCH_SIZE = 16;
    size_t i = 0;

    std::vector<size_t> zero_tick_insert_indices;
    std::vector<size_t> zero_tick_lookup_indices;
    std::vector<size_t> zero_tick_all_indices;

    double total_measured_insert_ns = 0.0;
    double total_measured_lookup_ns = 0.0;
    double total_measured_scope_ns = 0.0;

    while (i < commands.size()) {
        const auto& first_cmd = commands[i];
        TraceOp current_op = first_cmd.op;

        // Group consecutive commands of the same op type up to MAX_BATCH_SIZE
        size_t batch_end = i;
        while (batch_end < commands.size() &&
               commands[batch_end].op == current_op &&
               (batch_end - i) < MAX_BATCH_SIZE) {
            batch_end++;
        }
        size_t batch_size = batch_end - i;

        uint64_t t0 = HighPrecisionTimer::nowTicks();

        for (size_t b = i; b < batch_end; ++b) {
            const auto& cmd = commands[b];
            trial.total_operations++;
            uint32_t current_scope = scope_stack.empty() ? 0 : scope_stack.back();

            switch (cmd.op) {
                case TraceOp::ENTER_SCOPE: {
                    trial.enter_scope_count++;
                    uint32_t effective_parent = cmd.parent_scope_id.value_or(current_scope);
                    table.enterScope(cmd.scope_id, effective_parent);
                    scope_stack.push_back(cmd.scope_id);
                    break;
                }
                case TraceOp::EXIT_SCOPE: {
                    trial.exit_scope_count++;
                    table.exitScope(cmd.scope_id);
                    if (!scope_stack.empty() && scope_stack.back() == cmd.scope_id) {
                        scope_stack.pop_back();
                    }
                    break;
                }
                case TraceOp::DECLARE: {
                    trial.insert_count++;
                    uint32_t target_scope = cmd.has_explicit_scope ? cmd.scope_id : current_scope;
                    SymbolValue val{cmd.type_id, cmd.line_number, ""};
                    table.insert(cmd.identifier, val, target_scope);
                    break;
                }
                case TraceOp::REFERENCE: {
                    trial.lookup_count++;
                    uint32_t target_scope = cmd.has_explicit_scope ? cmd.scope_id : current_scope;
                    auto res = table.lookup(cmd.identifier, target_scope);
                    if (res.has_value()) {
                        trial.successful_references++;
                    } else {
                        trial.failed_references++;
                    }
                    break;
                }
            }
        }

        uint64_t t1 = HighPrecisionTimer::nowTicks();
        uint64_t batch_ticks = t1 - t0;

        if (batch_ticks > 0) {
            double batch_ns = HighPrecisionTimer::ticksToNanoseconds(batch_ticks);
            double per_op_ns = batch_ns / static_cast<double>(batch_size);

            if (current_op == TraceOp::DECLARE) {
                total_measured_insert_ns += batch_ns;
                for (size_t k = 0; k < batch_size; ++k) {
                    insert_latencies.push_back(per_op_ns);
                    all_latencies.push_back(per_op_ns);
                }
            } else if (current_op == TraceOp::REFERENCE) {
                total_measured_lookup_ns += batch_ns;
                for (size_t k = 0; k < batch_size; ++k) {
                    lookup_latencies.push_back(per_op_ns);
                    all_latencies.push_back(per_op_ns);
                }
            } else {
                total_measured_scope_ns += batch_ns;
                for (size_t k = 0; k < batch_size; ++k) {
                    all_latencies.push_back(per_op_ns);
                }
            }
        } else {
            // Sub-tick batch (< 100 ns). Queue for post-trial amortized calibration.
            if (current_op == TraceOp::DECLARE) {
                for (size_t k = 0; k < batch_size; ++k) {
                    zero_tick_insert_indices.push_back(insert_latencies.size());
                    insert_latencies.push_back(0.0);
                    zero_tick_all_indices.push_back(all_latencies.size());
                    all_latencies.push_back(0.0);
                }
            } else if (current_op == TraceOp::REFERENCE) {
                for (size_t k = 0; k < batch_size; ++k) {
                    zero_tick_lookup_indices.push_back(lookup_latencies.size());
                    lookup_latencies.push_back(0.0);
                    zero_tick_all_indices.push_back(all_latencies.size());
                    all_latencies.push_back(0.0);
                }
            } else {
                for (size_t k = 0; k < batch_size; ++k) {
                    zero_tick_all_indices.push_back(all_latencies.size());
                    all_latencies.push_back(0.0);
                }
            }
        }

        i = batch_end;
    }

    // Post-trial amortized calibration for sub-tick operations to yield amortized batch latency per operation
    double mean_trial_op_ns = (trial.total_operations > 0)
        ? (total_wall_ns / static_cast<double>(trial.total_operations))
        : HighPrecisionTimer::measureEmpiricalResolutionNs();

    double insert_fallback_ns = (insert_latencies.size() > zero_tick_insert_indices.size())
        ? (total_measured_insert_ns / static_cast<double>(insert_latencies.size() - zero_tick_insert_indices.size()))
        : mean_trial_op_ns;

    double lookup_fallback_ns = (lookup_latencies.size() > zero_tick_lookup_indices.size())
        ? (total_measured_lookup_ns / static_cast<double>(lookup_latencies.size() - zero_tick_lookup_indices.size()))
        : mean_trial_op_ns;

    for (size_t idx : zero_tick_insert_indices) {
        insert_latencies[idx] = insert_fallback_ns;
    }
    for (size_t idx : zero_tick_lookup_indices) {
        lookup_latencies[idx] = lookup_fallback_ns;
    }
    for (size_t idx : zero_tick_all_indices) {
        if (all_latencies[idx] == 0.0) {
            all_latencies[idx] = mean_trial_op_ns;
        }
    }

    trial.insert_time_ns = static_cast<uint64_t>(std::round(total_measured_insert_ns + zero_tick_insert_indices.size() * insert_fallback_ns));
    trial.lookup_time_ns = static_cast<uint64_t>(std::round(total_measured_lookup_ns + zero_tick_lookup_indices.size() * lookup_fallback_ns));
    trial.scope_exit_time_ns = static_cast<uint64_t>(std::round(total_measured_scope_ns));

    if (trial.total_time_ns > 0) {
        trial.throughput_ops_sec = (static_cast<double>(trial.total_operations) / static_cast<double>(trial.total_time_ns)) * 1e9;
    }

    // Compute distribution percentiles
    trial.insert_latency = LatencySummary::compute(insert_latencies);
    trial.lookup_latency = LatencySummary::compute(lookup_latencies);
    trial.overall_latency = LatencySummary::compute(all_latencies);

    // Retrieve implementation-appropriate metrics
    TableMetrics final_m = table.getMetrics();
    trial.memory_usage_bytes = final_m.memory_usage_bytes;
    trial.load_factor = final_m.load_factor;
    trial.capacity = final_m.capacity;
    trial.num_elements = final_m.num_elements;
    trial.collision_count = final_m.collision_count;
    trial.custom_metrics = final_m.custom_metrics;

    return trial;
}

TraceBenchmarkRunResult BenchmarkEngine::benchmarkTrace(
    const std::string& trace_filepath,
    const BenchmarkConfigOptions& options
) {
    auto commands = TraceParser::parseFile(trace_filepath);
    std::string basename = trace_filepath;
    size_t last_slash = trace_filepath.find_last_of("/\\");
    if (last_slash != std::string::npos) {
        basename = trace_filepath.substr(last_slash + 1);
    }

    TraceBenchmarkRunResult run_res;
    run_res.trace_file = basename;
    run_res.total_trace_commands = commands.size();

    // Check if trace exercises nested scopes
    bool is_nested = false;
    for (const auto& cmd : commands) {
        if (cmd.op == TraceOp::ENTER_SCOPE && cmd.scope_id > 0) {
            is_nested = true;
            break;
        }
    }
    run_res.is_nested_scope = is_nested;

    for (const auto& alg_name : options.algorithms) {
        auto table = createTable(
            alg_name,
            is_nested,
            options.scoped_baselines_on_nested,
            options.initial_capacity
        );

        // Warmup runs
        for (size_t w = 0; w < options.warmup_trials; ++w) {
            runTrial(commands, *table, basename, static_cast<uint32_t>(w), true);
        }

        // Timed repetitions
        std::vector<BenchmarkTrialResult> alg_trials;
        alg_trials.reserve(options.repetitions);

        for (size_t r = 0; r < options.repetitions; ++r) {
            auto trial = runTrial(commands, *table, basename, static_cast<uint32_t>(r + 1), false);
            alg_trials.push_back(trial);
            run_res.all_trials.push_back(trial);
        }

        auto summary = AlgorithmBenchmarkSummary::aggregate(alg_trials);
        run_res.algorithm_summaries[summary.algorithm_name] = summary;
    }

    return run_res;
}

TraceBenchmarkRunResult BenchmarkEngine::benchmarkTraceString(
    const std::string& trace_content,
    const std::string& trace_name,
    const BenchmarkConfigOptions& options
) {
    auto commands = TraceParser::parseString(trace_content);

    TraceBenchmarkRunResult run_res;
    run_res.trace_file = trace_name;
    run_res.total_trace_commands = commands.size();

    bool is_nested = false;
    for (const auto& cmd : commands) {
        if (cmd.op == TraceOp::ENTER_SCOPE && cmd.scope_id > 0) {
            is_nested = true;
            break;
        }
    }
    run_res.is_nested_scope = is_nested;

    for (const auto& alg_name : options.algorithms) {
        auto table = createTable(
            alg_name,
            is_nested,
            options.scoped_baselines_on_nested,
            options.initial_capacity
        );

        for (size_t w = 0; w < options.warmup_trials; ++w) {
            runTrial(commands, *table, trace_name, static_cast<uint32_t>(w), true);
        }

        std::vector<BenchmarkTrialResult> alg_trials;
        alg_trials.reserve(options.repetitions);

        for (size_t r = 0; r < options.repetitions; ++r) {
            auto trial = runTrial(commands, *table, trace_name, static_cast<uint32_t>(r + 1), false);
            alg_trials.push_back(trial);
            run_res.all_trials.push_back(trial);
        }

        auto summary = AlgorithmBenchmarkSummary::aggregate(alg_trials);
        run_res.algorithm_summaries[summary.algorithm_name] = summary;
    }

    return run_res;
}

void BenchmarkEngine::exportToJson(
    const std::string& filepath,
    const std::vector<TraceBenchmarkRunResult>& results
) {
    nlohmann::json root;
    root["benchmark_version"] = "1.0.0";
    root["latency_measurement_methodology"] = "amortized batch latency per operation";
    root["total_runs"] = results.size();

    nlohmann::json runs_arr = nlohmann::json::array();
    for (const auto& res : results) {
        runs_arr.push_back(res.toJson());
    }
    root["runs"] = runs_arr;

    std::ofstream ofs(filepath);
    if (!ofs.is_open()) {
        throw std::runtime_error("Cannot open JSON output file: " + filepath);
    }
    ofs << root.dump(2);
}

void BenchmarkEngine::exportToCsv(
    const std::string& filepath,
    const std::vector<TraceBenchmarkRunResult>& results
) {
    std::ofstream ofs(filepath);
    if (!ofs.is_open()) {
        throw std::runtime_error("Cannot open CSV output file: " + filepath);
    }

    ofs << BenchmarkTrialResult::csvHeader() << "\n";
    for (const auto& res : results) {
        for (const auto& trial : res.all_trials) {
            ofs << trial.toCsvRow() << "\n";
        }
    }
}

} // namespace colliscope
