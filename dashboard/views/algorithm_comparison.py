"""
ColliScope Dashboard: Section 3 — Algorithm Comparison
Comprehensive cross-algorithm benchmarking combining multi-metric distributions,
head-to-head speedup ratios, and internal collision-resolution diagnostics.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from dashboard.data_loader import (
    load_trace_summary,
    load_pairwise_comparisons,
    load_effect_sizes,
    load_svc_diagnostics
)

# Standardized algorithm color palette across all dashboard charts
ALGO_PALETTE = {
    "chaining": "#2563eb",
    "scoped_chaining": "#2563eb",
    "Chaining / Scoped": "#2563eb",
    "cuckoo": "#f97316",
    "scoped_cuckoo": "#f97316",
    "Cuckoo / Scoped": "#f97316",
    "hopscotch": "#059669",
    "scoped_hopscotch": "#059669",
    "Hopscotch / Scoped": "#059669",
    "svc_hash": "#dc2626",
    "SVC-Hash": "#dc2626"
}


def render_algorithm_comparison():
    st.markdown("""
    <div style="margin-bottom: 20px;">
        <h2 style="margin: 0 0 6px 0; font-size: 26px; font-weight: 800;">
            ⚖️ Algorithm Comparison
        </h2>
        <p style="margin: 0; font-size: 14.5px; opacity: 0.85;">
            Evaluate collision-resolution approaches across throughput, amortized per-operation latency, 
            memory footprints, and paired head-to-head speedups under both flat and nested scopes.
        </p>
    </div>
    """, unsafe_allow_html=True)

    df_summary = load_trace_summary()
    df_paired = load_pairwise_comparisons()
    df_effects = load_effect_sizes()
    df_diag = load_svc_diagnostics()

    # Metric mapping with rigorous labeling
    metrics_map = {
        "Throughput (k-ops/sec)": (
            "tp_median", 1000.0, "Kilo-Operations / Second (Higher is better)",
            "Total operations completed per second of execution time."
        ),
        "Amortized Lookup Latency p50 (ns)": (
            "lookup_p50_median_ns", 1.0, "Nanoseconds / Operation (Lower is better)",
            "Median batch latency divided by lookup operations (amortized hardware clock time per lookup)."
        ),
        "Amortized Lookup Latency p99 (ns)": (
            "lookup_p99_median_ns", 1.0, "Nanoseconds / Operation (Lower is better)",
            "99th-percentile amortized lookup latency capturing tail-case hash collisions and parent-scope traversals."
        ),
        "Amortized Insert Latency p50 (ns)": (
            "insert_p50_median_ns", 1.0, "Nanoseconds / Operation (Lower is better)",
            "Median batch latency divided by insert/declaration operations."
        ),
        "Amortized Insert Latency p99 (ns)": (
            "insert_p99_median_ns", 1.0, "Nanoseconds / Operation (Lower is better)",
            "99th-percentile insert latency reflecting cuckoo kick cascades or hopscotch neighborhood shifts."
        ),
        "Peak Memory (KB)": (
            "peak_memory_kb_median", 1.0, "Kilobytes (Lower is better)",
            "Peak resident heap memory allocated by the symbol table structure during execution."
        ),
        "Peak Load Factor": (
            "peak_load_factor_median", 1.0, "Observed Load Factor (Ratio)",
            "Maximum ratio of occupied slots to total allocated capacity."
        )
    }

    # Filter Controls
    f_col1, f_col2, f_col3 = st.columns([2, 1, 1])
    with f_col1:
        sel_metric_label = st.selectbox("Primary Evaluation Metric", options=list(metrics_map.keys()), index=0)
    with f_col2:
        sel_scope = st.selectbox("Scope Mode Filter", options=["All Scopes", "Flat Only", "Nested Only"], index=0)
    with f_col3:
        sel_category = st.selectbox("Dataset Filter", options=["All Datasets", "Synthetic Only", "Real-Source Only"], index=0)

    col_name, scale, axis_title, metric_desc = metrics_map[sel_metric_label]

    # Metric Explanation Callout
    st.markdown(f"""
    <div class="research-callout" style="padding: 10px 16px; margin: 8px 0 16px 0; font-size: 13px;">
        <strong>Metric Definition:</strong> {metric_desc}
    </div>
    """, unsafe_allow_html=True)

    # Filter dataframe
    filtered = df_summary.copy()
    if sel_scope == "Flat Only":
        filtered = filtered[filtered["scope_mode"] == "flat"]
    elif sel_scope == "Nested Only":
        filtered = filtered[filtered["scope_mode"] == "nested"]

    if sel_category == "Synthetic Only":
        filtered = filtered[filtered["category"] == "synthetic"]
    elif sel_category == "Real-Source Only":
        filtered = filtered[filtered["category"] == "real-source"]

    # Algorithm multiselect with clear identities
    available_algs = sorted(filtered["algorithm_name"].unique())
    sel_algs = st.multiselect("Active Algorithm Implementations:", options=available_algs, default=available_algs)
    filtered = filtered[filtered["algorithm_name"].isin(sel_algs)]
    filtered["display_val"] = filtered[col_name] / scale

    # Primary Comparative Chart
    st.markdown(f"### {sel_metric_label} Distribution")
    chart_fmt = st.radio("Display Format:", ["Box Plot (Spread & Outliers)", "Grouped Bar (Trace Medians)"], horizontal=True)

    if chart_fmt == "Box Plot (Spread & Outliers)":
        fig = px.box(
            filtered,
            x="algorithm_name",
            y="display_val",
            color="algorithm_name",
            color_discrete_map=ALGO_PALETTE,
            points="all",
            hover_data=["trace_name", "category", "scope_mode"],
            title=f"{sel_metric_label} Across Algorithm Implementations"
        )
    else:
        fig = px.bar(
            filtered,
            x="algorithm_name",
            y="display_val",
            color="algorithm_name",
            color_discrete_map=ALGO_PALETTE,
            barmode="group",
            title=f"{sel_metric_label} Across Algorithm Implementations"
        )

    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis_title="Algorithm Implementation",
        yaxis_title=axis_title,
        showlegend=False,
        margin=dict(l=40, r=40, t=40, b=40)
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # 2. Paired Head-to-Head Speedup Analysis (Integrated from SVC Analysis)
    st.markdown("### Paired Head-to-Head Speedup Analysis (SVC-Hash vs Baselines)")
    st.caption("Ratio of SVC-Hash throughput divided by baseline throughput on identical workloads. Values > 1.0x favor SVC-Hash.")

    # Stratum selection
    if sel_scope == "Nested Only":
        stratum_name = "Nested Scope (N=18)"
        sub_paired = df_paired[df_paired["scope_mode"] == "nested"]
    elif sel_scope == "Flat Only":
        stratum_name = "Flat Scope (N=18)"
        sub_paired = df_paired[df_paired["scope_mode"] == "flat"]
    else:
        stratum_name = "Overall Synthetic (N=36)"
        sub_paired = df_paired

    effects_sub = df_effects[df_effects["stratum"] == stratum_name]

    # Speedup Cards
    sp_col1, sp_col2, sp_col3 = st.columns(3)
    cards_info = [
        (sp_col1, "cuckoo", "vs Cuckoo / Scoped Cuckoo", "#f97316"),
        (sp_col2, "chaining", "vs Chaining / Scoped Chaining", "#2563eb"),
        (sp_col3, "hopscotch", "vs Hopscotch / Scoped Hopscotch", "#059669")
    ]

    for col, bfam, label, accent_color in cards_info:
        with col:
            match = effects_sub[effects_sub["baseline_family"] == bfam]
            if not match.empty:
                med_ratio = match["median_speedup_ratio"].iloc[0]
                ci_low = match["speedup_ratio_ci95_low"].iloc[0]
                ci_high = match["speedup_ratio_ci95_high"].iloc[0]
                r_rb = match["rank_biserial_r"].iloc[0]

                if med_ratio > 1.0 and ci_low > 1.0:
                    tag = "Statistically Significant Advantage"
                    tag_color = "#15803d"
                elif med_ratio > 1.0:
                    tag = "Descriptive Advantage (Non-significant)"
                    tag_color = "#b45309"
                else:
                    tag = "Baseline Advantage"
                    tag_color = "#b91c1c"

                st.markdown(f"""
                <div class="research-card" style="border-top: 3px solid {accent_color}; margin-bottom: 10px;">
                    <div style="font-weight: 700; font-size: 14.5px;">{label}</div>
                    <div style="font-size: 26px; font-weight: 800; margin: 4px 0;">{med_ratio:.2f}x</div>
                    <div style="font-size: 12px; opacity: 0.75;">95% Bootstrap CI: [{ci_low:.2f}x, {ci_high:.2f}x]</div>
                    <div style="font-size: 12px; opacity: 0.75;">Rank-Biserial r: {r_rb:+.2f}</div>
                    <div style="margin-top: 8px; font-size: 11px; font-weight: 700; color: {tag_color}; text-transform: uppercase;">
                        ● {tag}
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # Speedup Ratio Distribution Box Plot
    fig_ratio = px.box(
        sub_paired,
        x="baseline_family",
        y="tp_ratio",
        color="baseline_family",
        points="all",
        hover_data=["trace_name", "workload_type", "replicate"],
        color_discrete_map={"chaining": "#2563eb", "cuckoo": "#f97316", "hopscotch": "#059669"},
        title=f"Throughput Speedup Ratios ({stratum_name}) — Values > 1.0 favor SVC-Hash"
    )
    fig_ratio.add_hline(y=1.0, line_dash="dash", line_color="#ef4444", annotation_text="Parity (1.0x)", annotation_position="bottom right")
    fig_ratio.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis_title="Baseline Algorithm Family",
        yaxis_title="Speedup Ratio (SVC / Baseline)",
        showlegend=False,
        margin=dict(l=40, r=40, t=40, b=40)
    )
    st.plotly_chart(fig_ratio, use_container_width=True)

    st.markdown("---")

    # 3. Internal Algorithm Diagnostics
    st.markdown("### Internal Table Diagnostics")
    st.caption("Hardware execution audit of internal relocation kicks, table capacity rebuilds, and overflow stash utilization.")

    if not df_diag.empty:
        d1, d2, d3, d4 = st.columns(4)
        with d1:
            st.metric("Median Relocation Kicks", f"{df_diag['svc_kicks'].median():.1f}", help="Cuckoo kick displacements executed during insertions")
        with d2:
            st.metric("Median Table Rebuilds", f"{df_diag['svc_rebuilds'].median():.1f}", help="Capacity resize rebuilds triggered")
        with d3:
            st.metric("Max Stash Usage", f"{df_diag['svc_stash_count'].max():.0f}", help="Max elements placed in the 8-slot overflow stash (0 confirms primary buckets accommodated all symbols)")
        with d4:
            st.metric("Tombstones Leftover", f"{df_diag['svc_tombstones'].max():.0f}", help="Tombstones remaining at trace completion (0 confirms clean deactivation sweep)")

    # 4. Detailed Data Tables in Expander
    with st.expander("📊 View Detailed Paired Performance Breakdown Table", expanded=False):
        display_pairs = sub_paired[[
            "trace_name", "scope_mode", "identifier_distribution", "workload_type",
            "baseline_family", "svc_tp_median", "base_tp_median", "tp_diff", "tp_ratio",
            "svc_mem_kb", "base_mem_kb", "mem_diff_kb"
        ]].copy()

        st.dataframe(
            display_pairs,
            column_config={
                "trace_name": "Trace",
                "scope_mode": "Scope",
                "identifier_distribution": "Distribution",
                "workload_type": "Mix",
                "baseline_family": "Baseline",
                "svc_tp_median": st.column_config.NumberColumn("SVC TP (op/s)", format="%.0f"),
                "base_tp_median": st.column_config.NumberColumn("Base TP (op/s)", format="%.0f"),
                "tp_diff": st.column_config.NumberColumn("TP Diff (SVC - Base)", format="%+.0f"),
                "tp_ratio": st.column_config.NumberColumn("Ratio (SVC/Base)", format="%.2fx"),
                "svc_mem_kb": st.column_config.NumberColumn("SVC Mem (KB)", format="%.1f"),
                "base_mem_kb": st.column_config.NumberColumn("Base Mem (KB)", format="%.1f"),
                "mem_diff_kb": st.column_config.NumberColumn("Mem Diff (KB)", format="%+.1f"),
            },
            use_container_width=True,
            hide_index=True
        )
