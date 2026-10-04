"""
ColliScope Benchmark Runner (Python CLI Wrapper)

Orchestrates execution of colliscope_bench across workload traces
and verifies generated machine-readable outputs.
"""

import os
import sys
import subprocess
import argparse
import shutil
import json

def find_bench_binary() -> str:
    possible_paths = [
        os.path.join("build", "benchmarks", "colliscope_bench.exe"),
        os.path.join("build", "benchmarks", "colliscope_bench"),
        os.path.join("build", "colliscope_bench.exe"),
        os.path.join("build", "colliscope_bench"),
    ]
    for p in possible_paths:
        if os.path.isfile(p):
            return os.path.abspath(p)
    raise FileNotFoundError("colliscope_bench executable not found. Please build the project first.")

def main():
    parser = argparse.ArgumentParser(description="ColliScope Benchmark Orchestrator (Phase 7)")
    parser.add_argument("--trace", help="Path to single trace file")
    parser.add_argument("--manifest", default="workloads/traces/manifest.json", help="Path to trace manifest")
    parser.add_argument("--algorithms", default="chaining,cuckoo,hopscotch,svc_hash", help="Algorithms to benchmark")
    parser.add_argument("--repetitions", type=int, default=10, help="Repetitions per algorithm (default: 10)")
    parser.add_argument("--warmup", type=int, default=3, help="Warmup iterations (default: 3)")
    parser.add_argument("--order-seed", type=int, default=42, help="Seed for alternating algorithm execution order (default: 42)")
    parser.add_argument("--no-alternating-order", action="store_true", help="Disable alternating algorithm execution order")
    parser.add_argument("--output-json", default="results/phase7/phase7_benchmark_results.json", help="Path to output JSON")
    parser.add_argument("--output-csv", default="results/phase7/phase7_raw_trials.csv", help="Path to raw trials CSV")
    parser.add_argument("--output-summary-csv", default="results/phase7/phase7_aggregated_summary.csv", help="Path to aggregated summary CSV")
    parser.add_argument("--no-scoped-baselines", action="store_true", help="Disable ScopedTableWrapper")
    args = parser.parse_args()

    bench_bin = find_bench_binary()
    os.makedirs(os.path.dirname(args.output_json) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(args.output_csv) or ".", exist_ok=True)
    if args.output_summary_csv:
        os.makedirs(os.path.dirname(args.output_summary_csv) or ".", exist_ok=True)

    cmd = [
        bench_bin,
        "--algorithms", args.algorithms,
        "--repetitions", str(args.repetitions),
        "--warmup", str(args.warmup),
        "--order-seed", str(args.order_seed),
        "--output-json", os.path.abspath(args.output_json),
        "--output-csv", os.path.abspath(args.output_csv)
    ]
    if args.output_summary_csv:
        cmd.extend(["--output-summary-csv", os.path.abspath(args.output_summary_csv)])

    if args.trace:
        cmd.extend(["--trace", os.path.abspath(args.trace)])
    else:
        cmd.extend(["--manifest", os.path.abspath(args.manifest)])

    if args.no_scoped_baselines:
        cmd.append("--no-scoped-baselines")

    if args.no_alternating_order:
        cmd.append("--no-alternating-order")

    env = dict(os.environ)
    mingw_bin = r"C:\Program Files\CodeBlocks\MinGW\bin"
    if os.path.isdir(mingw_bin) and mingw_bin not in env.get("PATH", ""):
        env["PATH"] = mingw_bin + os.pathsep + env.get("PATH", "")

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=True, env=env)

    # Mirror primary outputs to top-level results/ for tooling compatibility
    try:
        top_json = os.path.abspath("results/benchmark_results.json")
        top_csv = os.path.abspath("results/benchmark_results.csv")
        if os.path.abspath(args.output_json) != top_json and os.path.isfile(args.output_json):
            shutil.copyfile(args.output_json, top_json)
        if os.path.abspath(args.output_csv) != top_csv and os.path.isfile(args.output_csv):
            shutil.copyfile(args.output_csv, top_csv)
    except Exception as e:
        print(f"Notice: Could not mirror results to top-level results/: {e}")

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()

