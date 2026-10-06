"""
ColliScope Dashboard: Page 1 - Overview
Executive summary, research questions, KPI cards, and verified empirical findings.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from dashboard.data_loader import load_trace_summary, load_cjson_summary, load_effect_sizes


def render_overview():
    st.markdown("""
    <div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); padding: 24px; border-radius: 12px; margin-bottom: 25px; border-left: 6px solid #3b82f6;">
        <h1 style="color: #f8fafc; margin: 0 0 8px 0; font-size: 28px; font-weight: 700;">
            ColliScope Research Dashboard
        </h1>
        <p style="color: #94a3b8; margin: 0; font-size: 16px;">
            Workload-Aware Evaluation and Scope-Aware Cuckoo Hashing for Compiler Symbol Tables
        </p>
    </div>
    """, unsafe_allow_html=True)

    # 1. Authoritative Campaign KPI Cards
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric(label="Authoritative Traces", value="38", help="36 synthetic traces + 2 authentic cJSON traces")
    with col2:
        st.metric(label="Synthetic Conditions", value="12", help="2 identifier distributions x 2 scopes x 3 mixes")
    with col3:
        st.metric(label="Workload Replicates", value="36", help="3 seed replicates per synthetic condition (N=36)")
    with col4:
        st.metric(label="Algorithm Families", value="4", help="Chaining, Cuckoo, Hopscotch, and SVC-Hash")
    with col5:
        st.metric(label="Measured Trials", value="1,520", help="152 trace-algorithm pairs x 10 repetitions (+456 warmups = 1,976 runs)")

    st.markdown("---")

    # 2. Experimental Structure & Unit Model Notice
    st.info("""
    **Methodological Unit Model Notice:**  
    The **1,520 measured benchmark trials** are repeated executions across the 38 traces (10 repetitions per trace $\\times$ algorithm) and are **not** 1,520 independent observations.  
    - **Synthetic Inference ($N = 36$):** Operates on 36 independent workload units (12 conditions $\\times$ 3 stochastic seed replicates), with repeated measurements aggregated via median.  
    - **Real-Source Case Study:** Evaluates **ONE software project (cJSON v1.7.18)** under **TWO scope representations** (flat compilation unit vs authentic lexical nested scopes) as descriptive case-study evidence.
    """)

    # 3. Core Research Questions & Evidence-Based Findings
    st.subheader("Research Questions & Key Findings")

    rq_col1, rq_col2 = st.columns(2)

    with rq_col1:
        st.markdown("""
        <div class="research-card" style="height: 100%;">
            <h4 style="margin-top: 0; color: #3b82f6; font-size: 16px; border-bottom: 2px solid rgba(59,130,246,0.3); padding-bottom: 6px;">RQ1: Symbol-Table Workloads vs Baselines</h4>
            <p style="font-size: 14px; opacity: 0.9;">
                <em>How do collision-resolution techniques behave under realistic compiler-symbol-table-like workloads compared with synthetic workload characteristics?</em>
            </p>
            <ul style="font-size: 13.5px; opacity: 0.95; padding-left: 18px; line-height: 1.6;">
                <li><strong>Cache Locality Wins on Flat Code:</strong> On flat, frequency-skewed traces, Separate Chaining (1.82M op/s) and Hopscotch (1.84M op/s) lead due to hot L1 CPU cache residency for frequently referenced symbols.</li>
                <li><strong>Cuckoo Relocation Pathology:</strong> Plain Cuckoo hashing suffers severe throughput degradation (166k–353k op/s) due to cascading relocation kicks and rehashes under dense symbol insertions.</li>
                <li><strong>SVC-Hash Open-Addressing Robustness:</strong> In frequency-matched synthetic workloads, SVC-Hash significantly outperforms Cuckoo (<strong>39.6% median speedup</strong>, Holm-adj <em>p</em> = 0.00158).</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    with rq_col2:
        st.markdown("""
        <div class="research-card" style="height: 100%;">
            <h4 style="margin-top: 0; color: #10b981; font-size: 16px; border-bottom: 2px solid rgba(16,185,129,0.3); padding-bottom: 6px;">RQ2: Scope-Aware Hashing (SVC-Hash)</h4>
            <p style="font-size: 14px; opacity: 0.9;">
                <em>How does SVC-Hash behave under lexical nesting/shadowing workloads compared with baseline approaches?</em>
            </p>
            <ul style="font-size: 13.5px; opacity: 0.95; padding-left: 18px; line-height: 1.6;">
                <li><strong>Scoped Baseline Degradation:</strong> Baseline multi-table wrappers degrade by <strong>61% to 64%</strong> when moving from flat to nested scopes due to scope-stack traversal overhead.</li>
                <li><strong>SVC-Hash Outperforms Scoped Cuckoo:</strong> In nested synthetic scopes, SVC-Hash delivers a statistically significant <strong>70.8% median speedup</strong> over Scoped Cuckoo (Holm-adj <em>p</em> = 0.00193).</li>
                <li><strong>Real-Source Inversion on cJSON Nested:</strong> On authentic nested code, SVC-Hash achieves <strong>highest throughput of all algorithms (734.9k op/s)</strong>: 1.76x over Scoped Chaining, 2.64x over Scoped Hopscotch, 3.71x over Scoped Cuckoo, while requiring the lowest peak memory (<strong>8.0 KB</strong>).</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 4. Summary Performance Overview Chart
    st.subheader("Performance Summary by Major Workload Family")
    df_summary = load_trace_summary()

    fam_order = [
        ("Random x Flat", ("random", "flat")),
        ("Random x Nested", ("random", "nested")),
        ("Freq-Matched x Flat", ("frequency-matched", "flat")),
        ("Freq-Matched x Nested", ("frequency-matched", "nested")),
        ("cJSON Flat", ("real", "flat")),
        ("cJSON Nested", ("real", "nested"))
    ]

    summary_plot_data = []
    for flabel, (dist, scope) in fam_order:
        sub = df_summary[(df_summary["identifier_distribution"] == dist) & (df_summary["scope_mode"] == scope)]
        for bfam in ["chaining", "cuckoo", "hopscotch", "svc_hash"]:
            sub_b = sub[sub["baseline_family"] == bfam]
            if not sub_b.empty:
                summary_plot_data.append({
                    "Workload Family": flabel,
                    "Algorithm Family": "Chaining / Scoped" if bfam == "chaining" else ("Cuckoo / Scoped" if bfam == "cuckoo" else ("Hopscotch / Scoped" if bfam == "hopscotch" else "SVC-Hash")),
                    "Median Throughput (k-ops/sec)": sub_b["tp_median"].median() / 1000.0
                })

    df_sp = pd.DataFrame(summary_plot_data)

    fig = px.bar(
        df_sp,
        x="Workload Family",
        y="Median Throughput (k-ops/sec)",
        color="Algorithm Family",
        barmode="group",
        color_discrete_map={
            "Chaining / Scoped": "#1f77b4",
            "Cuckoo / Scoped": "#ff7f0e",
            "Hopscotch / Scoped": "#2ca02c",
            "SVC-Hash": "#d62728"
        },
        title="Cross-Family Throughput Comparison (Kilo-Operations / Second)"
    )
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=12),
        margin=dict(l=40, r=40, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True)

    # 5. Dashboard Map
    st.markdown("""
    ### Dashboard Navigation Sitemap
    - **Dataset Explorer:** Filter and inspect the 38 authoritative trace manifests, command distributions, and symbol statistics.
    - **Workload Explorer:** Explore nominal vs realized operation compositions (Zipfian reference skew impact).
    - **Algorithm Comparison:** Interactive multi-metric evaluation across all 4 algorithm families (throughput, latencies, memory).
    - **SVC-Hash Analysis:** Head-to-head speedup ratios, statistical qualification, and internal kick/rebuild diagnostics.
    - **Scope Analysis:** Direct empirical contrast between flat single tables and nested lexical scoping.
    - **Statistical Evidence:** Full Wilcoxon signed-rank hypothesis test results, Holm-adjusted $p$-values, effect sizes, and 95% bootstrap CIs.
    - **Real-Source Case Study:** Dedicated examination of cJSON v1.7.18 (flat compilation unit vs authentic nested lexical scopes).
    - **Trace / Operation Explorer:** Deep-dive into individual traces with per-trace performance tables and command histograms.
    - **Methodology / About:** Comprehensive documentation of the benchmark protocol, timer architecture, and threats to validity.
    - **Interactive Symbol Table Lab:** Live educational demonstration tool with step-by-step operation execution, visual scope trees, bucket slot inspector, and native C++ verification.
    """)
