"""
ColliScope Dashboard: Page 10 - Methodology / About
Comprehensive documentation of benchmark architecture, timing system, and statistical protocols.
"""

import streamlit as st
from dashboard.data_loader import load_analysis_report_text


def render_methodology():
    st.title("Methodology & Experimental Protocol")
    st.markdown("Detailed documentation of the ColliScope experimental design, timing instrumentation, statistical models, and threats to validity.")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Experimental Protocol",
        "Statistical Inference Model",
        "Threats to Validity & Limitations",
        "Full Phase 8 Report"
    ])

    with tab1:
        st.markdown("""
        ### 1. Workload Architecture & Factorial Design
        The benchmark evaluates hash table collision resolution under compiler symbol-table access patterns.

        - **36 Synthetic Traces:**
          - **2 Identifier Distributions:**
            - `random`: Uniformly generated identifier tokens.
            - `frequency-matched`: Zipfian frequency skew sampled from authentic C code corpora.
          - **2 Scope Modes:**
            - `flat`: Single global scope table.
            - `nested`: Dynamic lexical block scopes with enter/exit stack transitions.
          - **3 Operation Mixes:**
            - `declaration-heavy`: Nominal 70% declarations.
            - `lookup-heavy`: Nominal 80% references.
            - `mixed`: Nominal 50/50 balance.
          - **3 Stochastic Seed Replicates:** `rep1` (seed 42), `rep2` (seed 43), `rep3` (seed 44) per condition.
        - **2 Authentic Real-Source Traces:**
          - Generated from **cJSON v1.7.18** (commit `acc76239bee01d8e9c858ae2cab296704e52d916`).
          - Evaluates **ONE software project** under **TWO scope representations** (flat compilation unit vs authentic Clang AST lexical block scopes).

        ### 2. Benchmark Execution Protocol
        - **Pre-timing Warmup:** 3 warmup executions per algorithm/trace pair (456 total warmups).
        - **Measured Trials:** 10 repetitions per algorithm/trace pair (1,520 total measured trials).
        - **Fresh State Isolation:** Tables are instantiated fresh per repetition (`table.reset()`), preventing state carryover.
        - **Order Balancing:** Deterministic pseudo-random shuffle of algorithm execution order per repetition eliminates systematic thermal/cache position bias.
        - **Timing Mechanism:** High-precision Windows `QueryPerformanceCounter` (10 MHz frequency, ~100 ns empirical resolution).
        - **Latency Semantics:** Amortized batch latency per operation for sub-microsecond commands.
        """)

    with tab2:
        st.markdown("""
        ### Statistical Inference Model & Unit Structure
        To ensure scientific validity and avoid pseudo-replication:

        1. **Independent Experimental Unit ($N=36$):**
           The 10 benchmark repetitions are repeated measurements nested within each workload replicate. They are aggregated using the **median** to produce a single robust performance observation per trace $\\times$ algorithm.
        2. **Paired Non-Parametric Inference:**
           Because every algorithm processes the identical sequence of operations on each trace, all comparisons are strictly paired within traces:
           $$\\Delta = \\text{Metric}_{\\text{SVC}} - \\text{Metric}_{\\text{Baseline}}$$
           Evaluated via the **two-sided Wilcoxon signed-rank test**.
        3. **Multiple Testing Correction:**
           Hypotheses are grouped into pre-defined orthogonal comparison families. Family-wise error rate is controlled at $\\alpha = 0.05$ and $\\alpha = 0.01$ via the **Holm-Bonferroni step-down procedure**:
           $$p^{\\text{adj}}_{(i)} = \\min\\left(1.0, \\max_{j \\le i} (k - j + 1) p_{(j)}\\right)$$
        4. **Effect Sizes & Bootstrap Uncertainty:**
           - Matched-pairs rank-biserial correlation: $r_{\\text{rb}} = (W^+ - W^-) / (W^+ + W^-) \\in [-1.0, +1.0]$.
           - 95% Percentile Bootstrap Confidence Intervals computed over 2,000 resamples across the workload replicates.
        """)

    with tab3:
        st.markdown("""
        ### Threats to Validity & Methodological Limitations
        1. **Small Within-Cell Replicate Count ($n=3$):**  
           While total synthetic workload units ($N=36$) and paired strata ($N=18$ or $N=12$) provide sufficient statistical power for non-parametric tests, individual 3-way interaction cells ($2 \\times 2 \\times 3$) have 3 replicates each. Cell-level bootstrap CIs are treated as exploratory.
        2. **Amortized Batch Latency:**  
           Sub-microsecond operation latencies reflect batch wall-clock durations amortized across operation batches, as established in Phase 6.
        3. **Open-Addressing Displacement Rejections:**  
           In 13 synthetic traces, Hopscotch or Cuckoo reached internal relocation/displacement limits under local clustering, causing small numbers of subsequent lookup misses (1 to 15 queries out of hundreds). This is documented as an authentic algorithmic characteristic.
        4. **Single-Project Real-Source Scope:**  
           The real-source case study is restricted to cJSON (C language). Findings cannot be generalized to object-oriented or multi-threaded compiler environments.
        5. **Observed Load Factor:**  
           Load factor is an observed output metric resulting from table expansion mechanics, NOT a controlled experimental factor.
        """)

    with tab4:
        st.subheader("Authoritative Phase 8 Statistical Analysis Report")
        report_text = load_analysis_report_text()
        if report_text:
            st.markdown(report_text)
        else:
            st.info("Phase 8 analysis report text will be loaded directly from results/phase8/phase8_analysis_report.md.")
