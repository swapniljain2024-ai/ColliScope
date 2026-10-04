#include <iostream>
#include <string>
#include <vector>
#include <sstream>
#include <fstream>
#include <iomanip>

#include "benchmark_engine.hpp"
#include "common/third_party/json.hpp"

using namespace colliscope;

void printUsage(const char* prog) {
    std::cout << "Usage: " << prog << " [options]\n\n"
              << "Options:\n"
              << "  --trace <path>            Single trace file to benchmark\n"
              << "  --manifest <path>         Path to manifest.json containing trace matrix\n"
              << "  --algorithms <list>       Comma-separated algorithms (chaining,cuckoo,hopscotch,svc_hash)\n"
              << "  --repetitions <N>         Repetitions per algorithm (default: 5)\n"
              << "  --warmup <N>              Warmup repetitions (default: 1)\n"
              << "  --output-json <path>      Export detailed results JSON\n"
              << "  --output-csv <path>       Export tabular results CSV\n"
              << "  --no-scoped-baselines     Disable ScopedTableWrapper for baselines on nested traces\n"
              << "  --help                    Show this help message\n";
}

std::vector<std::string> split(const std::string& str, char delim) {
    std::vector<std::string> tokens;
    std::stringstream ss(str);
    std::string token;
    while (std::getline(ss, token, delim)) {
        if (!token.empty()) {
            tokens.push_back(token);
        }
    }
    return tokens;
}

int main(int argc, char* argv[]) {
    std::string trace_file = "";
    std::string manifest_file = "";
    std::string alg_str = "chaining,cuckoo,hopscotch,svc_hash";
    size_t repetitions = 5;
    size_t warmup = 1;
    std::string output_json = "";
    std::string output_csv = "";
    bool scoped_baselines = true;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--trace" && i + 1 < argc) {
            trace_file = argv[++i];
        } else if (arg == "--manifest" && i + 1 < argc) {
            manifest_file = argv[++i];
        } else if (arg == "--algorithms" && i + 1 < argc) {
            alg_str = argv[++i];
        } else if (arg == "--repetitions" && i + 1 < argc) {
            repetitions = std::stoul(argv[++i]);
        } else if (arg == "--warmup" && i + 1 < argc) {
            warmup = std::stoul(argv[++i]);
        } else if (arg == "--output-json" && i + 1 < argc) {
            output_json = argv[++i];
        } else if (arg == "--output-csv" && i + 1 < argc) {
            output_csv = argv[++i];
        } else if (arg == "--no-scoped-baselines") {
            scoped_baselines = false;
        } else if (arg == "--help" || arg == "-h") {
            printUsage(argv[0]);
            return 0;
        } else {
            std::cerr << "Unknown argument: " << arg << "\n";
            printUsage(argv[0]);
            return 1;
        }
    }

    if (trace_file.empty() && manifest_file.empty()) {
        std::cerr << "Error: Must specify either --trace <path> or --manifest <path>\n";
        printUsage(argv[0]);
        return 1;
    }

    BenchmarkConfigOptions options;
    options.algorithms = split(alg_str, ',');
    options.repetitions = repetitions;
    options.warmup_trials = warmup;
    options.scoped_baselines_on_nested = scoped_baselines;

    std::vector<std::string> trace_paths;

    if (!trace_file.empty()) {
        trace_paths.push_back(trace_file);
    } else {
        std::ifstream mf(manifest_file);
        if (!mf.is_open()) {
            std::cerr << "Cannot open manifest file: " << manifest_file << "\n";
            return 1;
        }
        nlohmann::json mj;
        mf >> mj;
        std::string base_dir = manifest_file;
        size_t last_slash = base_dir.find_last_of("/\\");
        base_dir = (last_slash != std::string::npos) ? base_dir.substr(0, last_slash) : ".";

        for (const auto& entry : mj["traces"]) {
            std::string t_file = entry["trace_file"].get<std::string>();
            trace_paths.push_back(base_dir + "/" + t_file);
        }
    }

    std::cout << "=================================================================\n"
              << " ColliScope Benchmark Engine (Phase 6)\n"
              << " Replaying " << trace_paths.size() << " trace(s) across " << options.algorithms.size() << " algorithm(s)\n"
              << " Repetitions: " << options.repetitions << " (warmup: " << options.warmup_trials << ")\n"
              << " Scoped baselines on nested traces: " << (scoped_baselines ? "ENABLED" : "DISABLED") << "\n"
              << "=================================================================\n\n";

    std::vector<TraceBenchmarkRunResult> all_results;

    for (size_t t_idx = 0; t_idx < trace_paths.size(); ++t_idx) {
        const auto& path = trace_paths[t_idx];
        std::cout << "[" << (t_idx + 1) << "/" << trace_paths.size() << "] Benchmarking: " << path << " ...\n";

        try {
            auto run_res = BenchmarkEngine::benchmarkTrace(path, options);

            // Print summary table
            std::cout << "-----------------------------------------------------------------------------------------------------------------\n";
            std::cout << std::left << std::setw(20) << "Algorithm"
                      << std::right << std::setw(16) << "Throughput(op/s)"
                      << std::setw(14) << "Ins p50(ns)"
                      << std::setw(14) << "Look p50(ns)"
                      << std::setw(14) << "Ins p99(ns)"
                      << std::setw(14) << "Look p99(ns)"
                      << std::setw(12) << "Mem(KB)"
                      << std::setw(10) << "LoadFac"
                      << "\n";
            std::cout << "-----------------------------------------------------------------------------------------------------------------\n";

            for (const auto& pair : run_res.algorithm_summaries) {
                const auto& s = pair.second;
                std::cout << std::left << std::setw(20) << s.algorithm_name
                          << std::right << std::setw(16) << std::fixed << std::setprecision(0) << s.mean_throughput_ops_sec
                          << std::setw(14) << std::fixed << std::setprecision(1) << s.mean_insert_p50_ns
                          << std::setw(14) << std::fixed << std::setprecision(1) << s.mean_lookup_p50_ns
                          << std::setw(14) << std::fixed << std::setprecision(1) << s.mean_insert_p99_ns
                          << std::setw(14) << std::fixed << std::setprecision(1) << s.mean_lookup_p99_ns
                          << std::setw(12) << (s.memory_usage_bytes / 1024)
                          << std::setw(10) << std::fixed << std::setprecision(3) << s.final_load_factor
                          << "\n";
            }
            std::cout << "-----------------------------------------------------------------------------------------------------------------\n\n";

            all_results.push_back(run_res);
        } catch (const std::exception& ex) {
            std::cerr << "Error running benchmark on " << path << ": " << ex.what() << "\n";
            return 1;
        }
    }

    if (!output_json.empty()) {
        std::cout << "Exporting JSON results to: " << output_json << " ... ";
        BenchmarkEngine::exportToJson(output_json, all_results);
        std::cout << "Done.\n";
    }

    if (!output_csv.empty()) {
        std::cout << "Exporting CSV results to: " << output_csv << " ... ";
        BenchmarkEngine::exportToCsv(output_csv, all_results);
        std::cout << "Done.\n";
    }

    std::cout << "Benchmark run completed successfully.\n";
    return 0;
}
