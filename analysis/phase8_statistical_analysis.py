#!/usr/bin/env python3
"""
Phase 8: Comprehensive Statistical Analysis Pipeline for ColliScope

Authors: DeepMind Advanced Agentic Coding / ColliScope Research Team
Date: October 2026

Strict Experimental Design & Unit Model:
- Authoritative dataset: Phase 7 Benchmark Campaign
- Traces: 38 total (36 synthetic + 2 authentic real-source cJSON)
- Synthetic factorial structure: 2 identifier distributions x 2 scope modes x 3 operation mixes = 12 conditions
- Workload replicates: 3 seed replicates per synthetic condition (rep1, rep2, rep3) -> N = 36 workload replicates
- Benchmark repetitions: 10 repeated measurements per (trace x algorithm) nested within each workload replicate
- Trace-level estimator: Median across 10 repetitions (with mean and IQR retained for sensitivity)
- Real-source evaluation: ONE project (cJSON v1.7.18) x TWO scope representations (flat vs nested). Descriptive case study only.
- Load factor: Observed output metric, NOT an experimental factor.
- Latency: Amortized batch latency per operation.
"""

import os
import sys
import json
import math
import numpy as np
import pandas as pd
from scipy import stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_CSV_PATH = os.path.join(BASE_DIR, "results", "phase7", "phase7_raw_trials.csv")
BENCHMARK_JSON_PATH = os.path.join(BASE_DIR, "results", "phase7", "phase7_benchmark_results.json")
MANIFEST_PATH = os.path.join(BASE_DIR, "workloads", "traces", "manifest.json")
OUTPUT_DIR = os.path.join(BASE_DIR, "results", "phase8")
PLOTS_DIR = os.path.join(OUTPUT_DIR, "plots")

# Ensure output directories exist
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(PLOTS_DIR, exist_ok=True)

# Random seed for bootstrap reproducibility
BOOTSTRAP_SEED = 42
BOOTSTRAP_ROUNDS = 2000


def compute_bootstrap_ci(data, stat_func=np.median, alpha=0.05, n_resamples=BOOTSTRAP_ROUNDS, rng=None):
    """Compute percentile bootstrap confidence interval for a 1D array."""
    if rng is None:
        rng = np.random.default_rng(BOOTSTRAP_SEED)
    data = np.asarray(data)
    n = len(data)
    if n < 3:
        return (np.nan, np.nan)
    resamples = rng.choice(data, size=(n_resamples, n), replace=True)
    resample_stats = np.apply_along_axis(stat_func, 1, resamples)
    low = np.percentile(resample_stats, 100.0 * (alpha / 2.0))
    high = np.percentile(resample_stats, 100.0 * (1.0 - alpha / 2.0))
    return (float(low), float(high))


def holm_bonferroni(p_values):
    """
    Apply Holm-Bonferroni step-down correction to a list of p-values.
    Returns list of adjusted p-values in the original order.
    """
    m = len(p_values)
    if m == 0:
        return []
    
    # Sort with indices
    indexed_p = sorted(enumerate(p_values), key=lambda x: x[1])
    adjusted = [0.0] * m
    
    running_max = 0.0
    for rank, (orig_idx, p) in enumerate(indexed_p):
        k = rank + 1
        adj_p = (m - k + 1) * p
        adj_p = min(1.0, adj_p)
        running_max = max(running_max, adj_p)
        adjusted[orig_idx] = min(1.0, running_max)
        
    return adjusted


def get_baseline_family(alg_name):
    """Map implementation variant to underlying baseline algorithmic family."""
    if alg_name in ("chaining", "scoped_chaining"):
        return "chaining"
    elif alg_name in ("cuckoo", "scoped_cuckoo"):
        return "cuckoo"
    elif alg_name in ("hopscotch", "scoped_hopscotch"):
        return "hopscotch"
    elif alg_name == "svc_hash":
        return "svc_hash"
    return alg_name


def step1_trace_level_summary(df_raw):
    """
    Summarize 10 repetitions per (trace, algorithm) into a single row.
    Produces results/phase8/phase8_trace_level_summary.csv (152 rows).
    """
    print("\n--- STEP 1: Trace-Level Aggregation (N=152 pairs) ---")
    summary_rows = []
    
    grouped = df_raw.groupby(["trace_name", "algorithm_name"], sort=True)
    
    for (trace_name, alg_name), grp in grouped:
        n_reps = len(grp)
        tps = grp["throughput_ops_sec"].to_numpy()
        tot_times = grp["total_time_ns"].to_numpy()
        ins_p50s = grp["insert_p50_ns"].to_numpy()
        look_p50s = grp["lookup_p50_ns"].to_numpy()
        ins_p95s = grp["insert_p95_ns"].to_numpy()
        look_p95s = grp["lookup_p95_ns"].to_numpy()
        ins_p99s = grp["insert_p99_ns"].to_numpy()
        look_p99s = grp["lookup_p99_ns"].to_numpy()
        mems = grp["memory_usage_bytes"].to_numpy()
        lfs = grp["load_factor"].to_numpy()
        # Metadata from first row
        first = grp.iloc[0]
        mean_tp = float(np.mean(tps))
        std_tp = float(np.std(tps, ddof=1)) if n_reps > 1 else 0.0
        cv_tp = (std_tp / mean_tp * 100.0) if mean_tp > 0 else 0.0

        # Classify real-source vs synthetic
        is_real = ("real-source" in trace_name) or (first.get("source_type") == "cJSON") or (first.get("category") == "real-source")
        cat = "real-source" if is_real else "synthetic"
        id_dist = "real" if is_real else first["identifier_distribution"]

        row = {
            "trace_name": trace_name,
            "algorithm_name": alg_name,
            "baseline_family": get_baseline_family(alg_name),
            "category": cat,
            "identifier_distribution": id_dist,
            "scope_mode": first["scope_mode"],
            "workload_type": first["workload_type"],
            "replicate": first["replicate"],
            "seed": int(first["seed"]),
            "source_type": first["source_type"],
            "repetitions": n_reps,
            
            # Throughput
            "tp_median": float(np.median(tps)),
            "tp_mean": mean_tp,
            "tp_std": std_tp,
            "tp_iqr": float(np.percentile(tps, 75) - np.percentile(tps, 25)),
            "tp_min": float(np.min(tps)),
            "tp_max": float(np.max(tps)),
            "tp_cv_pct": cv_tp,
            
            # Total Execution Time (ns)
            "total_time_median_ns": float(np.median(tot_times)),
            "total_time_mean_ns": float(np.mean(tot_times)),
            "total_time_std_ns": float(np.std(tot_times, ddof=1)) if n_reps > 1 else 0.0,
            "total_time_iqr_ns": float(np.percentile(tot_times, 75) - np.percentile(tot_times, 25)),
            
            # Latency (ns)
            "insert_p50_median_ns": float(np.median(ins_p50s)),
            "insert_p50_mean_ns": float(np.mean(ins_p50s)),
            "insert_p95_median_ns": float(np.median(ins_p95s)),
            "insert_p99_median_ns": float(np.median(ins_p99s)),
            "lookup_p50_median_ns": float(np.median(look_p50s)),
            "lookup_p50_mean_ns": float(np.mean(look_p50s)),
            "lookup_p95_median_ns": float(np.median(look_p95s)),
            "lookup_p99_median_ns": float(np.median(look_p99s)),
            
            # Memory & Load Factor
            "peak_memory_bytes_median": float(np.median(mems)),
            "peak_memory_kb_median": float(np.median(mems)) / 1024.0,
            "peak_load_factor_median": float(np.median(lfs)),
            "capacity_median": float(np.median(grp["capacity"])),
            "num_elements_median": float(np.median(grp["num_elements"])),
            
            # Operation counts
            "total_operations": int(first["total_operations"]),
            "insert_count": int(first["insert_count"]),
            "lookup_count": int(first["lookup_count"]),
            "enter_scope_count": int(first["enter_scope_count"]),
            "exit_scope_count": int(first["exit_scope_count"]),
            "successful_references": int(first["successful_references"]),
            "failed_references": int(first["failed_references"]),
            "collision_count_median": float(np.median(grp["collision_count"]))
        }
        summary_rows.append(row)
        
    df_summary = pd.DataFrame(summary_rows)
    out_file = os.path.join(OUTPUT_DIR, "phase8_trace_level_summary.csv")
    df_summary.to_csv(out_file, index=False)
    print(f"Saved: {out_file} ({len(df_summary)} rows)")
    return df_summary


