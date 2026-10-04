"""
ColliScope Dashboard: Page 4 - Algorithm Comparison
Interactive cross-algorithm benchmarking across throughput, latencies, memory, and load factor.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from dashboard.data_loader import load_trace_summary


def render_algorithm_comparison():
    st.title("Algorithm Comparison")
    st.markdown("Compare the performance characteristics of collision-resolution techniques and scoped variants across multiple evaluation metrics.")

    df_summary = load_trace_summary()

    # Metric mapping
    metrics_map = {
        "Throughput (k-ops/sec)": ("tp_median", 1000.0, "Kilo-Operations / Second (Higher is better)"),
        "Total Time (us)": ("total_time_median_ns", 1000.0, "Microseconds (Lower is better)"),
        "Insert Latency p50 (ns)": ("insert_p50_median_ns", 1.0, "Nanoseconds (Lower is better)"),
        "Insert Latency p95 (ns)": ("insert_p95_median_ns", 1.0, "Nanoseconds (Lower is better)"),
        "Insert Latency p99 (ns)": ("insert_p99_median_ns", 1.0, "Nanoseconds (Lower is better)"),
        "Lookup Latency p50 (ns)": ("lookup_p50_median_ns", 1.0, "Nanoseconds (Lower is better)"),
        "Lookup Latency p95 (ns)": ("lookup_p95_median_ns", 1.0, "Nanoseconds (Lower is better)"),
        "Lookup Latency p99 (ns)": ("lookup_p99_median_ns", 1.0, "Nanoseconds (Lower is better)"),
        "Peak Memory (KB)": ("peak_memory_kb_median", 1.0, "Kilobytes (Lower is better)"),
        "Peak Load Factor": ("peak_load_factor_median", 1.0, "Observed Load Factor (Output Metric)")
    }

    # Control row
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        sel_metric_label = st.selectbox("Primary Evaluation Metric", options=list(metrics_map.keys()), index=0)
    with c2:
        sel_scope = st.selectbox("Scope Mode Filter", options=["All Scopes", "Flat Only", "Nested Only"], index=0)
    with c3:
        sel_category = st.selectbox("Dataset Filter", options=["All Datasets", "Synthetic Only", "Real-Source Only"], index=0)

    col_name, scale, axis_title = metrics_map[sel_metric_label]

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

    # Algorithm multiselect
    available_algs = sorted(filtered["algorithm_name"].unique())
    sel_algs = st.multiselect("Select Algorithms to Display", options=available_algs, default=available_algs)
    filtered = filtered[filtered["algorithm_name"].isin(sel_algs)]

    # Compute scaled metric
    filtered["display_val"] = filtered[col_name] / scale

    st.markdown("---")

    # Primary Visualization
    st.subheader(f"{sel_metric_label} Distribution by Algorithm Family")

    chart_type = st.radio("Visualization Format", options=["Box Plot (Variance & Spread)", "Bar Chart (Condition Means)"], horizontal=True)

    alg_colors = {
        "chaining": "#1f77b4",
        "cuckoo": "#ff7f0e",
        "hopscotch": "#2ca02c",
        "svc_hash": "#d62728",
        "scoped_chaining": "#1f77b4",
        "scoped_cuckoo": "#ff7f0e",
        "scoped_hopscotch": "#2ca02c"
    }

    if chart_type == "Box Plot (Variance & Spread)":
        fig = px.box(
            filtered,
            x="algorithm_name",
            y="display_val",
            color="algorithm_name",
            color_discrete_map=alg_colors,
            points="all",
            hover_data=["trace_name", "category", "scope_mode"],
            title=f"Box Plot: {sel_metric_label}"
        )
        fig.update_layout(
            template="plotly_white",
            xaxis_title="Algorithm Implementation",
            yaxis_title=axis_title,
            showlegend=False,
            margin=dict(l=40, r=40, t=50, b=40)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        # Grouped bar chart by condition
        agg_cond = filtered.groupby(["identifier_distribution", "scope_mode", "algorithm_name"])["display_val"].median().reset_index()
        agg_cond["condition"] = agg_cond["identifier_distribution"] + " (" + agg_cond["scope_mode"] + ")"

        fig = px.bar(
            agg_cond,
            x="condition",
            y="display_val",
            color="algorithm_name",
            barmode="group",
            color_discrete_map=alg_colors,
            title=f"Median {sel_metric_label} by Workload Dimension"
        )
        fig.update_layout(
            template="plotly_white",
            xaxis_title="Workload Dimension",
            yaxis_title=axis_title,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=40, r=40, t=50, b=40)
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Detailed Summary Table
    st.subheader("Statistical Summary Table by Algorithm")
    table_agg = filtered.groupby("algorithm_name")["display_val"].agg(
        Traces="count",
        Median="median",
        Mean="mean",
        Std="std",
        Min="min",
        Max="max"
    ).reset_index()

    st.dataframe(
        table_agg,
        column_config={
            "algorithm_name": "Algorithm",
            "Traces": "Traces Evaluated",
            "Median": st.column_config.NumberColumn("Median", format="%.2f"),
            "Mean": st.column_config.NumberColumn("Mean", format="%.2f"),
            "Std": st.column_config.NumberColumn("Std Dev", format="%.2f"),
            "Min": st.column_config.NumberColumn("Min", format="%.2f"),
            "Max": st.column_config.NumberColumn("Max", format="%.2f"),
        },
        use_container_width=True,
        hide_index=True
    )
