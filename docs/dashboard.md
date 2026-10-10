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

## Dashboard Navigation (5 Streamlined Sections)

The redesigned dashboard consolidates all empirical findings into 5 clean, focused sections optimized for faculty demonstrations:

1. **1. Overview:** High-level landing page with 5 KPI cards (38 traces, 12 synthetic conditions, 4 algorithm families, 1,520 measured trials, +70.8% nested speedup), cross-condition median throughput chart, 3 concise takeaways, and quick-launch CTA to the Interactive Lab.
2. **2. Interactive Symbol Table Lab:** Interactive live symbol table demonstrating lexical scope virtualization, dynamic variable shadowing, step-by-step execution, bucket slot visualizer, and native C++ engine verification.
3. **3. Algorithm Comparison:** Performance evaluation across throughput, latencies ($p_{50}/p_{95}$), and peak memory with distribution box plots, summary tables, dedicated SVC-Hash head-to-head cards, and expandable trial details.
4. **4. Scope & SVC-Hash:** Visual architecture comparison (multi-table wrappers vs SVC-Hash unified bucketed array), flat vs nested throughput degradation chart, and authentic cJSON AST inversion analysis.
5. **5. Experimental Results & Provenance:** Publication-grade empirical evidence arranged in 5 compact tabs (Key Results & Effect Sizes, Real-Source Case Study, Statistical Evidence, Workload Matrix, and Methodology & Threats to Validity) with expandable technical notes and CSV export options.

---

## Design System & Theme

The dashboard uses a soft, clean, professional light theme:
- **Main Background:** `#F5F7FB` (soft cool white)
- **Sidebar:** `#EAF0F8` (pale blue-grey)
- **Cards & Panels:** `#FFFFFF` with `#E1E7F0` borders
- **Typography:** `#263247` (main text), `#68758A` (secondary text)
- **Algorithm Palette:** Chaining (`#4F6BED`), Cuckoo (`#E8A34A`), Hopscotch (`#8B79D9`), SVC-Hash (`#39A985`)

---

## Methodological Integrity Rules Enforced

- **No Pseudo-Replication:** $N$ is clearly presented as the number of independent workload replicates ($N=36$ synthetic), never 1,520 independent observations.
- **Descriptive Case Study Label:** cJSON results are prominently labeled as a descriptive case study of ONE software project evaluated under TWO scope representations. No inferential $p$-values are assigned to cJSON.
- **Observed Load Factor:** Load factor is presented as an observed output metric resulting from table expansion mechanics, not a controlled independent factor.
- **Balanced Reporting:** The dashboard explicitly documents where baselines outperform SVC-Hash (e.g., flat frequency-skewed traces) alongside where SVC-Hash outperforms baselines (e.g., nested scopes and skewed distributions).
