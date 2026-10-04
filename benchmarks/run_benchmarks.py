"""
ColliScope Benchmark Runner (Python CLI Wrapper)

Orchestrates execution of colliscope_bench across workload traces
and verifies generated machine-readable outputs.
"""

import os
import sys
import subprocess
import argparse
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
    parser = argparse.ArgumentParser(description="ColliScope Benchmark Orchestrator")
    parser.add_argument("--trace", help="Path to single trace file")
    parser.add_argument("--manifest", default="workloads/traces/manifest.json", help="Path to trace manifest")
    parser.add_argument("--algorithms", default="chaining,cuckoo,hopscotch,svc_hash", help="Algorithms to benchmark")
    parser.add_argument("--repetitions", type=int, default=5, help="Repetitions per algorithm")
    parser.add_argument("--warmup", type=int, default=1, help="Warmup iterations")
    parser.add_argument("--output-json", default="results/benchmark_results.json", help="Path to output JSON")
    parser.add_argument("--output-csv", default="results/benchmark_results.csv", help="Path to output CSV")
    parser.add_argument("--no-scoped-baselines", action="store_true", help="Disable ScopedTableWrapper")
    args = parser.parse_args()

    bench_bin = find_bench_binary()
    os.makedirs(os.path.dirname(args.output_json) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(args.output_csv) or ".", exist_ok=True)

    cmd = [
        bench_bin,
        "--algorithms", args.algorithms,
        "--repetitions", str(args.repetitions),
        "--warmup", str(args.warmup),
        "--output-json", os.path.abspath(args.output_json),
        "--output-csv", os.path.abspath(args.output_csv)
    ]
    if args.trace:
        cmd.extend(["--trace", os.path.abspath(args.trace)])
    else:
        cmd.extend(["--manifest", os.path.abspath(args.manifest)])

    if args.no_scoped_baselines:
        cmd.append("--no-scoped-baselines")

    env = dict(os.environ)
    mingw_bin = r"C:\Program Files\CodeBlocks\MinGW\bin"
    if os.path.isdir(mingw_bin) and mingw_bin not in env.get("PATH", ""):
        env["PATH"] = mingw_bin + os.pathsep + env.get("PATH", "")

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=True, env=env)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