def step2_operation_composition(df_summary, manifest_data):
    """
    Examine actual operation proportions vs nominal workload labels.
    Produces results/phase8/phase8_operation_composition.csv (38 rows).
    """
    print("\n--- STEP 2: Actual Operation Composition Analysis (N=38 traces) ---")
    manifest_map = {t["trace_file"]: t for t in manifest_data["traces"]}
    
    # One row per trace
    trace_groups = df_summary.groupby("trace_name", sort=True).first().reset_index()
    comp_rows = []
    
    for _, r in trace_groups.iterrows():
        tname = r["trace_name"]
        m_entry = manifest_map.get(tname, {})
        
        tot_ops = r["total_operations"]
        ins = r["insert_count"]
        look = r["lookup_count"]
        ent = r["enter_scope_count"]
        ext = r["exit_scope_count"]
        
        pct_decl = (ins / tot_ops * 100.0) if tot_ops > 0 else 0.0
        pct_ref = (look / tot_ops * 100.0) if tot_ops > 0 else 0.0
        pct_scope = ((ent + ext) / tot_ops * 100.0) if tot_ops > 0 else 0.0
        
        succ_ref = r["successful_references"]
        fail_ref = r["failed_references"]
        succ_pct = (succ_ref / look * 100.0) if look > 0 else 0.0
        
        row = {
            "trace_name": tname,
            "category": r["category"],
            "identifier_distribution": r["identifier_distribution"],
            "scope_mode": r["scope_mode"],
            "nominal_workload_type": r["workload_type"],
            "replicate": r["replicate"],
            "seed": r["seed"],
            "total_operations": tot_ops,
            "declaration_count": ins,
            "reference_count": look,
            "enter_scope_count": ent,
            "exit_scope_count": ext,
            "pct_declaration": round(pct_decl, 2),
            "pct_reference": round(pct_ref, 2),
            "pct_scope_ops": round(pct_scope, 2),
            "lookup_success_pct": round(succ_pct, 2),
            "unique_symbols": m_entry.get("unique_symbols", -1)
        }
        comp_rows.append(row)
        
    df_comp = pd.DataFrame(comp_rows)
    out_file = os.path.join(OUTPUT_DIR, "phase8_operation_composition.csv")
    df_comp.to_csv(out_file, index=False)
    print(f"Saved: {out_file} ({len(df_comp)} rows)")
    return df_comp


def step3_synthetic_analysis(df_summary):
    """
    Extract synthetic traces (36 traces x 4 algorithms = 144 rows).
    Produces results/phase8/phase8_synthetic_analysis.csv.
    """
    print("\n--- STEP 3: Synthetic Analysis Dataset (N=144 rows) ---")
    df_synth = df_summary[df_summary["category"] == "synthetic"].copy()
    out_file = os.path.join(OUTPUT_DIR, "phase8_synthetic_analysis.csv")
    df_synth.to_csv(out_file, index=False)
    print(f"Saved: {out_file} ({len(df_synth)} rows: 36 traces x 4 algorithms)")
    return df_synth


