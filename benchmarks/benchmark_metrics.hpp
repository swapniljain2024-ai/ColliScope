#pragma once

#include <string>
#include <vector>
#include <map>
#include <cmath>
#include <algorithm>
#include <numeric>
#include <sstream>
#include <iomanip>
#include <cstdint>

#include "common/third_party/json.hpp"
#include "common/metrics.hpp"

namespace colliscope {

/**
 * Summary of amortized batch latency per operation distribution (nanoseconds).
 *
 * Methodological note:
 * Operations with execution durations below timer granularity (< 100 ns on 10 MHz QPC)
 * are sampled via run-based batches (up to 16 consecutive homogeneous operations) and calibrated
 * with post-trial amortization across verified wall time. These statistics represent
 * amortized batch latency per operation, not individually measured per-operation hardware latency.
 */
struct LatencySummary {
    uint64_t count{0};
    double min_ns{0.0};
    double mean_ns{0.0};
    double p50_ns{0.0};
    double p95_ns{0.0};
    double p99_ns{0.0};
    double max_ns{0.0};
    double stddev_ns{0.0};

    nlohmann::json toJson() const {
        nlohmann::json j;
        j["measurement_type"] = "amortized batch latency per operation";
        j["count"] = count;
        j["min_ns"] = min_ns;
        j["mean_ns"] = mean_ns;
        j["p50_ns"] = p50_ns;
        j["p95_ns"] = p95_ns;
        j["p99_ns"] = p99_ns;
        j["max_ns"] = max_ns;
        j["stddev_ns"] = stddev_ns;
        return j;
    }

    template <typename T>
    static LatencySummary compute(std::vector<T>& latencies_ns) {
        LatencySummary s;
        s.count = latencies_ns.size();
        if (latencies_ns.empty()) {
            return s;
        }

        std::sort(latencies_ns.begin(), latencies_ns.end());

        s.min_ns = static_cast<double>(latencies_ns.front());
        s.max_ns = static_cast<double>(latencies_ns.back());

        double sum = 0.0;
        for (const auto& val : latencies_ns) {
            sum += static_cast<double>(val);
        }
        s.mean_ns = sum / static_cast<double>(s.count);

        double variance_sum = 0.0;
        for (const auto& val : latencies_ns) {
            double diff = static_cast<double>(val) - s.mean_ns;
            variance_sum += diff * diff;
        }
        s.stddev_ns = (s.count > 1) ? std::sqrt(variance_sum / static_cast<double>(s.count - 1)) : 0.0;

        auto get_percentile = [&](double p) -> double {
            if (latencies_ns.empty()) return 0.0;
            double rank = (p / 100.0) * static_cast<double>(latencies_ns.size() - 1);
            size_t low = static_cast<size_t>(std::floor(rank));
            size_t high = static_cast<size_t>(std::ceil(rank));
            if (low == high || high >= latencies_ns.size() || latencies_ns[low] == latencies_ns[high]) {
                return static_cast<double>(latencies_ns[low]);
            }
            double weight = rank - static_cast<double>(low);
            return static_cast<double>(latencies_ns[low]) * (1.0 - weight) +
                   static_cast<double>(latencies_ns[high]) * weight;
        };

        s.p50_ns = get_percentile(50.0);
        s.p95_ns = std::max(s.p50_ns, get_percentile(95.0));
        s.p99_ns = std::max(s.p95_ns, get_percentile(99.0));

        return s;
    }
};

struct BenchmarkTrialResult {
    std::string algorithm_name{"unknown"};
    std::string trace_name{"unknown"};
    uint32_t trial_index{0};
    uint32_t execution_order{0};
    bool is_warmup{false};

    // Workload / manifest classification metadata
    std::string category{""};
    std::string identifier_distribution{""};
    std::string scope_mode{""};
    std::string workload_type{""};
    std::string replicate{""};
    int64_t seed{-1};
    std::string source_type{""};

    // Operation counts
    uint64_t total_operations{0};
    uint64_t insert_count{0};
    uint64_t lookup_count{0};
    uint64_t enter_scope_count{0};
    uint64_t exit_scope_count{0};
    uint64_t successful_references{0};
    uint64_t failed_references{0};

    // Timings & Throughput
    uint64_t total_time_ns{0};
    uint64_t insert_time_ns{0};
    uint64_t lookup_time_ns{0};
    uint64_t scope_exit_time_ns{0};
    double throughput_ops_sec{0.0};

    // Latency distributions
    LatencySummary insert_latency;
    LatencySummary lookup_latency;
    LatencySummary overall_latency;

    // Memory & Capacity
    uint64_t memory_usage_bytes{0};
    double load_factor{0.0};
    uint64_t capacity{0};
    uint64_t num_elements{0};

