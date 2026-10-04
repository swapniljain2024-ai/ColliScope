"""
ColliScope Benchmark Engine Python Integration Tests (Phase 6)
"""

import os
import json
import csv
import subprocess
import sys
import pytest

# Ensure workspace root is in sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from benchmarks.run_benchmarks import find_bench_binary

def test_find_bench_binary():
    binary_path = find_bench_binary()
    assert os.path.isfile(binary_path), "colliscope_bench executable must exist"

def test_benchmark_cli_single_trace(tmp_path):
    binary_path = find_bench_binary()
    trace_path = os.path.join("workloads", "traces", "sample_lexical.trace")
    assert os.path.isfile(trace_path), "sample_lexical.trace must exist"

    json_out = str(tmp_path / "results.json")
    csv_out = str(tmp_path / "results.csv")

    cmd = [
        binary_path,
        "--trace", trace_path,
        "--algorithms", "chaining,cuckoo,hopscotch,svc_hash",
        "--repetitions", "2",
        "--warmup", "1",
        "--output-json", json_out,
        "--output-csv", csv_out
    ]

    env = dict(os.environ)
    mingw_bin = r"C:\Program Files\CodeBlocks\MinGW\bin"
    if os.path.isdir(mingw_bin) and mingw_bin not in env.get("PATH", ""):
        env["PATH"] = mingw_bin + os.pathsep + env.get("PATH", "")

    res = subprocess.run(cmd, capture_output=True, text=True, env=env)
    assert res.returncode == 0, f"Benchmark run failed (code {res.returncode}): {res.stderr}"


    # 1. Validate JSON output
    assert os.path.isfile(json_out), "JSON output file must be created"
    with open(json_out, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "benchmark_version" in data
    assert data.get("latency_measurement_methodology") == "amortized batch latency per operation"
    assert "runs" in data
    assert len(data["runs"]) == 1
    run = data["runs"][0]
    assert run["trace_file"] == "sample_lexical.trace"
    assert run["is_nested_scope"] is True
    assert run["total_trace_commands"] == 23

    # Check that each algorithm was evaluated
    for alg in ["scoped_chaining", "scoped_cuckoo", "scoped_hopscotch", "svc_hash"]:
        assert alg in run["algorithms"], f"Algorithm {alg} missing from run"
        alg_data = run["algorithms"][alg]
        assert alg_data["repetitions"] == 2
        assert len(alg_data["trials"]) == 2
        assert alg_data["successful_references"] == 10
        assert alg_data["failed_references"] == 2
        assert alg_data["mean_throughput_ops_sec"] > 0
        assert alg_data["mean_insert_p50_ns"] > 0
        assert alg_data["mean_lookup_p50_ns"] > 0
        assert alg_data["memory_usage_bytes"] > 0
        assert alg_data["final_load_factor"] > 0

    # 2. Validate CSV output
    assert os.path.isfile(csv_out), "CSV output file must be created"
    with open(csv_out, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    # 4 algorithms x 2 repetitions = 8 rows
    assert len(reader) == 8
    first_row = reader[0]
    assert "trace_name" in first_row
    assert "algorithm_name" in first_row
    assert "throughput_ops_sec" in first_row
    assert "insert_p50_ns" in first_row
    assert "lookup_p50_ns" in first_row
    assert "memory_usage_bytes" in first_row
    assert "load_factor" in first_row
    assert "collision_count" in first_row
    assert float(first_row["load_factor"]) > 0.0
    assert float(first_row["insert_p50_ns"]) > 0.0