def step4_pairwise_comparisons(df_synth):
    """
    Compute paired differences and performance ratios for SVC-Hash vs each baseline
    on every synthetic workload trace (36 traces x 3 baselines = 108 rows).
    Produces results/phase8/phase8_pairwise_comparisons.csv.
    """
    print("\n--- STEP 4: Pairwise Comparisons (N=108 paired observations) ---")
    paired_rows = []
    
    traces = df_synth["trace_name"].unique()
    
    for tname in traces:
        sub = df_synth[df_synth["trace_name"] == tname]
        svc_row = sub[sub["algorithm_name"] == "svc_hash"]
        if svc_row.empty:
            continue
        svc = svc_row.iloc[0]
        
        # Baselines in this trace
        baselines = sub[sub["algorithm_name"] != "svc_hash"]
        for _, base in baselines.iterrows():
            base_fam = base["baseline_family"]
            base_name = base["algorithm_name"]
            
            # Throughput (higher is better for SVC if diff > 0, ratio > 1.0)
            tp_svc = svc["tp_median"]
            tp_base = base["tp_median"]
            tp_diff = tp_svc - tp_base
            tp_ratio = tp_svc / tp_base if tp_base > 0 else np.nan
            tp_pct = (tp_diff / tp_base * 100.0) if tp_base > 0 else np.nan
            
            # Total Execution Time (lower is better for SVC if diff < 0, ratio < 1.0)
            time_svc = svc["total_time_median_ns"]
            time_base = base["total_time_median_ns"]
            time_diff = time_svc - time_base
            time_ratio = time_svc / time_base if time_base > 0 else np.nan
            
            # Latency (lower is better for SVC if diff < 0)
            ins_svc = svc["insert_p50_median_ns"]
            ins_base = base["insert_p50_median_ns"]
            ins_diff = ins_svc - ins_base
            ins_ratio = ins_svc / ins_base if ins_base > 0 else np.nan
            
            look_svc = svc["lookup_p50_median_ns"]
            look_base = base["lookup_p50_median_ns"]
            look_diff = look_svc - look_base
            look_ratio = look_svc / look_base if look_base > 0 else np.nan
            
            # Memory (lower is better for SVC if diff < 0)
            mem_svc = svc["peak_memory_kb_median"]
            mem_base = base["peak_memory_kb_median"]
            mem_diff = mem_svc - mem_base
            mem_ratio = mem_svc / mem_base if mem_base > 0 else np.nan
            
            row = {
                "trace_name": tname,
                "identifier_distribution": svc["identifier_distribution"],
                "scope_mode": svc["scope_mode"],
                "workload_type": svc["workload_type"],
                "replicate": svc["replicate"],
                "seed": svc["seed"],
                "baseline_family": base_fam,
                "baseline_implementation": base_name,
                
                # Performance metrics
                "svc_tp_median": tp_svc,
                "base_tp_median": tp_base,
                "tp_diff": tp_diff,
                "tp_ratio": tp_ratio,
                "tp_pct_change": tp_pct,
                
                "svc_time_median_ns": time_svc,
                "base_time_median_ns": time_base,
                "time_diff_ns": time_diff,
                "time_ratio": time_ratio,
                
                "svc_ins_p50_ns": ins_svc,
                "base_ins_p50_ns": ins_base,
                "ins_diff_ns": ins_diff,
                "ins_ratio": ins_ratio,
                
                "svc_look_p50_ns": look_svc,
                "base_look_p50_ns": look_base,
                "look_diff_ns": look_diff,
                "look_ratio": look_ratio,
                
                "svc_mem_kb": mem_svc,
                "base_mem_kb": mem_base,
                "mem_diff_kb": mem_diff,
                "mem_ratio": mem_ratio
            }
            paired_rows.append(row)
            
    df_paired = pd.DataFrame(paired_rows)
    out_file = os.path.join(OUTPUT_DIR, "phase8_pairwise_comparisons.csv")
    df_paired.to_csv(out_file, index=False)
    print(f"Saved: {out_file} ({len(df_paired)} rows)")
    return df_paired


def step5_statistical_tests(df_paired):
    """
    Conduct paired Wilcoxon signed-rank tests across defined comparison families.
    Apply Holm-Bonferroni correction within each family.
    Produces results/phase8/phase8_statistical_tests.csv.
    """
    print("\n--- STEP 5: Statistical Hypothesis Testing (Paired Wilcoxon & Holm Correction) ---")
    test_results = []
    
    # Define test families
    # Each family groups related hypotheses for multiple-testing control
    families = [
        # Family 1: Overall Synthetic (All N=36 workload replicates) - Primary Throughput
        ("overall_synthetic_throughput", df_paired, "tp_diff", "svc_tp_median", "base_tp_median"),
        # Family 2: Flat Scope Synthetic (N=18) - Throughput
        ("flat_scope_throughput", df_paired[df_paired["scope_mode"] == "flat"], "tp_diff", "svc_tp_median", "base_tp_median"),
        # Family 3: Nested Scope Synthetic (N=18) - Throughput
        ("nested_scope_throughput", df_paired[df_paired["scope_mode"] == "nested"], "tp_diff", "svc_tp_median", "base_tp_median"),
        # Family 4: Overall Synthetic (N=36) - Lookup Latency
        ("overall_synthetic_lookup_latency", df_paired, "look_diff_ns", "svc_look_p50_ns", "base_look_p50_ns"),
        # Family 5: Overall Synthetic (N=36) - Peak Memory
        ("overall_synthetic_peak_memory", df_paired, "mem_diff_kb", "svc_mem_kb", "base_mem_kb"),
        # Family 6: Stratified by Identifier Distribution (Random vs Freq-Matched) - Throughput
        ("random_distribution_throughput", df_paired[df_paired["identifier_distribution"] == "random"], "tp_diff", "svc_tp_median", "base_tp_median"),
        ("freq_matched_distribution_throughput", df_paired[df_paired["identifier_distribution"] == "frequency-matched"], "tp_diff", "svc_tp_median", "base_tp_median"),
        # Family 7: Stratified by Workload Mix - Throughput
        ("declaration_heavy_throughput", df_paired[df_paired["workload_type"] == "declaration-heavy"], "tp_diff", "svc_tp_median", "base_tp_median"),
        ("lookup_heavy_throughput", df_paired[df_paired["workload_type"] == "lookup-heavy"], "tp_diff", "svc_tp_median", "base_tp_median"),
        ("mixed_workload_throughput", df_paired[df_paired["workload_type"] == "mixed"], "tp_diff", "svc_tp_median", "base_tp_median"),
    ]
    
    for fam_name, sub_df, diff_col, svc_col, base_col in families:
        fam_tests = []
        for base_fam in ["chaining", "cuckoo", "hopscotch"]:
            data = sub_df[sub_df["baseline_family"] == base_fam]
            diffs = data[diff_col].dropna().to_numpy()
            n = len(diffs)
            
            if n < 3:
                continue
                
            # Check if all differences are zero
            if np.all(diffs == 0):
                w_stat, p_val = 0.0, 1.0
                r_rb = 0.0
            else:
                try:
                    res = stats.wilcoxon(diffs, alternative="two-sided")
                    w_stat = float(res.statistic)
                    p_val = float(res.pvalue)
                except Exception as e:
                    w_stat = np.nan
                    p_val = np.nan
                
                # Compute matched-pairs rank biserial correlation: (W+ - W-) / (W+ + W-)
                # Rank absolute non-zero differences
                non_zero = diffs[diffs != 0]
                if len(non_zero) > 0:
                    ranks = stats.rankdata(np.abs(non_zero))
                    w_plus = np.sum(ranks[non_zero > 0])
                    w_minus = np.sum(ranks[non_zero < 0])
                    total_ranks = w_plus + w_minus
                    r_rb = float((w_plus - w_minus) / total_ranks) if total_ranks > 0 else 0.0
                else:
                    r_rb = 0.0
                    
            med_diff = float(np.median(diffs))
            mean_diff = float(np.mean(diffs))
            med_svc = float(np.median(data[svc_col]))
            med_base = float(np.median(data[base_col]))
            
            fam_tests.append({
                "family": fam_name,
                "baseline_family": base_fam,
                "n_pairs": n,
                "metric_diff": diff_col,
                "median_svc": med_svc,
                "median_baseline": med_base,
                "median_diff": med_diff,
                "mean_diff": mean_diff,
                "wilcoxon_stat": w_stat,
                "raw_p_value": p_val,
                "rank_biserial_r": round(r_rb, 4)
            })
            
        # Apply Holm-Bonferroni correction within this family
        raw_p_list = [t["raw_p_value"] for t in fam_tests]
        adj_p_list = holm_bonferroni(raw_p_list)
        for t, adj_p in zip(fam_tests, adj_p_list):
            t["adjusted_p_value_holm"] = round(adj_p, 6)
            t["sig_alpha_05"] = bool(adj_p < 0.05)
            t["sig_alpha_01"] = bool(adj_p < 0.01)
            test_results.extend([t])
            
    df_tests = pd.DataFrame(test_results)
    out_file = os.path.join(OUTPUT_DIR, "phase8_statistical_tests.csv")
    df_tests.to_csv(out_file, index=False)
    print(f"Saved: {out_file} ({len(df_tests)} hypothesis tests evaluated)")
    return df_tests