    // Collision & algorithm-specific metrics
    uint64_t collision_count{0};
    std::map<std::string, double> custom_metrics;

    nlohmann::json toJson() const {
        nlohmann::json j;
        j["algorithm_name"] = algorithm_name;
        j["trace_name"] = trace_name;
        j["trial_index"] = trial_index;
        j["execution_order"] = execution_order;
        j["is_warmup"] = is_warmup;
        j["category"] = category;
        j["identifier_distribution"] = identifier_distribution;
        j["scope_mode"] = scope_mode;
        j["workload_type"] = workload_type;
        j["replicate"] = replicate;
        j["seed"] = seed;
        j["source_type"] = source_type;
        j["total_operations"] = total_operations;
        j["insert_count"] = insert_count;
        j["lookup_count"] = lookup_count;
        j["enter_scope_count"] = enter_scope_count;
        j["exit_scope_count"] = exit_scope_count;
        j["successful_references"] = successful_references;
        j["failed_references"] = failed_references;
        j["total_time_ns"] = total_time_ns;
        j["insert_time_ns"] = insert_time_ns;
        j["lookup_time_ns"] = lookup_time_ns;
        j["scope_exit_time_ns"] = scope_exit_time_ns;
        j["throughput_ops_sec"] = throughput_ops_sec;
        j["insert_latency"] = insert_latency.toJson();
        j["lookup_latency"] = lookup_latency.toJson();
        j["overall_latency"] = overall_latency.toJson();
        j["memory_usage_bytes"] = memory_usage_bytes;
        j["load_factor"] = load_factor;
        j["capacity"] = capacity;
        j["num_elements"] = num_elements;
        j["collision_count"] = collision_count;
        j["custom_metrics"] = custom_metrics;
        return j;
    }

    static std::string csvHeader() {
        return "trace_name,category,identifier_distribution,scope_mode,workload_type,replicate,seed,source_type,"
               "algorithm_name,trial_index,execution_order,is_warmup,total_operations,insert_count,lookup_count,"
               "enter_scope_count,exit_scope_count,successful_references,failed_references,total_time_ns,"
               "insert_time_ns,lookup_time_ns,scope_exit_time_ns,throughput_ops_sec,insert_p50_ns,insert_p95_ns,"
               "insert_p99_ns,lookup_p50_ns,lookup_p95_ns,lookup_p99_ns,memory_usage_bytes,load_factor,capacity,"
               "num_elements,collision_count";
    }

    std::string toCsvRow() const {
        std::ostringstream oss;
        oss << trace_name << ","
            << category << ","
            << identifier_distribution << ","
            << scope_mode << ","
            << workload_type << ","
            << replicate << ","
            << seed << ","
            << source_type << ","
            << algorithm_name << ","
            << trial_index << ","
            << execution_order << ","
            << (is_warmup ? "true" : "false") << ","
            << total_operations << ","
            << insert_count << ","
            << lookup_count << ","
            << enter_scope_count << ","
            << exit_scope_count << ","
            << successful_references << ","
            << failed_references << ","
            << total_time_ns << ","
            << insert_time_ns << ","
            << lookup_time_ns << ","
            << scope_exit_time_ns << ","
            << std::fixed << std::setprecision(2) << throughput_ops_sec << ","
            << std::fixed << std::setprecision(1) << insert_latency.p50_ns << ","
            << std::fixed << std::setprecision(1) << insert_latency.p95_ns << ","
            << std::fixed << std::setprecision(1) << insert_latency.p99_ns << ","
            << std::fixed << std::setprecision(1) << lookup_latency.p50_ns << ","
            << std::fixed << std::setprecision(1) << lookup_latency.p95_ns << ","
            << std::fixed << std::setprecision(1) << lookup_latency.p99_ns << ","
            << memory_usage_bytes << ","
            << std::fixed << std::setprecision(4) << load_factor << ","
            << capacity << ","
            << num_elements << ","
            << collision_count;
        return oss.str();
    }
};

struct AlgorithmBenchmarkSummary {
    std::string algorithm_name;
    std::string trace_name;
    uint32_t repetitions{0};

    double mean_throughput_ops_sec{0.0};
    double stddev_throughput_ops_sec{0.0};

    double mean_insert_time_ns{0.0};
    double mean_lookup_time_ns{0.0};
    double mean_total_time_ns{0.0};

    double mean_insert_p50_ns{0.0};
    double mean_insert_p95_ns{0.0};
    double mean_insert_p99_ns{0.0};

    double mean_lookup_p50_ns{0.0};
    double mean_lookup_p95_ns{0.0};
    double mean_lookup_p99_ns{0.0};

    uint64_t memory_usage_bytes{0};
    double final_load_factor{0.0};
    uint64_t successful_references{0};
    uint64_t failed_references{0};

