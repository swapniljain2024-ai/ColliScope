"""
ColliScope Dashboard: Page 6 - Scope Analysis
Evaluating flat single tables vs nested lexical scopes, baseline wrapper degradation, and virtualization benefits.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from dashboard.data_loader import load_synthetic_analysis, load_cjson_summary


def render_scope_analysis():
    st.title("Scope Analysis: Flat vs Nested Scoping")
    st.markdown("Examine the computational overhead of lexical scoping and compare multi-table wrapper architectures against virtualized single-table scoping.")

    # Critical Methodological Disclaimer
    st.info("""
    **Methodological Context & Limitation:**  
    Comparing **flat** vs **nested** workloads is **not** an isolated single-factor causal experiment.  
    In compiler workloads, introducing nested lexical scopes changes the underlying trace characteristics: it adds scope enter/exit commands, introduces local identifier shadowing, and limits symbol lifetimes. Therefore, observed differences reflect the combined effect of scope mechanics and authentic lexical symbol behavior.
    """)

    df_synth = load_synthetic_analysis()
    df_cjson = load_cjson_summary()

    st.subheader("1. Synthetic Workloads: Scope Degradation")

    # Compute median throughput per algorithm in flat vs nested
    base_fams = ["chaining", "cuckoo", "hopscotch", "svc_hash"]
    disp_names = ["Chaining", "Cuckoo", "Hopscotch", "SVC-Hash"]

    scope_perf = []
    for bfam, dname in zip(base_fams, disp_names):
        flat_tp = df_synth[(df_synth["baseline_family"] == bfam) & (df_synth["scope_mode"] == "flat")]["tp_median"].median()
        nest_tp = df_synth[(df_synth["baseline_family"] == bfam) & (df_synth["scope_mode"] == "nested")]["tp_median"].median()
        flat_mem = df_synth[(df_synth["baseline_family"] == bfam) & (df_synth["scope_mode"] == "flat")]["peak_memory_kb_median"].median()
        nest_mem = df_synth[(df_synth["baseline_family"] == bfam) & (df_synth["scope_mode"] == "nested")]["peak_memory_kb_median"].median()
        
        pct_tp_chg = ((nest_tp - flat_tp) / flat_tp * 100.0) if flat_tp > 0 else 0.0

        scope_perf.append({
            "Algorithm Family": dname,
            "Flat Throughput (k-ops/s)": flat_tp / 1000.0,
            "Nested Throughput (k-ops/s)": nest_tp / 1000.0,
            "Throughput Change (%)": pct_tp_chg,
            "Flat Memory (KB)": flat_mem,
            "Nested Memory (KB)": nest_mem
        })

    df_scope = pd.DataFrame(scope_perf)

    # Bar chart of degradation
    col1, col2 = st.columns(2)
    with col1:
        fig_tp = go.Figure()
        fig_tp.add_trace(go.Bar(
            x=df_scope["Algorithm Family"],
            y=df_scope["Flat Throughput (k-ops/s)"],
            name="Flat Scope (Single Table)",
            marker_color="#4575b4"
        ))
        fig_tp.add_trace(go.Bar(
            x=df_scope["Algorithm Family"],
            y=df_scope["Nested Throughput (k-ops/s)"],
            name="Nested Scope (Scoped Wrapper / SVC)",
            marker_color="#d73027"
        ))
        fig_tp.update_layout(
            barmode="group",
            template="plotly_white",
            title="Synthetic Throughput: Flat vs Nested",
            yaxis_title="Median Throughput (kilo-ops / sec)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=40, r=40, t=50, b=40)
        )
        st.plotly_chart(fig_tp, use_container_width=True)

    with col2:
        fig_mem = go.Figure()
        fig_mem.add_trace(go.Bar(
            x=df_scope["Algorithm Family"],
            y=df_scope["Flat Memory (KB)"],
            name="Flat Scope Memory (KB)",
            marker_color="#74add1"
        ))
        fig_mem.add_trace(go.Bar(
            x=df_scope["Algorithm Family"],
            y=df_scope["Nested Memory (KB)"],
            name="Nested Scope Memory (KB)",
            marker_color="#fdae61"
        ))
        fig_mem.update_layout(
            barmode="group",
            template="plotly_white",
            title="Synthetic Peak Memory: Flat vs Nested",
            yaxis_title="Peak Memory (KB) [Lower is better]",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=40, r=40, t=50, b=40)
        )
        st.plotly_chart(fig_mem, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Scope Performance Table
    st.dataframe(
        df_scope,
        column_config={
            "Algorithm Family": "Algorithm",
            "Flat Throughput (k-ops/s)": st.column_config.NumberColumn("Flat TP (k-ops/s)", format="%.1f"),
            "Nested Throughput (k-ops/s)": st.column_config.NumberColumn("Nested TP (k-ops/s)", format="%.1f"),
            "Throughput Change (%)": st.column_config.NumberColumn("Degradation (%)", format="%+.1f%%"),
            "Flat Memory (KB)": st.column_config.NumberColumn("Flat Mem (KB)", format="%.1f"),
            "Nested Memory (KB)": st.column_config.NumberColumn("Nested Mem (KB)", format="%.1f"),
        },
        use_container_width=True,
        hide_index=True
    )

    st.markdown("---")

    # 2. Real-Source cJSON Contrast
    st.subheader("2. Real-Source cJSON: Flat vs Authentic Nested Scope Inversion")
    st.markdown("In real compiler AST code (cJSON v1.7.18), the relative performance between baselines and SVC-Hash completely inverts between flat and nested representations:")

    cjson_flat = df_cjson[df_cjson["scope_mode"] == "flat"].set_index("baseline_family")
    cjson_nest = df_cjson[df_cjson["scope_mode"] == "nested"].set_index("baseline_family")

    cjson_contrast = []
    for bfam, dname in [("chaining", "Chaining / Scoped"), ("cuckoo", "Cuckoo / Scoped"), ("hopscotch", "Hopscotch / Scoped"), ("svc_hash", "SVC-Hash")]:
        f_tp = cjson_flat.loc[bfam, "throughput_ops_sec"] if bfam in cjson_flat.index else 0
        n_tp = cjson_nest.loc[bfam, "throughput_ops_sec"] if bfam in cjson_nest.index else 0
        f_mem = cjson_flat.loc[bfam, "peak_memory_kb"] if bfam in cjson_flat.index else 0
        n_mem = cjson_nest.loc[bfam, "peak_memory_kb"] if bfam in cjson_nest.index else 0

        cjson_contrast.append({
            "Algorithm": dname,
            "cJSON Flat TP (k-ops/s)": f_tp / 1000.0,
            "cJSON Nested TP (k-ops/s)": n_tp / 1000.0,
            "Nested TP Ratio (SVC / Algo)": (cjson_nest.loc["svc_hash", "throughput_ops_sec"] / n_tp) if n_tp > 0 else 1.0,
            "cJSON Nested Memory (KB)": n_mem
        })

    st.dataframe(
        pd.DataFrame(cjson_contrast),
        column_config={
            "Algorithm": "Algorithm",
            "cJSON Flat TP (k-ops/s)": st.column_config.NumberColumn("cJSON Flat TP", format="%.1f"),
            "cJSON Nested TP (k-ops/s)": st.column_config.NumberColumn("cJSON Nested TP", format="%.1f"),
            "Nested TP Ratio (SVC / Algo)": st.column_config.NumberColumn("SVC Advantage on Nested", format="%.2fx"),
            "cJSON Nested Memory (KB)": st.column_config.NumberColumn("Peak Memory (KB)", format="%.1f KB")
        },
        use_container_width=True,
        hide_index=True
    )
