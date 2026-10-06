# ColliScope Research Dashboard (Phase 9)

## Overview
The **ColliScope Research Dashboard** is an interactive, publication-grade visualization tool for exploring empirical symbol table benchmark results and Scope-Aware Cuckoo Hashing (SVC-Hash) evaluation data.

The dashboard directly visualizes the authoritative outputs produced by the **Phase 7 Benchmark Campaign** and verified by the **Phase 8 Statistical Analysis Suite**.

---

## Quickstart

### Prerequisites
Install the required Python dependencies:
```bash
pip install -r requirements.txt
```

### Launching the Dashboard
Launch the dashboard from the workspace root directory:
```bash
python -m streamlit run dashboard/app.py
# Or if streamlit is directly on PATH:
streamlit run dashboard/app.py
```
By default, the dashboard runs on `http://localhost:8501`.

---

## Architecture & Data Sources

The dashboard follows a read-only architecture that consumes locked Phase 8 and Phase 7 artifacts without recalculating or modifying underlying benchmark numbers:

| Data Source | Path | Purpose |
| :--- | :--- | :--- |
| **Trace Summary** | `results/phase8/phase8_trace_level_summary.csv` | Median/mean/IQR metrics across 10 repetitions per trace $\times$ algorithm (152 rows) |
| **Synthetic Dataset** | `results/phase8/phase8_synthetic_analysis.csv` | Workload-replicate matrix across 12 conditions $\times$ 3 seeds (144 rows) |
| **Pairwise Comparisons** | `results/phase8/phase8_pairwise_comparisons.csv` | Paired throughput differences, speedup ratios, and latency differences (108 rows) |
| **Statistical Tests** | `results/phase8/phase8_statistical_tests.csv` | Paired Wilcoxon signed-rank tests with Holm-Bonferroni correction (30 tests) |
| **Effect Sizes** | `results/phase8/phase8_effect_sizes.csv` | Rank-biserial correlations and 95% bootstrap confidence intervals (24 strata) |
| **Operation Composition** | `results/phase8/phase8_operation_composition.csv` | Realized DECLARE, REFERENCE, and SCOPE operation percentages (38 traces) |
| **cJSON Case Study** | `results/phase8/phase8_real_cjson_summary.csv` | Real-source cJSON v1.7.18 flat vs nested performance profile (8 rows) |
| **Analysis Report** | `results/phase8/phase8_analysis_report.md` | Full narrative report covering statistical methodology and findings |
| **Trace Manifest** | `workloads/traces/manifest.json` | Provenance metadata, Git commit hashes, and unique symbol counts |
| **Phase 7 Results** | `results/phase7/phase7_benchmark_results.json` | SVC-specific internal diagnostics (kicks, rebuilds, stash, tombstones) |

---

## Dashboard Pages

1. **1. Overview:** High-level landing page with KPI cards (38 traces, 36 synthetic, 2 cJSON, 4 algorithm families, 1,520 measured trials), core research questions (RQ1, RQ2), and key verified empirical findings.
2. **2. Dataset Explorer:** Multi-dimensional filterable table and distribution histograms for all 38 authoritative workload traces and their provenance.
3. **3. Workload Explorer:** Analysis of nominal mix labels versus realized operation compositions, highlighting the Phase 7 finding regarding Zipfian reference skew (87% references in nominal declaration-heavy frequency-matched traces).
4. **4. Algorithm Comparison:** Interactive multi-metric evaluation (throughput, latencies $p_{50}/p_{95}/p_{99}$, peak memory, load factor) across algorithms with box plots and condition bar charts.
5. **5. SVC-Hash Analysis:** Head-to-head speedup comparisons, statistical significance tags, 95% bootstrap confidence intervals, and internal table diagnostics (relocation kicks, rebuilds, stash).
6. **6. Scope Analysis:** Direct contrast between flat single-table lookups and nested lexical scoping, illustrating the 61%–64% throughput degradation of multi-table baseline wrappers.
7. **7. Statistical Evidence:** Complete hypothesis testing table with Wilcoxon test statistics, raw $p$-values, Holm-adjusted $p$-values, and forest plots with 95% bootstrap CIs.
8. **8. Real-Source Case Study:** Dedicated descriptive analysis of cJSON v1.7.18 (flat global scope vs authentic Clang AST lexical block scopes).
9. **9. Trace / Operation Explorer:** Single-trace drill-down tool displaying command donut charts, symbol metrics, and per-trace algorithm execution outcomes.
10. **10. Methodology / About:** Complete technical documentation covering experimental unit definition ($N=36$ workload units), timer resolution (Windows QPC 10 MHz), and threats to validity.

---

## Methodological Integrity Rules Enforced

- **No Pseudo-Replication:** $N$ is clearly presented as the number of independent workload replicates ($N=36$ synthetic), never 1,520 independent observations.
- **Descriptive Case Study Label:** cJSON results are prominently labeled as a descriptive case study of ONE software project evaluated under TWO scope representations. No inferential $p$-values are assigned to cJSON.
- **Observed Load Factor:** Load factor is presented as an observed output metric resulting from table expansion mechanics, not a controlled independent factor.
- **Balanced Reporting:** The dashboard explicitly documents where baselines outperform SVC-Hash (e.g., flat frequency-skewed traces) alongside where SVC-Hash outperforms baselines (e.g., nested scopes and skewed distributions).