    std::vector<BenchmarkTrialResult> trials;
    std::map<std::string, double> average_custom_metrics;

    nlohmann::json toJson() const {
        nlohmann::json j;
        j["algorithm_name"] = algorithm_name;
        j["trace_name"] = trace_name;
        j["repetitions"] = repetitions;
        j["mean_throughput_ops_sec"] = mean_throughput_ops_sec;
        j["stddev_throughput_ops_sec"] = stddev_throughput_ops_sec;
        j["mean_insert_time_ns"] = mean_insert_time_ns;
        j["mean_lookup_time_ns"] = mean_lookup_time_ns;
        j["mean_total_time_ns"] = mean_total_time_ns;
        j["mean_insert_p50_ns"] = mean_insert_p50_ns;
        j["mean_insert_p95_ns"] = mean_insert_p95_ns;
        j["mean_insert_p99_ns"] = mean_insert_p99_ns;
        j["mean_lookup_p50_ns"] = mean_lookup_p50_ns;
        j["mean_lookup_p95_ns"] = mean_lookup_p95_ns;
        j["mean_lookup_p99_ns"] = mean_lookup_p99_ns;
        j["memory_usage_bytes"] = memory_usage_bytes;
        j["final_load_factor"] = final_load_factor;
        j["successful_references"] = successful_references;
        j["failed_references"] = failed_references;
        j["average_custom_metrics"] = average_custom_metrics;

        nlohmann::json trial_list = nlohmann::json::array();
        for (const auto& t : trials) {
            trial_list.push_back(t.toJson());
        }
        j["trials"] = trial_list;
        return j;
    }

    static AlgorithmBenchmarkSummary aggregate(const std::vector<BenchmarkTrialResult>& trial_results) {
        AlgorithmBenchmarkSummary s;
        if (trial_results.empty()) return s;

        s.algorithm_name = trial_results.front().algorithm_name;
        s.trace_name = trial_results.front().trace_name;
        s.repetitions = static_cast<uint32_t>(trial_results.size());
        s.trials = trial_results;

        double sum_tp = 0.0, sum_insert_time = 0.0, sum_lookup_time = 0.0, sum_total_time = 0.0;
        double sum_ins_p50 = 0.0, sum_ins_p95 = 0.0, sum_ins_p99 = 0.0;
        double sum_look_p50 = 0.0, sum_look_p95 = 0.0, sum_look_p99 = 0.0;
        std::map<std::string, double> custom_sums;

        for (const auto& t : trial_results) {
            sum_tp += t.throughput_ops_sec;
            sum_insert_time += static_cast<double>(t.insert_time_ns);
            sum_lookup_time += static_cast<double>(t.lookup_time_ns);
            sum_total_time += static_cast<double>(t.total_time_ns);

            sum_ins_p50 += t.insert_latency.p50_ns;
            sum_ins_p95 += t.insert_latency.p95_ns;
            sum_ins_p99 += t.insert_latency.p99_ns;

            sum_look_p50 += t.lookup_latency.p50_ns;
            sum_look_p95 += t.lookup_latency.p95_ns;
            sum_look_p99 += t.lookup_latency.p99_ns;

            for (const auto& cm : t.custom_metrics) {
                custom_sums[cm.first] += cm.second;
            }
        }

        double n = static_cast<double>(s.repetitions);
        s.mean_throughput_ops_sec = sum_tp / n;
        s.mean_insert_time_ns = sum_insert_time / n;
        s.mean_lookup_time_ns = sum_lookup_time / n;
        s.mean_total_time_ns = sum_total_time / n;

        s.mean_insert_p50_ns = sum_ins_p50 / n;
        s.mean_insert_p95_ns = sum_ins_p95 / n;
        s.mean_insert_p99_ns = sum_ins_p99 / n;

        s.mean_lookup_p50_ns = sum_look_p50 / n;
        s.mean_lookup_p95_ns = sum_look_p95 / n;
        s.mean_lookup_p99_ns = sum_look_p99 / n;

        // Sample standard deviation for throughput
        double var_sum = 0.0;
        for (const auto& t : trial_results) {
            double diff = t.throughput_ops_sec - s.mean_throughput_ops_sec;
            var_sum += diff * diff;
        }
        s.stddev_throughput_ops_sec = (s.repetitions > 1) ? std::sqrt(var_sum / (n - 1.0)) : 0.0;

        // Take last trial's deterministic state metrics
        const auto& last = trial_results.back();
        s.memory_usage_bytes = last.memory_usage_bytes;
        s.final_load_factor = last.load_factor;
        s.successful_references = last.successful_references;
        s.failed_references = last.failed_references;

        for (const auto& pair : custom_sums) {
            s.average_custom_metrics[pair.first] = pair.second / n;
        }

        return s;
    }
};

} // namespace colliscope
