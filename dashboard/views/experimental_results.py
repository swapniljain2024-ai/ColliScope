"""
ColliScope Dashboard: Section 5 — Experimental Results & Provenance
Clean, light, concise presentation of authoritative Phase 7 benchmark measurements,
Phase 8 inferential statistical tests, effect sizes, and cJSON artifact provenance.
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

# Standardized algorithm palette matching ColliScope light theme design system
ALGO_PALETTE = {
    "chaining": "#4F6BED",
    "scoped_chaining": "#4F6BED",
    "Chaining": "#4F6BED",
    "cuckoo": "#E8A34A",
    "scoped_cuckoo": "#E8A34A",
    "Cuckoo": "#E8A34A",
    "hopscotch": "#8B79D9",
    "scoped_hopscotch": "#8B79D9",
    "Hopscotch": "#8B79D9",
    "svc_hash": "#39A985",
    "SVC-Hash": "#39A985"
}


def render_experimental_results():
    st.markdown("""
    <div style="margin-bottom: 16px;">
        <h2 style="margin: 0 0 4px 0; font-size: 24px; font-weight: 800; color: #263247;">
            📊 Experimental Results & Provenance
        </h2>
        <p style="margin: 0; font-size: 14.5px; color: #68758A;">
            Authoritative Phase 7 benchmark measurements (1,520 trials), Phase 8 inferential statistics, and cJSON artifact provenance.
        </p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "1. Key Results & Effect Sizes",
        "2. Real-Source Case Study",
        "3. Statistical Evidence",
        "4. Workload Matrix",
        "5. Methodology & Validity"
    ])

    # ----------------------------------------------------
    # TAB 1: Key Results & Effect Sizes
    # ----------------------------------------------------
    with tab1:
        st.markdown("""
        <div style="padding: 10px 14px; background-color: #FFFFFF; border: 1px solid #E1E7F0; border-radius: 6px; margin-bottom: 14px; font-size: 13.5px; color: #263247;">
            <strong>Evaluation Summary:</strong> 1,520 measured trials (10 repetitions per trace-algorithm pair). Inferential comparisons evaluate <strong>N = 36 independent synthetic units</strong> aggregated by median.
        </div>
        """, unsafe_allow_html=True)

        df_summary = load_trace_summary()
        df_effects = load_effect_sizes()

        # Cross-Condition Median Throughput Table
        fam_order = [
            ("Random × Flat", ("random", "flat")),
            ("Random × Nested", ("random", "nested")),
            ("Freq-Matched × Flat", ("frequency-matched", "flat")),
            ("Freq-Matched × Nested", ("frequency-matched", "nested")),
            ("cJSON Flat", ("real", "flat")),
            ("cJSON Nested", ("real", "nested"))
        ]

        summary_rows = []
        for flabel, (dist, scope) in fam_order:
            sub = df_summary[(df_summary["identifier_distribution"] == dist) & (df_summary["scope_mode"] == scope)]
            row = {"Workload Condition": flabel}
            for bfam in ["chaining", "cuckoo", "hopscotch", "svc_hash"]:
                sub_b = sub[sub["baseline_family"] == bfam]
                if not sub_b.empty:
                    row[bfam] = sub_b["tp_median"].median() / 1000.0
                else:
                    row[bfam] = None
            summary_rows.append(row)

        df_fam_table = pd.DataFrame(summary_rows)

        st.markdown("#### Median Throughput Across Workload Conditions (k-ops/sec)")
        st.dataframe(
            df_fam_table,
            column_config={
                "Workload Condition": "Condition",
                "chaining": st.column_config.NumberColumn("Chaining (k-op/s)", format="%.1f"),
                "cuckoo": st.column_config.NumberColumn("Cuckoo (k-op/s)", format="%.1f"),
                "hopscotch": st.column_config.NumberColumn("Hopscotch (k-op/s)", format="%.1f"),
                "svc_hash": st.column_config.NumberColumn("SVC-Hash (k-op/s)", format="%.1f")
            },
            use_container_width=True,
            hide_index=True
        )

        st.markdown("<br>", unsafe_allow_html=True)

        # Effect Sizes Table
        st.markdown("#### Effect Sizes & Hodges-Lehmann Confidence Intervals")
        st.dataframe(
            df_effects[[
                "stratum", "baseline_family", "n_workload_replicates",
                "median_speedup_ratio", "speedup_ratio_ci95_low", "speedup_ratio_ci95_high",
                "median_throughput_diff_ops_sec", "diff_ci95_low", "diff_ci95_high",
                "rank_biserial_r"
            ]],
            column_config={
                "stratum": "Stratum",
                "baseline_family": "Baseline",
                "n_workload_replicates": "N (Units)",
                "median_speedup_ratio": st.column_config.NumberColumn("Median Speedup", format="%.2fx"),
                "speedup_ratio_ci95_low": st.column_config.NumberColumn("95% CI Low", format="%.2fx"),
                "speedup_ratio_ci95_high": st.column_config.NumberColumn("95% CI High", format="%.2fx"),
                "median_throughput_diff_ops_sec": st.column_config.NumberColumn("Median Diff (op/s)", format="%+.0f"),
                "diff_ci95_low": st.column_config.NumberColumn("Diff CI Low", format="%+.0f"),
                "diff_ci95_high": st.column_config.NumberColumn("Diff CI High", format="%+.0f"),
                "rank_biserial_r": st.column_config.NumberColumn("Rank-Biserial r", format="%+.2f"),
            },
            use_container_width=True,
            hide_index=True
        )

        # Expandable methodological and raw data details
        with st.expander("ℹ️ Unit Model & Aggregation Methodology", expanded=False):
            st.markdown("""
            - **Repeated Trials:** The 1,520 benchmark trials are repeated measurements (10 per trace-algorithm pair), not independent workload units.
            - **Unit Model (N = 36):** Statistical inference operates on 36 independent stochastic seed units (12 conditions × 3 seeds) with trial repetitions aggregated via median.
            - **Case Study (N = 2):** cJSON represents 1 software codebase evaluated under 2 scope representations; reported descriptively without inferential p-values.
            """)

        with st.expander("📋 View Paired Trials Data (108 Paired Comparisons)", expanded=False):
            df_paired = load_pairwise_comparisons()
            st.dataframe(df_paired, use_container_width=True, hide_index=True)
            csv_data = df_paired.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="⬇️ Download Paired Comparisons CSV",
                data=csv_data,
                file_name="phase8_pairwise_comparisons.csv",
                mime="text/csv"
            )

    # ----------------------------------------------------
    # TAB 2: Real-Source Case Study (cJSON v1.7.18)
    # ----------------------------------------------------
    with tab2:
        # Provenance Header Badge
        st.markdown("""
        <div class="research-card" style="border-left: 4px solid #65A6D9; padding: 12px 18px; margin-bottom: 14px;">
            <div style="font-weight: 700; color: #263247; font-size: 13.5px; margin-bottom: 4px;">
                Software Corpus Provenance
            </div>
            <div style="font-size: 12.5px; color: #68758A; display: flex; flex-wrap: wrap; gap: 14px;">
                <span><strong>Source:</strong> <a href="https://github.com/DaveGamble/cJSON" target="_blank" style="color: #4F6BED; text-decoration: none;">github.com/DaveGamble/cJSON</a></span>
                <span><strong>Release:</strong> <code>v1.7.18</code></span>
                <span><strong>Commit:</strong> <code>acc7623</code></span>
                <span><strong>License:</strong> MIT</span>
                <span><strong>Scope Modes:</strong> Flat (746 ops, 1 scope) vs Nested (1,002 ops, 128 scopes)</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        df_cjson = load_cjson_summary()
        cjson_nest = df_cjson[df_cjson["scope_mode"] == "nested"].copy()
        cjson_flat = df_cjson[df_cjson["scope_mode"] == "flat"].copy()

        c_col1, c_col2 = st.columns(2)
        with c_col1:
            st.markdown("#### Authentic Nested AST (128 Scopes)")
            fig_nest = px.bar(
                cjson_nest,
                x="algorithm_name",
                y="throughput_ops_sec",
                color="algorithm_name",
                color_discrete_map=ALGO_PALETTE,
                title="Nested AST Throughput (ops/sec)"
            )
            fig_nest.update_layout(
                template="plotly_white",
                paper_bgcolor="#FFFFFF",
                plot_bgcolor="#FFFFFF",
                showlegend=False,
                margin=dict(l=30, r=30, t=35, b=30),
                font=dict(color="#263247", size=11.5),
                xaxis=dict(title=None, showgrid=False, tickfont=dict(size=11, color="#263247")),
                yaxis=dict(title="Throughput (ops/sec)", gridcolor="#E1E7F0", tickfont=dict(size=11, color="#68758A")),
                height=260
            )
            st.plotly_chart(fig_nest, use_container_width=True)

        with c_col2:
            st.markdown("#### Flat Translation Unit (1 Scope)")
            fig_flat = px.bar(
                cjson_flat,
                x="algorithm_name",
                y="throughput_ops_sec",
                color="algorithm_name",
                color_discrete_map=ALGO_PALETTE,
                title="Flat AST Throughput (ops/sec)"
            )
            fig_flat.update_layout(
                template="plotly_white",
                paper_bgcolor="#FFFFFF",
                plot_bgcolor="#FFFFFF",
                showlegend=False,
                margin=dict(l=30, r=30, t=35, b=30),
                font=dict(color="#263247", size=11.5),
                xaxis=dict(title=None, showgrid=False, tickfont=dict(size=11, color="#263247")),
                yaxis=dict(title="Throughput (ops/sec)", gridcolor="#E1E7F0", tickfont=dict(size=11, color="#68758A")),
                height=260
            )
            st.plotly_chart(fig_flat, use_container_width=True)

        # Full cJSON table
        st.markdown("#### Comprehensive cJSON Benchmark Comparison")
        st.dataframe(
            df_cjson[["trace_name", "scope_mode", "algorithm_name", "throughput_ops_sec", "total_time_us", "lookup_p50_ns", "insert_p50_ns", "peak_memory_kb", "peak_load_factor"]],
            column_config={
                "trace_name": "Trace",
                "scope_mode": "Scope",
                "algorithm_name": "Algorithm",
                "throughput_ops_sec": st.column_config.NumberColumn("Throughput (op/s)", format="%.0f"),
                "total_time_us": st.column_config.NumberColumn("Total Time (µs)", format="%.1f"),
                "lookup_p50_ns": st.column_config.NumberColumn("Lookup p50 (ns)", format="%.0f"),
                "insert_p50_ns": st.column_config.NumberColumn("Insert p50 (ns)", format="%.0f"),
                "peak_memory_kb": st.column_config.NumberColumn("Peak Mem (KB)", format="%.1f"),
                "peak_load_factor": st.column_config.NumberColumn("Load Factor", format="%.2f"),
            },
            use_container_width=True,
            hide_index=True
        )

        with st.expander("🔍 AST Extraction Protocol & Interpretation", expanded=False):
            st.markdown("""
            - **AST Extraction:** Traces extracted via libclang parser from `cJSON.c` declarations and identifiers.
            - **Nested Mode:** Captures compound statement blocks, function bodies, and switch statements as push/pop scope operations.
            - **Descriptive Evidence:** Evaluates 1 real-world C project under 2 scope representations. It provides empirical validation without inferential p-values.
            """)

    # ----------------------------------------------------
    # TAB 3: Statistical Evidence
    # ----------------------------------------------------
    with tab3:
        st.markdown("""
        <div style="padding: 10px 14px; background-color: #FFFFFF; border: 1px solid #E1E7F0; border-radius: 6px; margin-bottom: 14px; font-size: 13.5px; color: #263247;">
            <strong>Protocol:</strong> Two-sided paired Wilcoxon signed-rank tests across <strong>N = 36 synthetic units</strong> (N = 18 per scope stratum). Family-wise error rate controlled via <strong>Holm-Bonferroni step-down correction</strong> at α = 0.05.
        </div>
        """, unsafe_allow_html=True)

        df_tests = load_statistical_tests()

        # Compact Filter Controls
        fcol1, fcol2 = st.columns(2)
        with fcol1:
            baseline_filter = st.selectbox(
                "Filter Baseline Algorithm",
                options=["All Baselines", "Chaining", "Cuckoo", "Hopscotch"],
                index=0
            )
        with fcol2:
            metric_filter = st.selectbox(
                "Filter Metric",
                options=["All Metrics", "Throughput (tp_diff)", "Lookup Latency (look_diff_ns)", "Peak Memory (mem_diff_kb)"],
                index=0
            )

        # Apply filtering
        df_filtered_tests = df_tests.copy()
        if baseline_filter != "All Baselines":
            df_filtered_tests = df_filtered_tests[df_filtered_tests["baseline_family"] == baseline_filter.lower()]
        if "Throughput" in metric_filter:
            df_filtered_tests = df_filtered_tests[df_filtered_tests["metric_diff"] == "tp_diff"]
        elif "Lookup" in metric_filter:
            df_filtered_tests = df_filtered_tests[df_filtered_tests["metric_diff"] == "look_diff_ns"]
        elif "Memory" in metric_filter:
            df_filtered_tests = df_filtered_tests[df_filtered_tests["metric_diff"] == "mem_diff_kb"]

        st.markdown(f"#### Hypothesis Test Results ({len(df_filtered_tests)} Tests Shown)")
        st.dataframe(
            df_filtered_tests[[
                "family", "baseline_family", "n_pairs", "metric_diff",
                "median_svc", "median_baseline", "median_diff",
                "wilcoxon_stat", "raw_p_value", "adjusted_p_value_holm", "rank_biserial_r", "sig_alpha_05"
            ]],
            column_config={
                "family": "Hypothesis Family",
                "baseline_family": "Baseline",
                "n_pairs": "N (Pairs)",
                "metric_diff": "Metric",
                "median_svc": st.column_config.NumberColumn("Median SVC", format="%.0f"),
                "median_baseline": st.column_config.NumberColumn("Median Base", format="%.0f"),
                "median_diff": st.column_config.NumberColumn("Median Diff", format="%+.0f"),
                "wilcoxon_stat": st.column_config.NumberColumn("Stat (W)", format="%.1f"),
                "raw_p_value": st.column_config.NumberColumn("Raw p", format="%.5f"),
                "adjusted_p_value_holm": st.column_config.NumberColumn("Holm p", format="%.5f"),
                "rank_biserial_r": st.column_config.NumberColumn("Rank-Biserial r", format="%+.2f"),
                "sig_alpha_05": "Sig (α=0.05)"
            },
            use_container_width=True,
            hide_index=True
        )

        with st.expander("📐 Wilcoxon Test Methodology & Holm Step-Down Mechanics", expanded=False):
            st.markdown("""
            - **Paired Design:** Each synthetic workload unit (replicate seed) pairs SVC-Hash against the corresponding baseline algorithm on identical trace operations.
            - **Rank-Biserial Correlation ($r$):** Standardized effect size computed as $r = 1 - \\frac{2W}{N(N+1)/2}$, bounded between $[-1, +1]$.
            - **Holm-Bonferroni Correction:** Controls family-wise error rate across all 30 tests by sorting raw p-values and adjusting significance thresholds step-wise.
            """)

    # ----------------------------------------------------
    # TAB 4: Workload Matrix
    # ----------------------------------------------------
    with tab4:
        st.markdown("""
        <div style="padding: 10px 14px; background-color: #FFFFFF; border: 1px solid #E1E7F0; border-radius: 6px; margin-bottom: 14px; font-size: 13.5px; color: #263247;">
            <strong>Workload Design:</strong> 38 authoritative traces (36 synthetic conditions with controlled Zipfian skew and scope nesting + 2 real-world cJSON AST traces).
        </div>
        """, unsafe_allow_html=True)

        df_comp = load_operation_composition()
        st.markdown("#### Realized Operation Composition Across 38 Traces")

        fig_comp = px.bar(
            df_comp,
            x="trace_name",
            y=["pct_reference", "pct_declaration", "pct_scope_ops"],
            title="Realized Operation Breakdown (%)",
            barmode="stack",
            labels={
                "value": "Percentage of Operations (%)",
                "variable": "Operation Type",
                "trace_name": "Trace File"
            },
            color_discrete_map={
                "pct_reference": "#4F6BED",
                "pct_declaration": "#E8A34A",
                "pct_scope_ops": "#39A985"
            }
        )
        fig_comp.update_layout(
            template="plotly_white",
            paper_bgcolor="#FFFFFF",
            plot_bgcolor="#FFFFFF",
            margin=dict(l=30, r=30, t=35, b=60),
            font=dict(color="#263247", size=11.5),
            xaxis=dict(title=None, showticklabels=False, showgrid=False),
            yaxis=dict(title="Operations (%)", gridcolor="#E1E7F0", tickfont=dict(size=11, color="#68758A")),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5,
                title=None
            ),
            height=300
        )
        st.plotly_chart(fig_comp, use_container_width=True)

        with st.expander("📁 View Complete Workload Trace Manifest (38 Traces)", expanded=False):
            st.dataframe(df_comp, use_container_width=True, hide_index=True)
            csv_comp = df_comp.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="⬇️ Download Trace Composition CSV",
                data=csv_comp,
                file_name="phase8_operation_composition.csv",
                mime="text/csv"
            )

    # ----------------------------------------------------
    # TAB 5: Methodology & Validity
    # ----------------------------------------------------
    with tab5:
        m_col1, m_col2 = st.columns(2)

        with m_col1:
            st.markdown("""
            <div class="research-card" style="height: 100%; border-top: 3px solid #4F6BED;">
                <div style="font-weight: 700; font-size: 14px; color: #263247; margin-bottom: 6px;">
                    Hardware & Timing Architecture
                </div>
                <ul style="font-size: 12.5px; color: #68758A; line-height: 1.6; padding-left: 16px; margin: 0;">
                    <li><strong>Monotonic Timer:</strong> Windows <code>QueryPerformanceCounter</code> (10.0 MHz frequency, 100 ns resolution).</li>
                    <li><strong>Toolchain:</strong> MinGW-w64 GCC 8.1.0 with <code>-O3 -std=c++17 -march=native</code>.</li>
                    <li><strong>Warmup Protocol:</strong> 3 unmeasured warmup passes followed by 10 measured repetitions.</li>
                    <li><strong>Execution Campaign:</strong> 152 pairs × 13 passes = <strong>1,976 executions</strong> (1,520 measured).</li>
                    <li><strong>Cache Isolation:</strong> Full table deallocation and reconstruction between runs.</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

        with m_col2:
            st.markdown("""
            <div class="research-card" style="height: 100%; border-top: 3px solid #39A985;">
                <div style="font-weight: 700; font-size: 14px; color: #263247; margin-bottom: 6px;">
                    Threats to Validity Addressed
                </div>
                <ul style="font-size: 12.5px; color: #68758A; line-height: 1.6; padding-left: 16px; margin: 0;">
                    <li><strong>Construct:</strong> Monotonic QPC bounds timing overhead; amortized batch latencies account for clock quantization.</li>
                    <li><strong>Internal:</strong> 3 warmup passes eliminate startup transients; zero file IO during inner measurement loops.</li>
                    <li><strong>External:</strong> Dual-distribution synthetic matrix with Zipfian skew combined with real cJSON AST traces.</li>
                    <li><strong>Conclusion:</strong> N = 36 independent stochastic seed units; paired Wilcoxon tests with Holm-Bonferroni correction.</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### Reproducibility Commands")
        st.code("""# 1. Run Python verification suite (32 tests)
python -m pytest tests/python -v

# 2. Run compiled C++ Catch2 test binary (32 tests, 6,449 assertions)
$env:PATH = "C:\\Program Files\\CodeBlocks\\MinGW\\bin;" + $env:PATH
.\\build\\tests\\colliscope_tests.exe

# 3. Launch Research Demonstration Dashboard
streamlit run dashboard/app.py
""", language="powershell")

        with st.expander("📄 Full Phase 8 Statistical Analysis Report Text", expanded=False):
            report_text = load_analysis_report_text()
            if report_text:
                st.markdown(report_text)
            else:
                st.info("Report markdown file not found.")
