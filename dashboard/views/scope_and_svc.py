"""
ColliScope Dashboard: Section 4 — Scope & SVC-Hash
Comprehensive explanation of lexical scoping mechanics, multi-table wrapper degradation,
SVC-Hash composite-key virtualization architecture, and empirical performance impact.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from dashboard.data_loader import load_synthetic_analysis, load_cjson_summary

# Standardized palette
ALGO_PALETTE = {
    "chaining": "#2563eb",
    "Chaining": "#2563eb",
    "cuckoo": "#f97316",
    "Cuckoo": "#f97316",
    "hopscotch": "#059669",
    "Hopscotch": "#059669",
    "svc_hash": "#dc2626",
    "SVC-Hash": "#dc2626"
}


def render_scope_and_svc():
    st.markdown("""
    <div style="margin-bottom: 20px;">
        <h2 style="margin: 0 0 6px 0; font-size: 26px; font-weight: 800;">
            🌲 Scope Analysis & SVC-Hash Architecture
        </h2>
        <p style="margin: 0; font-size: 14.5px; opacity: 0.85;">
            Understand the architectural divergence between classical multi-table wrapper stacks 
            and virtualized single-table hashing under lexical nesting, variable shadowing, and scope exits.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # 1. Architectural Contrast: Multi-Table vs Virtualized Table
    st.markdown("### 1. Two Architectural Paradigms for Lexical Scoping")
    arch_col1, arch_col2 = st.columns(2)

    with arch_col1:
        st.markdown("""
        <div class="research-card" style="height: 100%; border-top: 3px solid #2563eb;">
            <h4 style="margin: 0 0 8px 0; color: #2563eb; font-size: 16px;">
                Classical Paradigm: Multi-Table Wrapper Stack
            </h4>
            <div style="font-size: 12.5px; opacity: 0.8; margin-bottom: 10px;">
                <code>std::vector&lt;std::unique_ptr&lt;HashTable&gt;&gt; scope_stack;</code>
            </div>
            <ul style="font-size: 13px; line-height: 1.6; padding-left: 18px; margin: 0;">
                <li><strong>Enter Scope:</strong> Allocates a new heap-allocated hash table and pushes it onto the scope stack.</li>
                <li><strong>Declaration:</strong> Inserts strictly into <code>scope_stack.back()</code>.</li>
                <li><strong>Lookup Traversal:</strong> Probes the innermost table. On a miss, traverses backwards: <code>stack[depth-1]</code> &rarr; <code>stack[depth-2]</code> &rarr; ... &rarr; <code>stack[0]</code>.</li>
                <li><strong>Exit Scope:</strong> Deallocates and pops the active table.</li>
                <li><strong style="color: #ef4444;">Bottleneck:</strong> Outer-scope references incur multiple sequential table misses, causing CPU pipeline stalls and cache misses.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    with arch_col2:
        st.markdown("""
        <div class="research-card" style="height: 100%; border-top: 3px solid #dc2626;">
            <h4 style="margin: 0 0 8px 0; color: #dc2626; font-size: 16px;">
                Proposed Paradigm: SVC-Hash Virtualized Table
            </h4>
            <div style="font-size: 12.5px; opacity: 0.8; margin-bottom: 10px;">
                <code>SvcHashTable (Unified 4-Way Bucketed Array + Stash)</code>
            </div>
            <ul style="font-size: 13px; line-height: 1.6; padding-left: 18px; margin: 0;">
                <li><strong>Composite Key Hashing:</strong> Hashes the pair <code>(identifier, scope_id)</code> via 64-bit FNV-1a. Shadowed symbols naturally map to distinct candidate buckets.</li>
                <li><strong>Candidate Buckets:</strong> Computes 2 candidate bucket indices. Each bucket holds <strong>4 slots</strong> to absorb local collisions without relocation.</li>
                <li><strong>8-Slot Stash:</strong> Absorbs worst-case displacements when recursive kick depth reaches the limit.</li>
                <li><strong>O(1) Scope Exit:</strong> Marks slots matching <code>scope_id</code> as tombstoned without deallocating or rebalancing tables.</li>
                <li><strong style="color: #10b981;">Benefit:</strong> Eliminates table wrapper indirection and bounds peak memory footprint.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 2. Scope Degradation Phenomenon in Synthetic Workloads
    st.markdown("### 2. The Scope Degradation Phenomenon")
    st.markdown("""
    <div class="research-callout" style="margin-top: 4px; margin-bottom: 16px; font-size: 13.5px;">
        <strong>Methodological Note:</strong> Comparing flat vs nested workloads is not an isolated single-factor causal experiment. 
        Introducing lexical block scopes adds scope enter/exit events, introduces identifier shadowing, and limits symbol lifetimes. 
        Observed throughput differences reflect the combined impact of scope mechanics and authentic compiler symbol lifetimes.
    </div>
    """, unsafe_allow_html=True)

    df_synth = load_synthetic_analysis()

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
            "Algorithm": dname,
            "Flat Throughput (k-ops/s)": flat_tp / 1000.0,
            "Nested Throughput (k-ops/s)": nest_tp / 1000.0,
            "Throughput Change (%)": pct_tp_chg,
            "Flat Memory (KB)": flat_mem,
            "Nested Memory (KB)": nest_mem
        })

    df_scope = pd.DataFrame(scope_perf)

    c1, c2 = st.columns(2)
    with c1:
        fig_tp = go.Figure()
        fig_tp.add_trace(go.Bar(
            x=df_scope["Algorithm"],
            y=df_scope["Flat Throughput (k-ops/s)"],
            name="Flat Scope (Single Table)",
            marker_color="#2563eb"
        ))
        fig_tp.add_trace(go.Bar(
            x=df_scope["Algorithm"],
            y=df_scope["Nested Throughput (k-ops/s)"],
            name="Nested Scope (Scoped Wrapper / SVC)",
            marker_color="#f97316"
        ))
        fig_tp.update_layout(
            barmode="group",
            template="plotly_white",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            title="Throughput Impact of Lexical Scoping (Synthetic N=36)",
            yaxis_title="Median Throughput (k-ops/sec)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=40, r=40, t=50, b=40)
        )
        st.plotly_chart(fig_tp, use_container_width=True)

    with c2:
        fig_mem = go.Figure()
        fig_mem.add_trace(go.Bar(
            x=df_scope["Algorithm"],
            y=df_scope["Flat Memory (KB)"],
            name="Flat Scope Memory (KB)",
            marker_color="#059669"
        ))
        fig_mem.add_trace(go.Bar(
            x=df_scope["Algorithm"],
            y=df_scope["Nested Memory (KB)"],
            name="Nested Scope Memory (KB)",
            marker_color="#d97706"
        ))
        fig_mem.update_layout(
            barmode="group",
            template="plotly_white",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            title="Peak Memory Impact of Lexical Scoping",
            yaxis_title="Peak Memory (KB) [Lower is better]",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=40, r=40, t=50, b=40)
        )
        st.plotly_chart(fig_mem, use_container_width=True)

    # Degradation Table
    st.dataframe(
        df_scope,
        column_config={
            "Algorithm": "Algorithm Family",
            "Flat Throughput (k-ops/s)": st.column_config.NumberColumn("Flat TP (k-ops/s)", format="%.1f"),
            "Nested Throughput (k-ops/s)": st.column_config.NumberColumn("Nested TP (k-ops/s)", format="%.1f"),
            "Throughput Change (%)": st.column_config.NumberColumn("Change (%)", format="%+.1f%%"),
            "Flat Memory (KB)": st.column_config.NumberColumn("Flat Mem (KB)", format="%.1f"),
            "Nested Memory (KB)": st.column_config.NumberColumn("Nested Mem (KB)", format="%.1f")
        },
        use_container_width=True,
        hide_index=True
    )

    st.markdown("---")

    # 3. Real-Source Case Study Inversion (cJSON v1.7.18)
    st.markdown("### 3. Real-Source Case Study Inversion (cJSON AST)")
    st.caption("Demonstrating how authentic compiler AST traces invert performance rankings relative to flat synthetic benchmarks.")

    df_cjson = load_cjson_summary()
    cjson_nest = df_cjson[df_cjson["scope_mode"] == "nested"].sort_values("throughput_ops_sec", ascending=False)
    cjson_flat = df_cjson[df_cjson["scope_mode"] == "flat"].sort_values("throughput_ops_sec", ascending=False)

    rc1, rc2 = st.columns([3, 2])
    with rc1:
        fig_cj = go.Figure()
        fig_cj.add_trace(go.Bar(
            x=cjson_nest["algorithm_name"],
            y=cjson_nest["throughput_ops_sec"] / 1000.0,
            name="Authentic Nested AST (128 Scopes)",
            marker_color="#dc2626"
        ))
        fig_cj.add_trace(go.Bar(
            x=cjson_flat["algorithm_name"],
            y=cjson_flat["throughput_ops_sec"] / 1000.0,
            name="Flat Compilation Unit",
            marker_color="#2563eb"
        ))
        fig_cj.update_layout(
            barmode="group",
            template="plotly_white",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            title="cJSON Throughput: Authentic Nested vs Flat Compilation Unit",
            yaxis_title="Throughput (kilo-ops / sec)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=40, r=40, t=50, b=40)
        )
        st.plotly_chart(fig_cj, use_container_width=True)

    with rc2:
        st.markdown("""
        <div class="research-card" style="height: 100%;">
            <h4 style="margin-top: 0; color: #dc2626; font-size: 15px;">cJSON Nested Empirical Inversion</h4>
            <ul style="font-size: 13px; line-height: 1.6; padding-left: 18px; margin: 0;">
                <li><strong>SVC-Hash Leads Authentic Nested Code:</strong> Reaches <strong>734.9k op/s</strong> on real Clang AST traces.</li>
                <li><strong>1.76x Speedup over Scoped Chaining:</strong> 734.9k vs 418.4k op/s.</li>
                <li><strong>2.64x Speedup over Scoped Hopscotch:</strong> 734.9k vs 278.5k op/s.</li>
                <li><strong>3.71x Speedup over Scoped Cuckoo:</strong> 734.9k vs 197.9k op/s.</li>
                <li><strong>Minimal Memory Footprint:</strong> Requires only <strong>8.0 KB</strong> heap memory compared to 10.9 KB for Scoped Chaining.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # 4. Objective Boundary Conditions & Empirical Limitations
    st.markdown("### 4. Objective Assessment & Scientific Boundary Conditions")
    st.markdown("""
    <div class="research-callout-warning" style="margin: 0; font-size: 13.5px; line-height: 1.6;">
        <strong>Scientific Limitations:</strong><br>
        • <strong>Not Universally Superior:</strong> On flat code with Zipfian reference distributions, Separate Chaining (1.82M op/s) 
        and Hopscotch (1.84M op/s) outperform SVC-Hash (1.29M op/s). Closed addressing retains hot symbols in the CPU L1 cache line without hash recomputation.<br>
        • <strong>Single Real-World Project:</strong> The cJSON case study evaluates <strong>ONE software codebase</strong> under 
        <strong>TWO scope representations</strong> (flat translation unit vs authentic AST block scopes). It provides descriptive case-study evidence, not inferential proof across all programming languages.<br>
        • <strong>No Constant-Time Guarantees:</strong> While lookups check at most candidate slots along the parent scope chain, 
        nested lookup depth remains bounded by the active lexical block depth (max depth 6 in cJSON).
    </div>
    """, unsafe_allow_html=True)
