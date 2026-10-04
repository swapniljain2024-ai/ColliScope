"""
ColliScope Phase 7 Benchmark Execution Auditor

Performs comprehensive machine-verifiable audit of Phase 7 benchmark outputs:
- Validates trial counts, warmups exclusion, repetitions, and state isolation
- Checks for NaN/inf/zero-duration anomalies
- Verifies trace-to-manifest consistency
- Audits algorithm coverage and execution order
- Exports structured audit report to JSON
"""

import os
import sys
import json
import csv
import math
from typing import Dict, List, Any, Optional

def audit_results(
    json_path: str,
    raw_csv_path: str,
    manifest_path: str,
    summary_csv_path: Optional[str] = None,
    expected_repetitions: int = 10,
    expected_warmups: int = 3,
    expected_trace_count: Optional[int] = 38
) -> Dict[str, Any]:
    audit = {
        "status": "PASS",
        "failures": [],
        "warnings": [],
        "dataset_summary": {},
        "coverage": {},
        "timing_and_metrics": {},
        "algorithm_order_audit": {},
        "checks": {}
    }

    # 1. Load manifest
    if not os.path.isfile(manifest_path):
        audit["status"] = "FAIL"
        audit["failures"].append(f"Manifest not found: {manifest_path}")
        return audit

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    manifest_traces = {entry["trace_file"]: entry for entry in manifest.get("traces", [])}
    if expected_trace_count is not None and len(manifest_traces) != expected_trace_count:
        audit["warnings"].append(f"Manifest contains {len(manifest_traces)} traces; expected {expected_trace_count}")

    # 2. Load JSON results
    if not os.path.isfile(json_path):
        audit["status"] = "FAIL"
        audit["failures"].append(f"JSON output not found: {json_path}")
        return audit

    with open(json_path, "r", encoding="utf-8") as f:
        json_data = json.load(f)

    # 3. Load CSV results
    if not os.path.isfile(raw_csv_path):
        audit["status"] = "FAIL"
        audit["failures"].append(f"Raw CSV output not found: {raw_csv_path}")
        return audit

    with open(raw_csv_path, "r", encoding="utf-8") as f:
        csv_rows = list(csv.DictReader(f))

    # Basic counts
    runs = json_data.get("runs", [])
    actual_traces_in_json = [r["trace_file"] for r in runs]
    actual_trace_count = len(runs)
    total_measured_trials = len(csv_rows)
    
    expected_total_measured = (expected_trace_count or actual_trace_count) * 4 * expected_repetitions
    expected_total_warmups = (expected_trace_count or actual_trace_count) * 4 * expected_warmups
    expected_total_executions = expected_total_measured + expected_total_warmups

    audit["dataset_summary"] = {
        "expected_traces": expected_trace_count or actual_trace_count,
        "actual_traces": actual_trace_count,
        "expected_algorithms_per_trace": 4,
        "expected_repetitions_per_algorithm": expected_repetitions,
        "expected_warmups_per_algorithm": expected_warmups,
        "expected_measured_trials": expected_total_measured,
        "actual_measured_trials": total_measured_trials,
        "expected_warmup_executions": expected_total_warmups,
        "expected_total_executions": expected_total_executions
    }

    # Check 1: sample_lexical.trace exclusion
    lexical_in_json = any("sample_lexical" in t for t in actual_traces_in_json)
    lexical_in_csv = any("sample_lexical" in r.get("trace_name", "") for r in csv_rows)
    if lexical_in_json or lexical_in_csv:
        audit["status"] = "FAIL"
        audit["failures"].append("sample_lexical.trace was inadvertently included in benchmark execution!")
    audit["checks"]["sample_lexical_excluded"] = not (lexical_in_json or lexical_in_csv)

    # Check 2: Trace matching with manifest
    missing_manifest_traces = set(manifest_traces.keys()) - set(actual_traces_in_json)
    extra_traces = set(actual_traces_in_json) - set(manifest_traces.keys())
    if expected_trace_count == len(manifest_traces):
        if missing_manifest_traces:
            audit["status"] = "FAIL"
            audit["failures"].append(f"Missing {len(missing_manifest_traces)} traces from manifest: {list(missing_manifest_traces)[:5]}")
        if extra_traces:
            audit["status"] = "FAIL"
            audit["failures"].append(f"Unexpected traces not in manifest: {list(extra_traces)}")
    audit["checks"]["traces_match_manifest"] = len(missing_manifest_traces) == 0 and len(extra_traces) == 0

    # Check 3: Algorithm coverage per trace
    expected_alg_bases = {"chaining", "cuckoo", "hopscotch", "svc_hash"}
    trace_alg_coverage = {}
    per_alg_trial_counts = {}

    for run in runs:
        t_file = run["trace_file"]
        is_nested = run["is_nested_scope"]
        algs = run.get("algorithms", {})
        
        # Determine expected algorithm names based on scope mode
        if is_nested:
            exp_algs = {"scoped_chaining", "scoped_cuckoo", "scoped_hopscotch", "svc_hash"}
        else:
            exp_algs = {"chaining", "cuckoo", "hopscotch", "svc_hash"}
        
        found_algs = set(algs.keys())
        trace_alg_coverage[t_file] = list(found_algs)
        
        if found_algs != exp_algs:
            audit["status"] = "FAIL"
            audit["failures"].append(f"Trace {t_file} algorithm mismatch. Expected: {exp_algs}, Found: {found_algs}")

        for alg, data in algs.items():
            per_alg_trial_counts[alg] = per_alg_trial_counts.get(alg, 0) + len(data.get("trials", []))
            if data.get("repetitions") != expected_repetitions:
                audit["status"] = "FAIL"
                audit["failures"].append(f"Trace {t_file} algo {alg} has {data.get('repetitions')} reps; expected {expected_repetitions}")

    audit["coverage"]["per_algorithm_trial_counts"] = per_alg_trial_counts
    audit["checks"]["all_algorithms_evaluated"] = len(audit["failures"]) == 0

    # Check 4: Warmups exclusion in CSV
    warmup_rows = [r for r in csv_rows if r.get("is_warmup", "").lower() == "true"]
    if warmup_rows:
        audit["status"] = "FAIL"
        audit["failures"].append(f"{len(warmup_rows)} warmup trials were incorrectly included in raw CSV output!")
    audit["checks"]["warmups_excluded_from_measured"] = (len(warmup_rows) == 0)

    # Check 5: Duplicate trials check
    trial_keys = set()
    duplicate_trials = []
    for r in csv_rows:
        key = (r.get("trace_name"), r.get("algorithm_name"), r.get("trial_index"))
        if key in trial_keys:
            duplicate_trials.append(key)
        trial_keys.add(key)
    if duplicate_trials:
        audit["status"] = "FAIL"
        audit["failures"].append(f"Found {len(duplicate_trials)} duplicate trial records! e.g. {duplicate_trials[:3]}")
    audit["checks"]["no_duplicate_trials"] = (len(duplicate_trials) == 0)

    # Check 6: Metrics validity (no zero wall time, no NaN, no Inf, valid throughput, p50 > 0)
    invalid_rows = []
    zero_time_rows = []
    for i, r in enumerate(csv_rows):
        try:
            total_time = float(r.get("total_time_ns", 0))
            tp = float(r.get("throughput_ops_sec", 0))
            ins_p50 = float(r.get("insert_p50_ns", 0))
            look_p50 = float(r.get("lookup_p50_ns", 0))
            mem = float(r.get("memory_usage_bytes", 0))
            lf = float(r.get("load_factor", 0))

            if total_time <= 0 or math.isnan(total_time) or math.isinf(total_time):
                zero_time_rows.append(i)
            if tp <= 0 or math.isnan(tp) or math.isinf(tp):
                invalid_rows.append((i, "throughput_ops_sec", r.get("throughput_ops_sec")))
            if ins_p50 <= 0 or math.isnan(ins_p50) or math.isinf(ins_p50):
                invalid_rows.append((i, "insert_p50_ns", r.get("insert_p50_ns")))
            if look_p50 <= 0 or math.isnan(look_p50) or math.isinf(look_p50):
                invalid_rows.append((i, "lookup_p50_ns", r.get("lookup_p50_ns")))
            if mem <= 0 or math.isnan(mem) or math.isinf(mem):
                invalid_rows.append((i, "memory_usage_bytes", r.get("memory_usage_bytes")))
            if lf < 0 or math.isnan(lf) or math.isinf(lf):
                invalid_rows.append((i, "load_factor", r.get("load_factor")))
        except Exception as ex:
            invalid_rows.append((i, "parse_error", str(ex)))

    if zero_time_rows:
        audit["status"] = "FAIL"
        audit["failures"].append(f"Found {len(zero_time_rows)} trials with 0 or invalid total_time_ns")
    if invalid_rows:
        audit["status"] = "FAIL"
        audit["failures"].append(f"Found {len(invalid_rows)} invalid metric entries (NaN/inf/<=0) in CSV")

    audit["checks"]["all_timings_positive_and_valid"] = (len(zero_time_rows) == 0 and len(invalid_rows) == 0)

    # Check 7: Execution order distribution
    execution_orders = [int(r.get("execution_order", 0)) for r in csv_rows if "execution_order" in r]
    order_counts = {}
    for o in execution_orders:
        order_counts[o] = order_counts.get(o, 0) + 1
    audit["algorithm_order_audit"] = {
        "execution_order_counts": order_counts,
        "valid_order_range": set(order_counts.keys()) == {1, 2, 3, 4} if order_counts else False
    }
    if set(order_counts.keys()) != {1, 2, 3, 4}:
        audit["warnings"].append(f"Execution order values found: {set(order_counts.keys())}; expected {{1, 2, 3, 4}}")

    # Check 8: Required metadata fields in CSV
    required_fields = [
        "trace_name", "category", "identifier_distribution", "scope_mode", "workload_type",
        "replicate", "seed", "source_type", "algorithm_name", "trial_index", "execution_order",
        "throughput_ops_sec", "insert_p50_ns", "lookup_p50_ns", "memory_usage_bytes", "load_factor"
    ]
    missing_fields = []
    if csv_rows:
        for fld in required_fields:
            if fld not in csv_rows[0]:
                missing_fields.append(fld)
    if missing_fields:
        audit["status"] = "FAIL"
        audit["failures"].append(f"Missing required metadata fields in CSV: {missing_fields}")
    audit["checks"]["all_metadata_fields_present"] = (len(missing_fields) == 0)

    # Check 9: Summary CSV validation if provided
    if summary_csv_path and os.path.isfile(summary_csv_path):
        with open(summary_csv_path, "r", encoding="utf-8") as f:
            summary_rows = list(csv.DictReader(f))
        expected_summary_rows = (expected_trace_count or actual_trace_count) * 4
        audit["dataset_summary"]["summary_csv_rows"] = len(summary_rows)
        audit["dataset_summary"]["expected_summary_rows"] = expected_summary_rows
        if len(summary_rows) != expected_summary_rows:
            audit["failures"].append(f"Summary CSV has {len(summary_rows)} rows; expected {expected_summary_rows}")
        audit["checks"]["summary_csv_matches_aggregates"] = (len(summary_rows) == expected_summary_rows)

    return audit

