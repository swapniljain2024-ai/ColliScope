"""
ColliScope Dashboard: Page 8 - Real-Source Case Study (cJSON v1.7.18)
Descriptive case study evaluating 1 real-world project under 2 scope representations.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from dashboard.data_loader import load_cjson_summary


def render_cjson_case_study():
    st.title("Real-Source Case Study: cJSON v1.7.18")
    st.markdown("Descriptive case study evaluating compiler symbol table behavior on authentic C codebase AST traces.")

    # Provenance Card & Explicit Descriptive Label
    st.markdown("""
    <div class="research-callout" style="margin-bottom: 20px;">
        <h4 style="margin-top: 0; color: #0284c7;">cJSON v1.7.18 Software Corpus Provenance</h4>
        <p style="font-size: 14px; margin: 4px 0; opacity: 0.9;">
            <strong>Repository:</strong> <a href="https://github.com/DaveGamble/cJSON.git" target="_blank">https://github.com/DaveGamble/cJSON.git</a><br>
            <strong>Version:</strong> v1.7.18 | <strong>Commit:</strong> <code>acc76239bee01d8e9c858ae2cab296704e52d916</code> | <strong>License:</strong> MIT
        </p>
        <div style="background: rgba(2, 132, 199, 0.12); border-radius: 6px; padding: 10px; margin-top: 10px; font-size: 13.5px;">
            <strong>DESCRIPTIVE CASE STUDY ONLY:</strong> These traces represent <strong>ONE software project</strong> evaluated under <strong>TWO scope representations</strong> (flat global compilation unit vs genuine Clang AST lexical block scopes). They do not constitute independent random samples and are analyzed strictly as descriptive evidence without inferential <em>p</em>-values.
        </div>
    </div>
    """, unsafe_allow_html=True)

    df_cjson = load_cjson_summary()

    # Metrics Summary
    flat_data = df_cjson[df_cjson["scope_mode"] == "flat"]
    nest_data = df_cjson[df_cjson["scope_mode"] == "nested"]

    tab1, tab2 = st.tabs(["cJSON Authentic Nested Scope", "cJSON Flat Global Scope"])

    with tab1:
        st.subheader("Authentic Lexical Nested Representation (1,002 commands, 128 scopes)")
        st.markdown("Symbol declarations and references resolved according to authentic C lexical block nesting rules.")

        col1, col2 = st.columns([3, 2])
        with col1:
            fig_nest_tp = px.bar(
                nest_data,
                x="algorithm_name",
                y="throughput_ops_sec",
                color="algorithm_name",
                color_discrete_map={
                    "scoped_chaining": "#1f77b4",
                    "scoped_cuckoo": "#ff7f0e",
                    "scoped_hopscotch": "#2ca02c",
                    "svc_hash": "#d62728"
                },
                title="cJSON Nested Throughput (op/s) [Higher is better]"
            )
            fig_nest_tp.update_layout(template="plotly_white", showlegend=False, margin=dict(l=40, r=40, t=50, b=40))
            st.plotly_chart(fig_nest_tp, use_container_width=True)

        with col2:
            fig_nest_mem = px.bar(
                nest_data,
                x="algorithm_name",
                y="peak_memory_kb",
                color="algorithm_name",
                color_discrete_map={
                    "scoped_chaining": "#1f77b4",
                    "scoped_cuckoo": "#ff7f0e",
                    "scoped_hopscotch": "#2ca02c",
                    "svc_hash": "#d62728"
                },
                title="cJSON Nested Peak Memory (KB) [Lower is better]"
            )
            fig_nest_mem.update_layout(template="plotly_white", showlegend=False, margin=dict(l=40, r=40, t=50, b=40))
            st.plotly_chart(fig_nest_mem, use_container_width=True)

        st.markdown("""
        **Observed Performance on cJSON Nested:**
        - **SVC-Hash achieved highest throughput:** **734,949 op/s**
          - 1.76x faster than Scoped Chaining (418,421 op/s)
          - 2.64x faster than Scoped Hopscotch (278,485 op/s)
          - 3.71x faster than Scoped Cuckoo (197,883 op/s)
        - **SVC-Hash achieved lowest peak memory:** **8.0 KB**
          - 15% less memory than Scoped Chaining (9.4 KB)
          - 58% less memory than Scoped Cuckoo (19.1 KB)
          - 64% less memory than Scoped Hopscotch (22.2 KB)
        """)

    with tab2:
        st.subheader("Flat Scope Representation (1,001 commands, 0 nested scopes)")
        st.markdown("All identifiers placed in a single global table without lexical nesting overhead.")

        col1, col2 = st.columns([3, 2])
        with col1:
            fig_flat_tp = px.bar(
                flat_data,
                x="algorithm_name",
                y="throughput_ops_sec",
                color="algorithm_name",
                color_discrete_map={
                    "chaining": "#1f77b4",
                    "cuckoo": "#ff7f0e",
                    "hopscotch": "#2ca02c",
                    "svc_hash": "#d62728"
                },
                title="cJSON Flat Throughput (op/s) [Higher is better]"
            )
            fig_flat_tp.update_layout(template="plotly_white", showlegend=False, margin=dict(l=40, r=40, t=50, b=40))
            st.plotly_chart(fig_flat_tp, use_container_width=True)

        with col2:
            fig_flat_mem = px.bar(
                flat_data,
                x="algorithm_name",
                y="peak_memory_kb",
                color="algorithm_name",
                color_discrete_map={
                    "chaining": "#1f77b4",
                    "cuckoo": "#ff7f0e",
                    "hopscotch": "#2ca02c",
                    "svc_hash": "#d62728"
                },
                title="cJSON Flat Peak Memory (KB) [Lower is better]"
            )
            fig_flat_mem.update_layout(template="plotly_white", showlegend=False, margin=dict(l=40, r=40, t=50, b=40))
            st.plotly_chart(fig_flat_mem, use_container_width=True)

        st.markdown("""
        **Observed Performance on cJSON Flat:**
        - On flat global scopes with zero nesting overhead, **Separate Chaining (1.75M op/s)** and **Hopscotch (1.64M op/s)** lead due to simple array index lookups and hot L1 cache locality for frequently referenced JSON symbols.
        - SVC-Hash achieved 308,156 op/s and Cuckoo achieved 365,395 op/s.
        """)

    st.markdown("---")

    # Complete Table
    st.subheader("cJSON Benchmark Results Table")
    st.dataframe(
        df_cjson[[
            "scope_mode", "algorithm_name", "throughput_ops_sec", "total_time_us",
            "insert_p50_ns", "lookup_p50_ns", "peak_memory_kb", "peak_load_factor",
            "svc_speedup_ratio", "svc_memory_ratio"
        ]],
        column_config={
            "scope_mode": "Scope Mode",
            "algorithm_name": "Algorithm",
            "throughput_ops_sec": st.column_config.NumberColumn("Throughput (op/s)", format="%.0f"),
            "total_time_us": st.column_config.NumberColumn("Total Time (us)", format="%.1f"),
            "insert_p50_ns": st.column_config.NumberColumn("Insert p50 (ns)", format="%.1f"),
            "lookup_p50_ns": st.column_config.NumberColumn("Lookup p50 (ns)", format="%.1f"),
            "peak_memory_kb": st.column_config.NumberColumn("Peak Memory (KB)", format="%.2f"),
            "peak_load_factor": st.column_config.NumberColumn("Peak LF", format="%.3f"),
            "svc_speedup_ratio": st.column_config.NumberColumn("SVC Speedup", format="%.2fx"),
            "svc_memory_ratio": st.column_config.NumberColumn("SVC Mem Ratio", format="%.2fx"),
        },
        use_container_width=True,
        hide_index=True
    )
