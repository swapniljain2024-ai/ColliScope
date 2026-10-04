"""
ColliScope Dashboard: Page 5 - SVC-Hash Analysis
Detailed head-to-head evaluation, speedup ratios, statistical qualification, and internal table diagnostics.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from dashboard.data_loader import (
    load_pairwise_comparisons, load_statistical_tests,
    load_effect_sizes, load_svc_diagnostics
)


def render_svc_analysis():
    st.title("SVC-Hash In-Depth Analysis")
    st.markdown("Head-to-head performance analysis of Scope-Aware Cuckoo Hashing (SVC-Hash) against traditional collision-resolution techniques.")

    df_paired = load_pairwise_comparisons()
    df_tests = load_statistical_tests()
    df_effects = load_effect_sizes()
    df_diag = load_svc_diagnostics()

    # Scope selection
    sel_scope = st.radio("Evaluation Scope Mode", options=["Nested Scopes (Scoped Baselines)", "Flat Scopes (Single Unified Tables)", "All Workloads Combined"], horizontal=True)

    if sel_scope == "Nested Scopes (Scoped Baselines)":
        filtered_paired = df_paired[df_paired["scope_mode"] == "nested"]
        stratum_name = "Nested Scope (N=18)"
    elif sel_scope == "Flat Scopes (Single Unified Tables)":
        filtered_paired = df_paired[df_paired["scope_mode"] == "flat"]
        stratum_name = "Flat Scope (N=18)"
    else:
        filtered_paired = df_paired
        stratum_name = "Overall Synthetic (N=36)"

    # Head-to-head summary cards
    st.subheader("Head-to-Head Speedup Summary (SVC / Baseline Throughput)")
    c1, c2, c3 = st.columns(3)

    effects_sub = df_effects[df_effects["stratum"] == stratum_name]

    for col, bfam, label in [(c1, "cuckoo", "vs Cuckoo / Scoped"), (c2, "chaining", "vs Chaining / Scoped"), (c3, "hopscotch", "vs Hopscotch / Scoped")]:
        with col:
            match = effects_sub[effects_sub["baseline_family"] == bfam]
            if not match.empty:
                med_ratio = match["median_speedup_ratio"].iloc[0]
                ci_low = match["speedup_ratio_ci95_low"].iloc[0]
                ci_high = match["speedup_ratio_ci95_high"].iloc[0]
                r_rb = match["rank_biserial_r"].iloc[0]

                # Qualification tag
                if med_ratio > 1.0 and ci_low > 1.0:
                    tag = "Statistically Significant Advantage"
                    tag_color = "#15803d" # green
                elif med_ratio > 1.0:
                    tag = "Descriptive Advantage (Non-significant)"
                    tag_color = "#b45309" # amber
                else:
                    tag = "Baseline Advantage"
                    tag_color = "#b91c1c" # red

                st.markdown(f"""
                <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin-bottom: 10px;">
                    <div style="font-weight: 700; color: #334155; font-size: 15px;">{label}</div>
                    <div style="font-size: 26px; font-weight: 800; color: #0f172a; margin: 4px 0;">{med_ratio:.2f}x</div>
                    <div style="font-size: 12px; color: #64748b;">95% Bootstrap CI: [{ci_low:.2f}x, {ci_high:.2f}x]</div>
                    <div style="font-size: 12px; color: #64748b;">Rank-Biserial r: {r_rb:+.2f}</div>
                    <div style="margin-top: 8px; font-size: 11px; font-weight: 700; color: {tag_color}; text-transform: uppercase;">● {tag}</div>
                </div>
                """, unsafe_allow_html=True)

    st.markdown("---")

    # Ratio Distribution Box Plot
    st.subheader("Distribution of Throughput Speedup Ratios")
    fig_ratio = px.box(
        filtered_paired,
        x="baseline_family",
        y="tp_ratio",
        color="baseline_family",
        points="all",
        hover_data=["trace_name", "workload_type", "replicate"],
        color_discrete_map={"chaining": "#1f77b4", "cuckoo": "#ff7f0e", "hopscotch": "#2ca02c"},
        title="SVC Speedup Ratio by Baseline (Values > 1.0 favor SVC-Hash)"
    )
    fig_ratio.add_hline(y=1.0, line_dash="dash", line_color="red", annotation_text="Parity (1.0x)", annotation_position="bottom right")
    fig_ratio.update_layout(
        template="plotly_white",
        xaxis_title="Baseline Algorithm Family",
        yaxis_title="Throughput Speedup Ratio (SVC / Baseline)",
        showlegend=False,
        margin=dict(l=40, r=40, t=50, b=40)
    )
    st.plotly_chart(fig_ratio, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Paired Throughput Differences Table
    st.subheader("Paired Performance Difference Breakdown")
    display_pairs = filtered_paired[[
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

    st.markdown("---")

    # Internal Diagnostics Section
    st.subheader("SVC-Hash Internal Table Diagnostics")
    st.markdown("Inspection of internal relocation kicks, table rebuilds, stash usage, and load factors across all benchmark trials.")

    if not df_diag.empty:
        d1, d2, d3, d4 = st.columns(4)
        with d1:
            st.metric("Median Relocation Kicks", f"{df_diag['svc_kicks'].median():.1f}", help="Total cuckoo kick relocations during insertions")
        with d2:
            st.metric("Median Table Rebuilds", f"{df_diag['svc_rebuilds'].median():.1f}", help="Capacity resize rebuilds triggered")
        with d3:
            st.metric("Max Stash Usage", f"{df_diag['svc_stash_count'].max():.0f}", help="Overflow stash elements (0 confirms primary slots accommodated symbols)")
        with d4:
            st.metric("Tombstones Leftover", f"{df_diag['svc_tombstones'].max():.0f}", help="Tombstones remaining at completion (0 confirms clean scope exit sweep)")

        diag_fig = px.scatter(
            df_diag,
            x="peak_elements",
            y="svc_kicks",
            size="svc_rebuilds",
            hover_data=["trace_name", "peak_load_factor"],
            title="SVC Relocation Kicks vs Peak Elements (Bubble size = Table Rebuilds)",
            color_discrete_sequence=["#d62728"]
        )
        diag_fig.update_layout(template="plotly_white", margin=dict(l=40, r=40, t=50, b=40))
        st.plotly_chart(diag_fig, use_container_width=True)
    else:
        st.info("Diagnostics summary data loaded from Phase 8 trace summaries.")
