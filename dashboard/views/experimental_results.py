"""
ColliScope Dashboard: Section 5 — Experimental Results
Consolidated empirical results organized into five compact tabs:
Key Results, Real-Source Case Study, Statistical Evidence, Workload Details, and Methodology & Reproducibility.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from dashboard.data_loader import (
    load_trace_summary,
    load_synthetic_analysis,
    load_pairwise_comparisons,
    load_statistical_tests,
    load_effect_sizes,
    load_operation_composition,
    load_cjson_summary,
    load_manifest,
    load_analysis_report_text
)

# Standardized algorithm palette
ALGO_PALETTE = {
    "chaining": "#2563eb",
    "scoped_chaining": "#2563eb",
    "Chaining": "#2563eb",
    "cuckoo": "#f97316",
    "scoped_cuckoo": "#f97316",
    "Cuckoo": "#f97316",
    "hopscotch": "#059669",
    "scoped_hopscotch": "#059669",
    "Hopscotch": "#059669",
    "svc_hash": "#dc2626",
    "SVC-Hash": "#dc2626"
}


def render_experimental_results():
    st.markdown("""
    <div style="margin-bottom: 20px;">
        <h2 style="margin: 0 0 6px 0; font-size: 26px; font-weight: 800;">
            📊 Experimental Results & Statistical Evidence
        </h2>
        <p style="margin: 0; font-size: 14.5px; opacity: 0.85;">
            Explore the authoritative Phase 7 benchmark campaign measurements and Phase 8 inferential statistical outputs.
        </p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "1. Key Results",
        "2. Real-Source Case Study",
        "3. Statistical Evidence",
        "4. Workload Details",
        "5. Methodology & Reproducibility"
    ])

    # ----------------------------------------------------
    # TAB 1: Key Results
    # ----------------------------------------------------
    with tab1:
        st.subheader("Executive Empirical Summary")

        # Methodological Unit Model Notice
        st.markdown("""
        <div class="research-callout" style="font-size: 13.5px; line-height: 1.6; margin-top: 4px; margin-bottom: 16px;">
            <strong>Methodological Unit Model:</strong><br>
            • The <strong>1,520 measured trials</strong> are repeated measurements (10 repetitions per trace-algorithm pair) and are <em>not</em> independent workload observations.<br>
            • <strong>Synthetic Statistical Inference (N = 36):</strong> Operates on 36 independent workload units (12 experimental conditions &times; 3 pseudo-random seeds), with repeated measurements aggregated via median.<br>
            • <strong>Real-Source Case Study:</strong> Evaluates <strong>ONE software project (cJSON v1.7.18)</strong> under <strong>TWO scope representations</strong> as descriptive case-study evidence without inferential <em>p</em>-values.
        </div>
        """, unsafe_allow_html=True)

        df_summary = load_trace_summary()
        df_effects = load_effect_sizes()

        # Cross-Condition Performance Overview
        fam_order = [
            ("Random x Flat", ("random", "flat")),
            ("Random x Nested", ("random", "nested")),
            ("Freq-Matched x Flat", ("frequency-matched", "flat")),
            ("Freq-Matched x Nested", ("frequency-matched", "nested")),
            ("cJSON Flat", ("real", "flat")),
            ("cJSON Nested", ("real", "nested"))
        ]

        summary_rows = []
        for flabel, (dist, scope) in fam_order:
            sub = df_summary[(df_summary["identifier_distribution"] == dist) & (df_summary["scope_mode"] == scope)]
            row = {"Workload Family": flabel}
            for bfam in ["chaining", "cuckoo", "hopscotch", "svc_hash"]:
                sub_b = sub[sub["baseline_family"] == bfam]
                if not sub_b.empty:
                    row[bfam] = sub_b["tp_median"].median() / 1000.0
                else:
                    row[bfam] = None
            summary_rows.append(row)

        df_fam_table = pd.DataFrame(summary_rows)

        st.markdown("#### Median Throughput by Workload Family (Kilo-Operations / Second)")
        st.dataframe(
            df_fam_table,
            column_config={
                "Workload Family": "Workload Condition",
                "chaining": st.column_config.NumberColumn("Chaining / Scoped (k-op/s)", format="%.1f"),
                "cuckoo": st.column_config.NumberColumn("Cuckoo / Scoped (k-op/s)", format="%.1f"),
                "hopscotch": st.column_config.NumberColumn("Hopscotch / Scoped (k-op/s)", format="%.1f"),
                "svc_hash": st.column_config.NumberColumn("SVC-Hash (k-op/s)", format="%.1f")
            },
            use_container_width=True,
            hide_index=True
        )

        st.markdown("<br>", unsafe_allow_html=True)

        # Effect Sizes Summary Table
        st.markdown("#### Primary Effect Sizes & Bootstrap Confidence Intervals")
        st.dataframe(
            df_effects[["stratum", "baseline_family", "n_pairs", "median_speedup_ratio", "speedup_ratio_ci95_low", "speedup_ratio_ci95_high", "rank_biserial_r", "r_ci95_low", "r_ci95_high"]],
            column_config={
                "stratum": "Stratum",
                "baseline_family": "Baseline",
                "n_pairs": "N (Pairs)",
                "median_speedup_ratio": st.column_config.NumberColumn("Median Speedup", format="%.2fx"),
                "speedup_ratio_ci95_low": st.column_config.NumberColumn("CI 95% Low", format="%.2fx"),
                "speedup_ratio_ci95_high": st.column_config.NumberColumn("CI 95% High", format="%.2fx"),
                "rank_biserial_r": st.column_config.NumberColumn("Rank-Biserial r", format="%+.2f"),
                "r_ci95_low": st.column_config.NumberColumn("r CI Low", format="%+.2f"),
                "r_ci95_high": st.column_config.NumberColumn("r CI High", format="%+.2f"),
            },
            use_container_width=True,
            hide_index=True
        )

    # ----------------------------------------------------
    # TAB 2: Real-Source Case Study (cJSON v1.7.18)
    # ----------------------------------------------------
    with tab2:
        st.subheader("Authentic Compiler AST Case Study: cJSON v1.7.18")

        # Provenance Box
        st.markdown("""
        <div class="research-callout" style="margin-top: 4px; margin-bottom: 16px;">
            <div style="font-weight: 700; color: #0284c7; font-size: 14px;">Software Corpus Provenance</div>
            <div style="font-size: 13px; opacity: 0.9; margin: 4px 0;">
                <strong>Repository:</strong> github.com/DaveGamble/cJSON | <strong>Version:</strong> v1.7.18 | <strong>Commit:</strong> <code>acc76239bee01d8e9c858ae2cab296704e52d916</code> | <strong>License:</strong> MIT
            </div>
            <div style="font-size: 12.5px; opacity: 0.85; margin-top: 6px;">
                <strong>Descriptive Case Study Notice:</strong> These traces represent <strong>ONE software project</strong> evaluated under <strong>TWO scope representations</strong> (flat translation unit vs authentic Clang AST lexical block scopes). They provide descriptive evidence without inferential <em>p</em>-values.
            </div>
        </div>
        """, unsafe_allow_html=True)

        df_cjson = load_cjson_summary()
        cjson_nest = df_cjson[df_cjson["scope_mode"] == "nested"].copy()
        cjson_flat = df_cjson[df_cjson["scope_mode"] == "flat"].copy()

        c_col1, c_col2 = st.columns(2)
        with c_col1:
            st.markdown("#### Authentic Nested AST (1,002 commands, 128 scopes)")
            fig_nest = px.bar(
                cjson_nest,
                x="algorithm_name",
                y="throughput_ops_sec",
                color="algorithm_name",
                color_discrete_map=ALGO_PALETTE,
                title="cJSON Nested Throughput (ops/sec)"
            )
            fig_nest.update_layout(template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False, margin=dict(l=40, r=40, t=40, b=40))
            st.plotly_chart(fig_nest, use_container_width=True)

        with c_col2:
            st.markdown("#### Flat Compilation Unit (746 commands, 1 scope)")
            fig_flat = px.bar(
                cjson_flat,
                x="algorithm_name",
                y="throughput_ops_sec",
                color="algorithm_name",
                color_discrete_map=ALGO_PALETTE,
                title="cJSON Flat Throughput (ops/sec)"
            )
            fig_flat.update_layout(template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False, margin=dict(l=40, r=40, t=40, b=40))
            st.plotly_chart(fig_flat, use_container_width=True)

        # Full cJSON table
        st.markdown("#### cJSON Comprehensive Metric Comparison")
        st.dataframe(
            df_cjson[["trace_name", "scope_mode", "algorithm_name", "throughput_ops_sec", "total_time_median_us", "lookup_p50_ns", "insert_p50_ns", "peak_memory_kb", "peak_load_factor"]],
            column_config={
                "trace_name": "Trace",
                "scope_mode": "Scope",
                "algorithm_name": "Algorithm",
                "throughput_ops_sec": st.column_config.NumberColumn("Throughput (op/s)", format="%.0f"),
                "total_time_median_us": st.column_config.NumberColumn("Total Time (us)", format="%.1f"),
                "lookup_p50_ns": st.column_config.NumberColumn("Lookup p50 (ns)", format="%.0f"),
                "insert_p50_ns": st.column_config.NumberColumn("Insert p50 (ns)", format="%.0f"),
                "peak_memory_kb": st.column_config.NumberColumn("Peak Mem (KB)", format="%.1f"),
                "peak_load_factor": st.column_config.NumberColumn("Load Factor", format="%.2f"),
            },
            use_container_width=True,
            hide_index=True
        )

    # ----------------------------------------------------
    # TAB 3: Statistical Evidence
    # ----------------------------------------------------
    with tab3:
        st.subheader("Inferential Statistical Suite: Wilcoxon Signed-Rank Tests")
        st.markdown("""
        <div class="research-callout" style="font-size: 13.5px; margin-top: 4px; margin-bottom: 16px;">
            <strong>Statistical Protocol:</strong> Two-sided paired Wilcoxon signed-rank tests performed on paired difference vectors across 
            <strong>N = 36 synthetic workload units</strong> (and N = 18 per scope stratum). 
            Family-wise error rates controlled via <strong>Holm-Bonferroni step-down correction</strong> at significance threshold &alpha; = 0.05.
        </div>
        """, unsafe_allow_html=True)

        df_tests = load_statistical_tests()

        # Primary hypothesis tests summary
        st.markdown("#### Primary Hypothesis Test Results (30 Formulated Tests)")
        st.dataframe(
            df_tests[["test_id", "stratum", "metric", "comparison", "n_pairs", "statistic", "p_value_raw", "p_value_holm", "significant_raw", "significant_holm"]],
            column_config={
                "test_id": "Test ID",
                "stratum": "Stratum",
                "metric": "Metric",
                "comparison": "Comparison",
                "n_pairs": "N",
                "statistic": st.column_config.NumberColumn("Statistic (W)", format="%.1f"),
                "p_value_raw": st.column_config.NumberColumn("Raw p", format="%.5f"),
                "p_value_holm": st.column_config.NumberColumn("Holm-adj p", format="%.5f"),
                "significant_raw": "Sig (Raw)",
                "significant_holm": "Sig (Holm)"
            },
            use_container_width=True,
            hide_index=True
        )

    # ----------------------------------------------------
    # TAB 4: Workload Details
    # ----------------------------------------------------
    with tab4:
        st.subheader("Workload Matrix & Operation Compositions")
        st.markdown("""
        <div class="research-callout" style="font-size: 13.5px; margin-top: 4px; margin-bottom: 16px;">
            <strong>Workload Design:</strong> 38 authoritative traces comprised of 36 synthetic traces 
            (2 identifier distributions &times; 2 scope representations &times; 3 operation mixes &times; 3 seed replicates) 
            plus 2 authentic real-source traces extracted from the cJSON AST.
        </div>
        """, unsafe_allow_html=True)

        df_comp = load_operation_composition()
        st.markdown("#### Nominal vs Realized Operation Composition (Zipfian Skew Impact)")

        fig_comp = px.bar(
            df_comp,
            x="trace_name",
            y=["realized_lookup_pct", "realized_insert_pct", "realized_scope_enter_pct", "realized_scope_exit_pct"],
            title="Realized Operation Breakdown Across 38 Traces",
            barmode="stack",
            color_discrete_sequence=["#2563eb", "#f97316", "#059669", "#7c3aed"]
        )
        fig_comp.update_layout(template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=40, r=40, t=40, b=40))
        st.plotly_chart(fig_comp, use_container_width=True)

        with st.expander("📁 View Complete Workload Trace Manifest Table", expanded=False):
            st.dataframe(df_comp, use_container_width=True, hide_index=True)

    # ----------------------------------------------------
    # TAB 5: Methodology & Reproducibility
    # ----------------------------------------------------
    with tab5:
        st.subheader("Experimental Methodology & Threats to Validity")

        st.markdown("""
        <div class="research-card">
            <h4 style="margin-top: 0; color: #2563eb; font-size: 15px;">Hardware & Timing Specification</h4>
            <ul style="font-size: 13px; line-height: 1.6; padding-left: 18px; margin: 0;">
                <li><strong>Timer Architecture:</strong> Windows <code>QueryPerformanceCounter</code> (QPC) with 10.0 MHz monotonic frequency (100 ns hardware resolution).</li>
                <li><strong>Compiler Toolchain:</strong> MinGW-w64 GCC 8.1.0 with optimization flags <code>-O3 -std=c++17 -march=native</code>.</li>
                <li><strong>Warmup & Measurement Protocol:</strong> 3 unmeasured warmup passes per algorithm-trace pair followed by 10 measured repetitions.</li>
                <li><strong>Total Execution Campaign:</strong> 152 trace-algorithm pairs &times; 13 executions = <strong>1,976 executions</strong> (1,520 measured + 456 warmups).</li>
                <li><strong>Cold Cache Invariant:</strong> Complete table reallocation and destruction between repetition passes to prevent residual state contamination.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="research-card">
            <h4 style="margin-top: 0; color: #059669; font-size: 15px;">Threats to Validity Addressed</h4>
            <ul style="font-size: 13px; line-height: 1.6; padding-left: 18px; margin: 0;">
                <li><strong>Construct Validity:</strong> High-resolution monotonic QPC timing bounds timer overhead; amortized batch latencies account for clock quantization.</li>
                <li><strong>Internal Validity:</strong> 3 warmup passes eliminate cold-start transients; identical trace inputs feed all algorithms under zero IO during measurement.</li>
                <li><strong>External Validity:</strong> Benchmarks span both synthetic workloads with controlled Zipfian skew and authentic Clang AST traces extracted from production C code.</li>
                <li><strong>Conclusion Validity:</strong> Repeated trials are strictly treated as repeated measurements; statistical inference is conducted across 36 independent stochastic seed units with Holm-Bonferroni correction.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("#### Reproducibility Commands")
        st.code("""# 1. Run all Python unit tests and verification suites
python -m pytest tests/python -v

# 2. Run compiled C++ Catch2 test binary (6,449 assertions)
$env:PATH = "C:\\Program Files\\CodeBlocks\\MinGW\\bin;" + $env:PATH
.\\build\\tests\\colliscope_tests.exe

# 3. Launch Research Demonstration Dashboard
python -m streamlit run dashboard/app.py
""", language="powershell")

    # Full Research Report Expander
    st.markdown("---")
    with st.expander("📄 Full Phase 8 Statistical Analysis Report Text", expanded=False):
        report_text = load_analysis_report_text()
        if report_text:
            st.markdown(report_text)
        else:
            st.info("Report markdown file not found.")