def step6_effect_sizes_and_cis(df_paired):
    """
    Calculate effect sizes, median ratios (speedup/slowdown), and bootstrap CIs.
    Produces results/phase8/phase8_effect_sizes.csv.
    """
    print("\n--- STEP 6: Effect Sizes & Bootstrap Confidence Intervals ---")
    effect_rows = []
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    
    groupings = [
        ("Overall Synthetic (N=36)", df_paired),
        ("Flat Scope (N=18)", df_paired[df_paired["scope_mode"] == "flat"]),
        ("Nested Scope (N=18)", df_paired[df_paired["scope_mode"] == "nested"]),
        ("Random Distribution (N=18)", df_paired[df_paired["identifier_distribution"] == "random"]),
        ("Frequency-Matched Distribution (N=18)", df_paired[df_paired["identifier_distribution"] == "frequency-matched"]),
        ("Declaration-Heavy Mix (N=12)", df_paired[df_paired["workload_type"] == "declaration-heavy"]),
        ("Lookup-Heavy Mix (N=12)", df_paired[df_paired["workload_type"] == "lookup-heavy"]),
        ("Mixed Mix (N=12)", df_paired[df_paired["workload_type"] == "mixed"])
    ]
    
    for grp_name, sub_df in groupings:
        for base_fam in ["chaining", "cuckoo", "hopscotch"]:
            data = sub_df[sub_df["baseline_family"] == base_fam]
            tp_ratios = data["tp_ratio"].dropna().to_numpy()
            tp_diffs = data["tp_diff"].dropna().to_numpy()
            n = len(tp_ratios)
            if n < 3:
                continue
                
            med_ratio = float(np.median(tp_ratios))
            mean_ratio = float(np.mean(tp_ratios))
            ci_ratio_low, ci_ratio_high = compute_bootstrap_ci(tp_ratios, stat_func=np.median, rng=rng)
            
            med_diff = float(np.median(tp_diffs))
            ci_diff_low, ci_diff_high = compute_bootstrap_ci(tp_diffs, stat_func=np.median, rng=rng)
            
            # Rank biserial correlation
            non_zero = tp_diffs[tp_diffs != 0]
            if len(non_zero) > 0:
                ranks = stats.rankdata(np.abs(non_zero))
                w_plus = np.sum(ranks[non_zero > 0])
                w_minus = np.sum(ranks[non_zero < 0])
                total_ranks = w_plus + w_minus
                r_rb = float((w_plus - w_minus) / total_ranks) if total_ranks > 0 else 0.0
            else:
                r_rb = 0.0
                
            # Interquartile range of ratio
            q25 = float(np.percentile(tp_ratios, 25))
            q75 = float(np.percentile(tp_ratios, 75))
            
            row = {
                "stratum": grp_name,
                "baseline_family": base_fam,
                "n_workload_replicates": n,
                "median_speedup_ratio": round(med_ratio, 4),
                "speedup_ratio_ci95_low": round(ci_ratio_low, 4),
                "speedup_ratio_ci95_high": round(ci_ratio_high, 4),
                "mean_speedup_ratio": round(mean_ratio, 4),
                "ratio_q25": round(q25, 4),
                "ratio_q75": round(q75, 4),
                "ratio_min": round(float(np.min(tp_ratios)), 4),
                "ratio_max": round(float(np.max(tp_ratios)), 4),
                "median_throughput_diff_ops_sec": round(med_diff, 1),
                "diff_ci95_low": round(ci_diff_low, 1),
                "diff_ci95_high": round(ci_diff_high, 1),
                "rank_biserial_r": round(r_rb, 4)
            }
            effect_rows.append(row)
            
    df_effects = pd.DataFrame(effect_rows)
    out_file = os.path.join(OUTPUT_DIR, "phase8_effect_sizes.csv")
    df_effects.to_csv(out_file, index=False)
    print(f"Saved: {out_file} ({len(df_effects)} effect-size rows)")
    return df_effects


