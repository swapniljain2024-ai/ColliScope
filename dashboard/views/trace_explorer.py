"""
ColliScope Dashboard: Page 9 - Trace / Operation Explorer
Drill-down into individual workload traces, command statistics, and algorithm performance.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from dashboard.data_loader import load_trace_summary, load_operation_composition


def render_trace_explorer():
    st.title("Trace / Operation Explorer")
    st.markdown("Drill down into any of the 38 authoritative workload traces to inspect its command profile, symbol statistics, and algorithm execution results.")

    df_summary = load_trace_summary()
    df_comp = load_operation_composition()

    trace_list = sorted(df_comp["trace_name"].unique())
    selected_trace = st.selectbox("Select Workload Trace", options=trace_list, index=0)

    trace_comp = df_comp[df_comp["trace_name"] == selected_trace].iloc[0]
    trace_alg_rows = df_summary[df_summary["trace_name"] == selected_trace]

    # Metadata cards
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Category", trace_comp["category"].capitalize())
    with c2:
        st.metric("Identifier Distribution", trace_comp["identifier_distribution"].capitalize())
    with c3:
        st.metric("Scope Mode", trace_comp["scope_mode"].capitalize())
    with c4:
        st.metric("Nominal Mix", trace_comp["nominal_workload_type"].capitalize())

    st.markdown("---")

    # Command Profile & Realized Composition
    st.subheader("Operation Composition Profile")
    p1, p2, p3, p4 = st.columns(4)
    with p1:
        st.metric("Total Operations", f"{trace_comp['total_operations']:,}")
    with p2:
        st.metric("Declarations", f"{trace_comp['declaration_count']:,} ({trace_comp['pct_declaration']:.1f}%)")
    with p3:
        st.metric("References", f"{trace_comp['reference_count']:,} ({trace_comp['pct_reference']:.1f}%)")
    with p4:
        st.metric("Scope Operations", f"{trace_comp['enter_scope_count'] + trace_comp['exit_scope_count']:,} ({trace_comp['pct_scope_ops']:.1f}%)")

    # Pie/Donut Chart of operations
    donut_fig = go.Figure(data=[go.Pie(
        labels=["DECLARE", "REFERENCE", "SCOPE ENTER/EXIT"],
        values=[trace_comp["declaration_count"], trace_comp["reference_count"], trace_comp["enter_scope_count"] + trace_comp["exit_scope_count"]],
        hole=.45,
        marker=dict(colors=["#1b9e77", "#d95f02", "#7570b3"])
    )])
    donut_fig.update_layout(
        title=f"Operation Proportions: {selected_trace}",
        template="plotly_white",
        height=320,
        margin=dict(l=20, r=20, t=50, b=20)
    )
    st.plotly_chart(donut_fig, use_container_width=True)

    st.markdown("---")

    # Algorithm Performance on this trace
    st.subheader(f"Algorithm Benchmark Results on {selected_trace}")

    perf_fig = px.bar(
        trace_alg_rows,
        x="algorithm_name",
        y="tp_median",
        color="algorithm_name",
        color_discrete_map={
            "chaining": "#1f77b4", "scoped_chaining": "#1f77b4",
            "cuckoo": "#ff7f0e", "scoped_cuckoo": "#ff7f0e",
            "hopscotch": "#2ca02c", "scoped_hopscotch": "#2ca02c",
            "svc_hash": "#d62728"
        },
        title=f"Median Throughput across Algorithms on {selected_trace}"
    )
    perf_fig.update_layout(template="plotly_white", showlegend=False, yaxis_title="Throughput (op/s)", margin=dict(l=40, r=40, t=50, b=40))
    st.plotly_chart(perf_fig, use_container_width=True)

    # Detailed Table
    st.dataframe(
        trace_alg_rows[[
            "algorithm_name", "tp_median", "tp_mean", "tp_cv_pct",
            "total_time_median_ns", "insert_p50_median_ns", "lookup_p50_median_ns",
            "peak_memory_kb_median", "peak_load_factor_median",
            "successful_references", "failed_references"
        ]],
        column_config={
            "algorithm_name": "Algorithm",
            "tp_median": st.column_config.NumberColumn("Median TP (op/s)", format="%.0f"),
            "tp_mean": st.column_config.NumberColumn("Mean TP (op/s)", format="%.0f"),
            "tp_cv_pct": st.column_config.NumberColumn("CV (%)", format="%.1f%%"),
            "total_time_median_ns": st.column_config.NumberColumn("Total Time (ns)", format="%d"),
            "insert_p50_median_ns": st.column_config.NumberColumn("Insert p50 (ns)", format="%.1f"),
            "lookup_p50_median_ns": st.column_config.NumberColumn("Lookup p50 (ns)", format="%.1f"),
            "peak_memory_kb_median": st.column_config.NumberColumn("Peak Mem (KB)", format="%.2f"),
            "peak_load_factor_median": st.column_config.NumberColumn("Peak LF", format="%.3f"),
            "successful_references": st.column_config.NumberColumn("Hits", format="%d"),
            "failed_references": st.column_config.NumberColumn("Misses", format="%d"),
        },
        use_container_width=True,
        hide_index=True
    )
