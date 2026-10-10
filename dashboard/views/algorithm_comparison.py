"""
ColliScope Dashboard: Section 3 — Algorithm Comparison
Clean, light, modern comparison of collision-resolution techniques across
throughput, amortized latency, memory, and paired speedup ratios.
"""

import streamlit as st
import plotly.express as px
import pandas as pd
from dashboard.data_loader import (
    load_trace_summary,
    load_pairwise_comparisons,
    load_effect_sizes,
    load_svc_diagnostics
)

# Standard light palette
ALGO_PALETTE = {
    "chaining": "#4F6BED",
    "scoped_chaining": "#4F6BED",
    "cuckoo": "#E8A34A",
    "scoped_cuckoo": "#E8A34A",
    "hopscotch": "#8B79D9",
    "scoped_hopscotch": "#8B79D9",
    "svc_hash": "#39A985"
}


def render_algorithm_comparison():
    st.markdown("""
    <div style="margin-bottom: 16px;">
        <h2 style="margin: 0 0 4px 0; font-size: 24px; font-weight: 800; color: #263247;">
            ⚖️ Algorithm Comparison
        </h2>
        <p style="margin: 0; font-size: 14.5px; color: #68758A;">
            Compare collision-resolution techniques across throughput, amortized latencies, and memory footprints.
        </p>
    </div>
    """, unsafe_allow_html=True)

    df_summary = load_trace_summary()
    df_paired = load_pairwise_comparisons()
    df_effects = load_effect_sizes()
    df_diag = load_svc_diagnostics()

    # Metric mapping
    metrics_map = {
        "Throughput (k-ops/sec)": (
            "tp_median", 1000.0, "k-ops/sec (Higher is better)"
        ),
        "Lookup Latency p50 (ns)": (
            "lookup_p50_median_ns", 1.0, "ns / lookup (Lower is better)"
        ),
        "Lookup Latency p99 (ns)": (
            "lookup_p99_median_ns", 1.0, "ns / lookup (Lower is better)"
        ),
        "Insert Latency p50 (ns)": (
            "insert_p50_median_ns", 1.0, "ns / insert (Lower is better)"
        ),
        "Peak Memory (KB)": (
            "peak_memory_kb_median", 1.0, "KB (Lower is better)"
        ),
        "Peak Load Factor": (
            "peak_load_factor_median", 1.0, "Observed Load Factor"
        )
    }

    # Filter Controls (Compact Single Row)
    f_col1, f_col2, f_col3 = st.columns([2, 1, 1])
    with f_col1:
        sel_metric_label = st.selectbox("Primary Metric:", options=list(metrics_map.keys()), index=0)
    with f_col2:
        sel_scope = st.selectbox("Scope Mode:", options=["All Scopes", "Flat Only", "Nested Only"], index=0)
    with f_col3:
        sel_category = st.selectbox("Dataset:", options=["All Datasets", "Synthetic Only", "Real-Source Only"], index=0)

    col_name, scale, axis_title = metrics_map[sel_metric_label]

    # Filter Dataframe
    filtered = df_summary.copy()
    if sel_scope == "Flat Only":
        filtered = filtered[filtered["scope_mode"] == "flat"]
    elif sel_scope == "Nested Only":
        filtered = filtered[filtered["scope_mode"] == "nested"]

    if sel_category == "Synthetic Only":
        filtered = filtered[filtered["category"] == "synthetic"]
    elif sel_category == "Real-Source Only":
        filtered = filtered[filtered["category"] == "real-source"]

    # Algorithm selector
    available_algs = sorted(filtered["algorithm_name"].unique())
    sel_algs = st.multiselect("Algorithms to Display:", options=available_algs, default=available_algs)
    filtered = filtered[filtered["algorithm_name"].isin(sel_algs)]
    filtered["display_val"] = filtered[col_name] / scale

    # 1. Main Comparison Chart
    chart_col1, chart_col2 = st.columns([2.5, 1])

    with chart_col1:
        fig = px.box(
            filtered,
            x="algorithm_name",
            y="display_val",
            color="algorithm_name",
            color_discrete_map=ALGO_PALETTE,
            points="all",
            hover_data=["trace_name", "category", "scope_mode"]
        )
        fig.update_layout(
            template="plotly_white",
            paper_bgcolor="#FFFFFF",
            plot_bgcolor="#FFFFFF",
            font=dict(family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif", size=12, color="#263247"),
            xaxis=dict(title="Algorithm Implementation", showgrid=False, linecolor="#E1E7F0"),
            yaxis=dict(title=axis_title, gridcolor="#E1E7F0", linecolor="#E1E7F0"),
            showlegend=False,
            height=320,
            margin=dict(l=40, r=20, t=10, b=40)
        )
        st.plotly_chart(fig, use_container_width=True)

    with chart_col2:
        st.markdown("<div style='font-size: 13px; font-weight: 700; color: #263247; margin-bottom: 6px;'>Condition Medians</div>", unsafe_allow_html=True)
        summary_tbl = filtered.groupby("algorithm_name")[col_name].median() / scale
        df_mini = pd.DataFrame({
            "Algorithm": summary_tbl.index,
            "Median": summary_tbl.values.round(1)
        })
        st.dataframe(df_mini, use_container_width=True, hide_index=True, height=270)

    st.markdown("<br>", unsafe_allow_html=True)

    # 2. Dedicated SVC-Hash vs Baseline Speedup Summary
    st.markdown("### SVC-Hash Head-to-Head Speedup")
    st.caption("Ratio of SVC-Hash throughput divided by baseline throughput (values > 1.0x favor SVC-Hash).")

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

    sp_col1, sp_col2, sp_col3 = st.columns(3)
    cards_data = [
        (sp_col1, "cuckoo", "vs Cuckoo / Scoped Cuckoo", "#E8A34A"),
        (sp_col2, "chaining", "vs Chaining / Scoped Chaining", "#4F6BED"),
        (sp_col3, "hopscotch", "vs Hopscotch / Scoped Hopscotch", "#8B79D9")
    ]

    for col, bfam, label, accent_color in cards_data:
        with col:
            match = effects_sub[effects_sub["baseline_family"] == bfam]
            if not match.empty:
                med_ratio = match["median_speedup_ratio"].iloc[0]
                ci_low = match["speedup_ratio_ci95_low"].iloc[0]
                ci_high = match["speedup_ratio_ci95_high"].iloc[0]
                r_rb = match["rank_biserial_r"].iloc[0]

                if med_ratio > 1.0 and ci_low > 1.0:
                    tag = "Significant Advantage"
                    tag_color = "#39A985"
                elif med_ratio > 1.0:
                    tag = "Descriptive Advantage"
                    tag_color = "#E6B65C"
                else:
                    tag = "Baseline Advantage"
                    tag_color = "#DC6B75"

                st.markdown(f"""
                <div class="research-card" style="border-top: 3px solid {accent_color}; margin-bottom: 8px;">
                    <div style="font-weight: 700; font-size: 13.5px; color: #263247;">{label}</div>
                    <div style="font-size: 24px; font-weight: 800; color: #263247; margin: 3px 0;">{med_ratio:.2f}x</div>
                    <div style="font-size: 12px; color: #68758A;">95% CI: [{ci_low:.2f}x, {ci_high:.2f}x] · r: {r_rb:+.2f}</div>
                    <div style="margin-top: 6px; font-size: 11px; font-weight: 700; color: {tag_color}; text-transform: uppercase;">
                        ● {tag}
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # 3. Expanders for Detailed Diagnostics and Tables
    with st.expander("📊 Paired Speedup Distribution Chart & Detailed Breakdown", expanded=False):
        fig_ratio = px.box(
            sub_paired,
            x="baseline_family",
            y="tp_ratio",
            color="baseline_family",
            points="all",
            hover_data=["trace_name", "workload_type", "replicate"],
            color_discrete_map={"chaining": "#4F6BED", "cuckoo": "#E8A34A", "hopscotch": "#8B79D9"}
        )
        fig_ratio.add_hline(y=1.0, line_dash="dash", line_color="#DC6B75", annotation_text="Parity (1.0x)", annotation_position="bottom right")
        fig_ratio.update_layout(
            template="plotly_white",
            paper_bgcolor="#FFFFFF",
            plot_bgcolor="#FFFFFF",
            font=dict(color="#263247"),
            xaxis=dict(title="Baseline Family", linecolor="#E1E7F0"),
            yaxis=dict(title="Speedup Ratio (SVC / Baseline)", gridcolor="#E1E7F0", linecolor="#E1E7F0"),
            showlegend=False,
            height=280,
            margin=dict(l=40, r=20, t=10, b=40)
        )
        st.plotly_chart(fig_ratio, use_container_width=True)

        display_pairs = sub_paired[[
            "trace_name", "scope_mode", "identifier_distribution", "workload_type",
            "baseline_family", "svc_tp_median", "base_tp_median", "tp_diff", "tp_ratio"
        ]].copy()
        st.dataframe(display_pairs, use_container_width=True, hide_index=True)

    with st.expander("⚙️ Internal Table Diagnostics (Kicks, Rebuilds, Stash)", expanded=False):
        if not df_diag.empty:
            d1, d2, d3, d4 = st.columns(4)
            with d1:
                st.metric("Median Relocation Kicks", f"{df_diag['svc_kicks'].median():.1f}")
            with d2:
                st.metric("Median Table Rebuilds", f"{df_diag['svc_rebuilds'].median():.1f}")
            with d3:
                st.metric("Max Stash Elements", f"{df_diag['svc_stash_count'].max():.0f}", help="0 confirms primary buckets accommodated all symbols")
            with d4:
                st.metric("Leftover Tombstones", f"{df_diag['svc_tombstones'].max():.0f}")
        else:
            st.info("Diagnostics summary data loaded from Phase 8 trace summaries.")