def step7_real_cjson_case_study(df_summary):
    """
    Summarize cJSON flat and nested traces as a descriptive case study.
    Produces results/phase8/phase8_real_cjson_summary.csv.
    """
    print("\n--- STEP 7: Real cJSON Case Study Summary (1 project x 2 scope representations) ---")
    df_real = df_summary[df_summary["category"] == "real-source"].copy()
    
    case_study_rows = []
    
    for scope_mode in ["flat", "nested"]:
        sub = df_real[df_real["scope_mode"] == scope_mode]
        svc_row = sub[sub["algorithm_name"] == "svc_hash"]
        if svc_row.empty:
            continue
        svc_tp = float(svc_row["tp_median"].iloc[0])
        svc_time = float(svc_row["total_time_median_ns"].iloc[0])
        svc_ins = float(svc_row["insert_p50_median_ns"].iloc[0])
        svc_look = float(svc_row["lookup_p50_median_ns"].iloc[0])
        svc_mem = float(svc_row["peak_memory_kb_median"].iloc[0])
        
        for _, r in sub.iterrows():
            alg = r["algorithm_name"]
            tp = float(r["tp_median"])
            time_ns = float(r["total_time_median_ns"])
            ins_p50 = float(r["insert_p50_median_ns"])
            look_p50 = float(r["lookup_p50_median_ns"])
            mem_kb = float(r["peak_memory_kb_median"])
            lf = float(r["peak_load_factor_median"])
            
            # Speedup of SVC relative to this algorithm (if alg is baseline)
            # If alg is SVC, ratio is 1.0
            speedup_ratio = (svc_tp / tp) if tp > 0 else np.nan
            mem_ratio = (svc_mem / mem_kb) if mem_kb > 0 else np.nan
            
            case_study_rows.append({
                "scope_mode": scope_mode,
                "trace_name": r["trace_name"],
                "algorithm_name": alg,
                "baseline_family": r["baseline_family"],
                "throughput_ops_sec": round(tp, 1),
                "total_time_us": round(time_ns / 1000.0, 2),
                "insert_p50_ns": round(ins_p50, 1),
                "insert_p95_ns": round(float(r["insert_p95_median_ns"]), 1),
                "lookup_p50_ns": round(look_p50, 1),
                "lookup_p95_ns": round(float(r["lookup_p95_median_ns"]), 1),
                "peak_memory_kb": round(mem_kb, 2),
                "peak_load_factor": round(lf, 3),
                "svc_speedup_ratio": round(speedup_ratio, 4),
                "svc_memory_ratio": round(mem_ratio, 4),
                "total_operations": r["total_operations"],
                "successful_references": r["successful_references"],
                "failed_references": r["failed_references"]
            })
            
    df_cjson = pd.DataFrame(case_study_rows)
    out_file = os.path.join(OUTPUT_DIR, "phase8_real_cjson_summary.csv")
    df_cjson.to_csv(out_file, index=False)
    print(f"Saved: {out_file} ({len(df_cjson)} rows)")
    return df_cjson