def print_audit_report(audit: Dict[str, Any]):
    print("=" * 70)
    print(f" COLLISCOPE PHASE 7 BENCHMARK AUDIT: {audit['status']}")
    print("=" * 70)

    ds = audit.get("dataset_summary", {})
    print(f"Traces Evaluated:      {ds.get('actual_traces')} (Expected: {ds.get('expected_traces')})")
    print(f"Algorithms per Trace:  {ds.get('expected_algorithms_per_trace')}")
    print(f"Measured Repetitions:  {ds.get('expected_repetitions_per_algorithm')}")
    print(f"Warmup Trials:         {ds.get('expected_warmups_per_algorithm')} per algorithm")
    print(f"Total Measured Trials: {ds.get('actual_measured_trials')} (Expected: {ds.get('expected_measured_trials')})")
    print(f"Warmup Executions:     {ds.get('expected_warmup_executions')}")
    print(f"Total Executions:      {ds.get('expected_total_executions')}")
    print("-" * 70)

    print("CHECKLIST:")
    for chk, res in audit.get("checks", {}).items():
        status_sym = "[PASS]" if res else "[FAIL]"
        print(f"  {status_sym} {chk}")
    print("-" * 70)

    print("ALGORITHM TRIAL COVERAGE:")
    for alg, cnt in audit.get("coverage", {}).get("per_algorithm_trial_counts", {}).items():
        print(f"  - {alg:<20}: {cnt} trials")

    print("-" * 70)
    ord_counts = audit.get("algorithm_order_audit", {}).get("execution_order_counts", {})
    print(f"EXECUTION ORDER DISTRIBUTION: {ord_counts}")

    if audit.get("failures"):
        print("=" * 70)
        print("FAILURES:")
        for fail in audit["failures"]:
            print(f"  [ERROR] {fail}")

    if audit.get("warnings"):
        print("=" * 70)
        print("WARNINGS:")
        for warn in audit["warnings"]:
            print(f"  [WARN] {warn}")

    print("=" * 70)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Audit Phase 7 Benchmark Execution Outputs")
    parser.add_argument("--json", default="results/phase7/phase7_benchmark_results.json", help="Path to results JSON")
    parser.add_argument("--csv", default="results/phase7/phase7_raw_trials.csv", help="Path to raw trials CSV")
    parser.add_argument("--summary-csv", default="results/phase7/phase7_aggregated_summary.csv", help="Path to summary CSV")
    parser.add_argument("--manifest", default="workloads/traces/manifest.json", help="Path to manifest")
    parser.add_argument("--repetitions", type=int, default=10, help="Expected repetitions")
    parser.add_argument("--warmup", type=int, default=3, help="Expected warmups")
    parser.add_argument("--expected-traces", type=int, default=38, help="Expected trace count")
    parser.add_argument("--output-audit", default="results/phase7/phase7_execution_audit.json", help="Output audit JSON")
    args = parser.parse_args()

    audit = audit_results(
        json_path=args.json,
        raw_csv_path=args.csv,
        manifest_path=args.manifest,
        summary_csv_path=args.summary_csv,
        expected_repetitions=args.repetitions,
        expected_warmups=args.warmup,
        expected_trace_count=args.expected_traces
    )

    print_audit_report(audit)

    if args.output_audit:
        os.makedirs(os.path.dirname(args.output_audit) or ".", exist_ok=True)
        with open(args.output_audit, "w", encoding="utf-8") as f:
            json.dump(audit, f, indent=2)
        print(f"Audit report saved to: {args.output_audit}")

    sys.exit(0 if audit["status"] == "PASS" else 1)