def step8_generate_visualizations(df_summary, df_paired, df_comp, df_cjson):
    """
    Generate publication-grade matplotlib figures saved to results/phase8/plots/.
    """
    print("\n--- STEP 8: Generating Publication Visualizations ---")
    
    # Palette configuration
    colors = {
        "chaining": "#1f77b4",       # blue
        "cuckoo": "#ff7f0e",         # orange
        "hopscotch": "#2ca02c",      # green
        "svc_hash": "#d62728",       # crimson
        "scoped_chaining": "#1f77b4",
        "scoped_cuckoo": "#ff7f0e",
        "scoped_hopscotch": "#2ca02c"
    }
    
    # -------------------------------------------------------------
    # Plot 1: Throughput across Synthetic Workload Families & cJSON
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(12, 6))
    family_order = [
        ("Random x Flat", ("random", "flat")),
        ("Random x Nested", ("random", "nested")),
        ("Freq-Matched x Flat", ("frequency-matched", "flat")),
        ("Freq-Matched x Nested", ("frequency-matched", "nested")),
        ("cJSON Flat", ("real-source", "flat")),
        ("cJSON Nested", ("real-source", "nested"))
    ]
    
    plot_data = []
    for label, (dist, scope) in family_order:
        if dist == "real-source":
            sub = df_summary[(df_summary["category"] == "real-source") & (df_summary["scope_mode"] == scope)]
        else:
            sub = df_summary[(df_summary["identifier_distribution"] == dist) & (df_summary["scope_mode"] == scope)]
            
        for alg in ["chaining", "cuckoo", "hopscotch", "svc_hash", "scoped_chaining", "scoped_cuckoo", "scoped_hopscotch"]:
            sub_alg = sub[sub["algorithm_name"] == alg]
            if not sub_alg.empty:
                med_val = sub_alg["tp_median"].median()
                plot_data.append({
                    "family": label,
                    "algorithm": alg,
                    "baseline_family": get_baseline_family(alg),
                    "tp_median": med_val
                })
                
    df_p1 = pd.DataFrame(plot_data)
    families_labels = [f[0] for f in family_order]
    x = np.arange(len(families_labels))
    width = 0.20
    
    # Baseline families: chaining, cuckoo, hopscotch, svc_hash
    base_fams = ["chaining", "cuckoo", "hopscotch", "svc_hash"]
    disp_names = ["Chaining / Scoped", "Cuckoo / Scoped", "Hopscotch / Scoped", "SVC-Hash"]
    
    for i, (bfam, dname) in enumerate(zip(base_fams, disp_names)):
        vals = []
        for flabel in families_labels:
            match = df_p1[(df_p1["family"] == flabel) & (df_p1["baseline_family"] == bfam)]
            vals.append(match["tp_median"].iloc[0] if not match.empty else 0)
        ax.bar(x + (i - 1.5) * width, np.array(vals) / 1000.0, width, label=dname, color=colors[bfam], alpha=0.88, edgecolor='black', linewidth=0.6)
        
    ax.set_ylabel("Median Throughput (kilo-ops / sec)", fontsize=11, fontweight='bold')
    ax.set_title("Figure 1: Throughput by Algorithm across Synthetic Workload Families and cJSON", fontsize=12, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(families_labels, rotation=15, ha='right', fontsize=10)
    ax.legend(frameon=True, facecolor='white', framealpha=0.9)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    plt.tight_layout()
    p1_path = os.path.join(PLOTS_DIR, "plot1_throughput_by_workload_family.png")
    fig.savefig(p1_path, dpi=300)
    plt.close(fig)
    print(f"Generated: {p1_path}")

    # -------------------------------------------------------------
    # Plot 2: SVC-Hash Speedup/Slowdown Ratio vs Baselines
    # -------------------------------------------------------------
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5), sharey=True)
    
    for ax, scope, title in [(ax1, "flat", "Flat Scope Traces (N=18)"), (ax2, "nested", "Nested Scope Traces (N=18)")]:
        sub = df_paired[df_paired["scope_mode"] == scope]
        base_fams = ["chaining", "cuckoo", "hopscotch"]
        positions = [1, 2, 3]
        box_data = [sub[sub["baseline_family"] == b]["tp_ratio"].dropna().to_numpy() for b in base_fams]
        
        bplot = ax.boxplot(box_data, positions=positions, widths=0.45, patch_artist=True, medianprops=dict(color='black', linewidth=1.5))
        for patch, bfam in zip(bplot['boxes'], base_fams):
            patch.set_facecolor(colors[bfam])
            patch.set_alpha(0.7)
            
        ax.axhline(1.0, color='red', linestyle='--', linewidth=1.2, label='Parity (1.0x)')
        ax.set_xticks(positions)
        disp_labels = ["vs Chaining", "vs Cuckoo", "vs Hopscotch"] if scope == "flat" else ["vs Scoped Chaining", "vs Scoped Cuckoo", "vs Scoped Hopscotch"]
        ax.set_xticklabels(disp_labels, fontsize=10, fontweight='bold')
        ax.set_title(title, fontsize=11, fontweight='bold')
        ax.grid(axis='y', linestyle='--', alpha=0.5)
        
    ax1.set_ylabel("SVC Speedup Ratio (SVC TP / Baseline TP)\n[Values > 1.0 favor SVC-Hash]", fontsize=10, fontweight='bold')
    ax1.legend(loc='upper right')
    fig.suptitle("Figure 2: Distribution of SVC-Hash Speedup / Slowdown Ratios vs Baselines", fontsize=12, fontweight='bold')
    plt.tight_layout()
    p2_path = os.path.join(PLOTS_DIR, "plot2_svc_speedup_vs_baselines.png")
    fig.savefig(p2_path, dpi=300)
    plt.close(fig)
    print(f"Generated: {p2_path}")

    # -------------------------------------------------------------
    # Plot 3: Nested vs Flat Scope Performance Degradation
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 5))
    df_synth = df_summary[df_summary["category"] == "synthetic"]
    base_fams = ["chaining", "cuckoo", "hopscotch", "svc_hash"]
    disp_names = ["Chaining", "Cuckoo", "Hopscotch", "SVC-Hash"]
    
    flat_medians = []
    nested_medians = []
    for bfam in base_fams:
        flat_val = df_synth[(df_synth["baseline_family"] == bfam) & (df_synth["scope_mode"] == "flat")]["tp_median"].median()
        nest_val = df_synth[(df_synth["baseline_family"] == bfam) & (df_synth["scope_mode"] == "nested")]["tp_median"].median()
        flat_medians.append(flat_val / 1000.0)
        nested_medians.append(nest_val / 1000.0)
        
    x = np.arange(len(base_fams))
    w = 0.35
    ax.bar(x - w/2, flat_medians, w, label="Flat Scope (Unified Table)", color="#4575b4", edgecolor='black', alpha=0.85)
    ax.bar(x + w/2, nested_medians, w, label="Nested Scope (Scoped Wrappers / SVC)", color="#d73027", edgecolor='black', alpha=0.85)
    
    for i in range(len(base_fams)):
        pct_change = ((nested_medians[i] - flat_medians[i]) / flat_medians[i]) * 100.0
        ax.annotate(f"{pct_change:+.1f}%", xy=(x[i], max(flat_medians[i], nested_medians[i]) + 25), ha='center', fontsize=9, fontweight='bold')
        
    ax.set_ylabel("Median Throughput (kilo-ops / sec)", fontsize=11, fontweight='bold')
    ax.set_title("Figure 3: Synthetic Throughput Comparison: Flat vs Nested Scopes", fontsize=12, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(disp_names, fontsize=10, fontweight='bold')
    ax.legend(frameon=True)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    plt.tight_layout()
    p3_path = os.path.join(PLOTS_DIR, "plot3_nested_vs_flat_comparison.png")
    fig.savefig(p3_path, dpi=300)
    plt.close(fig)
    print(f"Generated: {p3_path}")

    # -------------------------------------------------------------
    # Plot 4: Random vs Frequency-Matched Identifier Distribution
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 5))
    rand_medians = []
    freq_medians = []
    for bfam in base_fams:
        r_val = df_synth[(df_synth["baseline_family"] == bfam) & (df_synth["identifier_distribution"] == "random")]["tp_median"].median()
        f_val = df_synth[(df_synth["baseline_family"] == bfam) & (df_synth["identifier_distribution"] == "frequency-matched")]["tp_median"].median()
        rand_medians.append(r_val / 1000.0)
        freq_medians.append(f_val / 1000.0)
        
    ax.bar(x - w/2, rand_medians, w, label="Uniform Random Identifiers", color="#74add1", edgecolor='black', alpha=0.85)
    ax.bar(x + w/2, freq_medians, w, label="Frequency-Matched (Zipfian Skew)", color="#fdae61", edgecolor='black', alpha=0.85)
    
    for i in range(len(base_fams)):
        pct_change = ((freq_medians[i] - rand_medians[i]) / rand_medians[i]) * 100.0
        ax.annotate(f"{pct_change:+.1f}%", xy=(x[i], max(rand_medians[i], freq_medians[i]) + 25), ha='center', fontsize=9, fontweight='bold')
        
    ax.set_ylabel("Median Throughput (kilo-ops / sec)", fontsize=11, fontweight='bold')
    ax.set_title("Figure 4: Impact of Identifier Distribution (Uniform vs Zipfian Frequency Skew)", fontsize=12, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(disp_names, fontsize=10, fontweight='bold')
    ax.legend(frameon=True)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    plt.tight_layout()
    p4_path = os.path.join(PLOTS_DIR, "plot4_random_vs_freq_matched_comparison.png")
    fig.savefig(p4_path, dpi=300)
    plt.close(fig)
    print(f"Generated: {p4_path}")

    # -------------------------------------------------------------
    # Plot 5: Workload Mix Comparison (Decl-Heavy vs Lookup-Heavy vs Mixed)
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(11, 5))
    mix_types = ["declaration-heavy", "mixed", "lookup-heavy"]
    mix_labels = ["Declaration-Heavy", "Mixed (50/50)", "Lookup-Heavy"]
    w3 = 0.22
    
    for i, (mtype, mlabel) in enumerate(zip(mix_types, mix_labels)):
        m_vals = []
        for bfam in base_fams:
            val = df_synth[(df_synth["baseline_family"] == bfam) & (df_synth["workload_type"] == mtype)]["tp_median"].median()
            m_vals.append(val / 1000.0)
        ax.bar(x + (i - 1) * w3, m_vals, w3, label=mlabel, edgecolor='black', alpha=0.85)
        
    ax.set_ylabel("Median Throughput (kilo-ops / sec)", fontsize=11, fontweight='bold')
    ax.set_title("Figure 5: Throughput by Operation Mix across Hash Table Families", fontsize=12, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(disp_names, fontsize=10, fontweight='bold')
    ax.legend(frameon=True)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    plt.tight_layout()
    p5_path = os.path.join(PLOTS_DIR, "plot5_workload_mix_comparison.png")
    fig.savefig(p5_path, dpi=300)
    plt.close(fig)
    print(f"Generated: {p5_path}")

    # -------------------------------------------------------------
    # Plot 6: Paired Throughput Differences Distribution
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 5))
    diff_data = [df_paired[df_paired["baseline_family"] == b]["tp_diff"].to_numpy() / 1000.0 for b in ["chaining", "cuckoo", "hopscotch"]]
    
    vplot = ax.violinplot(diff_data, positions=[1, 2, 3], showmeans=False, showmedians=True)
    for pc, bfam in zip(vplot['bodies'], ["chaining", "cuckoo", "hopscotch"]):
        pc.set_facecolor(colors[bfam])
        pc.set_edgecolor('black')
        pc.set_alpha(0.7)
        
    ax.axhline(0, color='red', linestyle='--', linewidth=1.2, label='Parity (0 diff)')
    ax.set_xticks([1, 2, 3])
    ax.set_xticklabels(["SVC vs Chaining / Scoped", "SVC vs Cuckoo / Scoped", "SVC vs Hopscotch / Scoped"], fontsize=10, fontweight='bold')
    ax.set_ylabel("Paired Difference: SVC TP - Baseline TP (kilo-ops / sec)\n[Values > 0 favor SVC-Hash]", fontsize=10, fontweight='bold')
    ax.set_title("Figure 6: Violin Plot of Paired Throughput Differences across 36 Workload Replicates", fontsize=12, fontweight='bold')
    ax.legend(loc='lower right')
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    plt.tight_layout()
    p6_path = os.path.join(PLOTS_DIR, "plot6_paired_differences_distribution.png")
    fig.savefig(p6_path, dpi=300)
    plt.close(fig)
    print(f"Generated: {p6_path}")

    # -------------------------------------------------------------
    # Plot 7: Peak Memory Comparison (KB)
    # -------------------------------------------------------------
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), sharey=False)
    
    for ax, scope, title in [(ax1, "flat", "Flat Scope Peak Memory (KB)"), (ax2, "nested", "Nested Scope Peak Memory (KB)")]:
        sub = df_synth[df_synth["scope_mode"] == scope]
        mem_vals = [sub[sub["baseline_family"] == b]["peak_memory_kb_median"].median() for b in base_fams]
        bar_colors = [colors[b] for b in base_fams]
        ax.bar(disp_names, mem_vals, color=bar_colors, edgecolor='black', alpha=0.85)
        ax.set_title(title, fontsize=11, fontweight='bold')
        ax.set_ylabel("Peak Allocated Memory (KB) [Lower is better]", fontsize=10)
        ax.grid(axis='y', linestyle='--', alpha=0.5)
        for i, v in enumerate(mem_vals):
            ax.annotate(f"{v:.1f} KB", xy=(i, v + (max(mem_vals)*0.02)), ha='center', fontsize=9, fontweight='bold')
            
    fig.suptitle("Figure 7: Peak Memory Footprint across Hash Table Families", fontsize=12, fontweight='bold')
    plt.tight_layout()
    p7_path = os.path.join(PLOTS_DIR, "plot7_peak_memory_comparison.png")
    fig.savefig(p7_path, dpi=300)
    plt.close(fig)
    print(f"Generated: {p7_path}")

    # -------------------------------------------------------------
    # Plot 8: Latency Comparison (Insert vs Lookup p50, p95)
    # -------------------------------------------------------------
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    
    # Insert Latency
    ins_p50 = [df_synth[df_synth["baseline_family"] == b]["insert_p50_median_ns"].median() for b in base_fams]
    ins_p95 = [df_synth[df_synth["baseline_family"] == b]["insert_p95_median_ns"].median() for b in base_fams]
    
    ax1.bar(x - w/2, ins_p50, w, label="Insert p50", color="#91bfdb", edgecolor='black', alpha=0.85)
    ax1.bar(x + w/2, ins_p95, w, label="Insert p95", color="#4575b4", edgecolor='black', alpha=0.85)
    ax1.set_title("Declaration (Insert) Latency [ns]", fontsize=11, fontweight='bold')
    ax1.set_ylabel("Amortized Batch Latency (ns)", fontsize=10)
    ax1.set_xticks(x)
    ax1.set_xticklabels(disp_names, fontsize=10, fontweight='bold')
    ax1.legend()
    ax1.grid(axis='y', linestyle='--', alpha=0.5)
    
    # Lookup Latency
    look_p50 = [df_synth[df_synth["baseline_family"] == b]["lookup_p50_median_ns"].median() for b in base_fams]
    look_p95 = [df_synth[df_synth["baseline_family"] == b]["lookup_p95_median_ns"].median() for b in base_fams]
    
    ax2.bar(x - w/2, look_p50, w, label="Lookup p50", color="#fee090", edgecolor='black', alpha=0.85)
    ax2.bar(x + w/2, look_p95, w, label="Lookup p95", color="#d73027", edgecolor='black', alpha=0.85)
    ax2.set_title("Reference (Lookup) Latency [ns]", fontsize=11, fontweight='bold')
    ax2.set_ylabel("Amortized Batch Latency (ns)", fontsize=10)
    ax2.set_xticks(x)
    ax2.set_xticklabels(disp_names, fontsize=10, fontweight='bold')
    ax2.legend()
    ax2.grid(axis='y', linestyle='--', alpha=0.5)
    
    fig.suptitle("Figure 8: Amortized Batch Latency Profiles (p50 and p95 Percentiles)", fontsize=12, fontweight='bold')
    plt.tight_layout()
    p8_path = os.path.join(PLOTS_DIR, "plot8_latency_percentiles.png")
    fig.savefig(p8_path, dpi=300)
    plt.close(fig)
    print(f"Generated: {p8_path}")

    # -------------------------------------------------------------
    # Plot 9: Real cJSON Case Study Performance Profile
    # -------------------------------------------------------------
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    
    flat_cjson = df_cjson[df_cjson["scope_mode"] == "flat"]
    nest_cjson = df_cjson[df_cjson["scope_mode"] == "nested"]
    
    f_names = flat_cjson["algorithm_name"].tolist()
    f_tps = (flat_cjson["throughput_ops_sec"] / 1000.0).tolist()
    f_colors = [colors[a] for a in f_names]
    
    ax1.bar(f_names, f_tps, color=f_colors, edgecolor='black', alpha=0.85)
    ax1.set_title("cJSON Flat Representation", fontsize=11, fontweight='bold')
    ax1.set_ylabel("Throughput (kilo-ops / sec)", fontsize=10)
    ax1.grid(axis='y', linestyle='--', alpha=0.5)
    for i, v in enumerate(f_tps):
        ax1.annotate(f"{v:.1f}k", xy=(i, v + 30), ha='center', fontsize=9, fontweight='bold')
        
    n_names = nest_cjson["algorithm_name"].tolist()
    n_tps = (nest_cjson["throughput_ops_sec"] / 1000.0).tolist()
    n_colors = [colors[a] for a in n_names]
    
    ax2.bar(n_names, n_tps, color=n_colors, edgecolor='black', alpha=0.85)
    ax2.set_title("cJSON Authentic Lexical Nested Representation", fontsize=11, fontweight='bold')
    ax2.set_ylabel("Throughput (kilo-ops / sec)", fontsize=10)
    ax2.grid(axis='y', linestyle='--', alpha=0.5)
    for i, v in enumerate(n_tps):
        ax2.annotate(f"{v:.1f}k", xy=(i, v + 15), ha='center', fontsize=9, fontweight='bold')
        
    fig.suptitle("Figure 9: Real-Source cJSON Benchmark: Flat vs Genuine Nested Scopes", fontsize=12, fontweight='bold')
    plt.tight_layout()
    p9_path = os.path.join(PLOTS_DIR, "plot9_real_cjson_case_study.png")
    fig.savefig(p9_path, dpi=300)
    plt.close(fig)
    print(f"Generated: {p9_path}")

    # -------------------------------------------------------------
    # Plot 10: Actual Operation Composition across Conditions
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(13, 6))
    
    # Sort traces logically
    sorted_comp = df_comp.sort_values(by=["category", "scope_mode", "identifier_distribution", "nominal_workload_type", "replicate"])
    x_indices = np.arange(len(sorted_comp))
    
    decl_vals = sorted_comp["pct_declaration"].to_numpy()
    ref_vals = sorted_comp["pct_reference"].to_numpy()
    scope_vals = sorted_comp["pct_scope_ops"].to_numpy()
    
    ax.bar(x_indices, decl_vals, label="DECLARE (%)", color="#1b9e77", edgecolor='black', linewidth=0.4, alpha=0.85)
    ax.bar(x_indices, ref_vals, bottom=decl_vals, label="REFERENCE (%)", color="#d95f02", edgecolor='black', linewidth=0.4, alpha=0.85)
    ax.bar(x_indices, scope_vals, bottom=decl_vals + ref_vals, label="SCOPE OPS (%)", color="#7570b3", edgecolor='black', linewidth=0.4, alpha=0.85)
    
    # Labels
    short_names = [f"{r['scope_mode'][:1].upper()}:{r['identifier_distribution'][:4]}:{r['nominal_workload_type'][:4]}:{r['replicate'][-1]}" if r['category'] == 'synthetic' else f"cJSON:{r['scope_mode'][:4]}" for _, r in sorted_comp.iterrows()]
    ax.set_xticks(x_indices)
    ax.set_xticklabels(short_names, rotation=90, fontsize=8)
    ax.set_ylabel("Operation Composition (%)", fontsize=10, fontweight='bold')
    ax.set_title("Figure 10: Realized Operation Composition across 38 Workload Traces", fontsize=12, fontweight='bold')
    ax.legend(loc='lower right', frameon=True)
    ax.set_ylim(0, 100)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    plt.tight_layout()
    p10_path = os.path.join(PLOTS_DIR, "plot10_actual_operation_composition.png")
    fig.savefig(p10_path, dpi=300)
    plt.close(fig)
    print(f"Generated: {p10_path}")


def main():
    print("=" * 70)
    print("ColliScope Phase 8: Statistical Analysis & Hypothesis Testing Pipeline")
    print("=" * 70)
    
    # 1. Load data
    print(f"Loading raw trial data from: {RAW_CSV_PATH}")
    df_raw = pd.read_csv(RAW_CSV_PATH)
    print(f"Raw rows: {len(df_raw)} (expected 1520)")
    
    print(f"Loading workload manifest from: {MANIFEST_PATH}")
    with open(MANIFEST_PATH, "r") as f:
        manifest_data = json.load(f)
    print(f"Manifest traces: {manifest_data['total_traces']} (expected 38)")
    
    # 2. Execute pipeline steps
    df_summary = step1_trace_level_summary(df_raw)
    df_comp = step2_operation_composition(df_summary, manifest_data)
    df_synth = step3_synthetic_analysis(df_summary)
    df_paired = step4_pairwise_comparisons(df_synth)
    df_tests = step5_statistical_tests(df_paired)
    df_effects = step6_effect_sizes_and_cis(df_paired)
    df_cjson = step7_real_cjson_case_study(df_summary)
    step8_generate_visualizations(df_summary, df_paired, df_comp, df_cjson)
    
    print("\n" + "=" * 70)
    print("Phase 8 Statistical Pipeline Successfully Completed!")
    print("=" * 70)


if __name__ == "__main__":
    main()
