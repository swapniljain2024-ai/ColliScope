"""
ColliScope Dashboard: Section 4 — Scope & SVC-Hash
Clean, visual, concise explanation of lexical scope virtualization,
flat-versus-nested throughput degradation, and real-source cJSON results.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from dashboard.data_loader import load_synthetic_analysis, load_cjson_summary


def render_scope_and_svc():
    st.markdown("""
    <div style="margin-bottom: 16px;">
        <h2 style="margin: 0 0 4px 0; font-size: 24px; font-weight: 800; color: #263247;">
            🌲 Scope & SVC-Hash
        </h2>
        <p style="margin: 0; font-size: 14.5px; color: #68758A;">
            Evaluating lexical scope mechanics: why multi-table wrappers degrade and how SVC-Hash virtualizes scopes in a single table.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # 1. Architectural Concept Comparison (Two Crisp Cards)
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("""
        <div class="research-card" style="height: 100%; border-top: 3px solid #65A6D9;">
            <div style="font-weight: 700; font-size: 14.5px; color: #263247; margin-bottom: 4px;">
                Classical Multi-Table Wrapper
            </div>
            <div style="font-size: 12px; color: #68758A; margin-bottom: 6px;">
                <code>std::vector&lt;std::unique_ptr&lt;HashTable&gt;&gt;</code>
            </div>
            <p style="font-size: 13px; color: #68758A; line-height: 1.5; margin: 0;">
                Allocates a separate table per scope block. Outer-scope references must traverse backwards down the scope stack, incurring repeated table misses and cache line evictions.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown("""
        <div class="research-card" style="height: 100%; border-top: 3px solid #39A985;">
            <div style="font-weight: 700; font-size: 14.5px; color: #263247; margin-bottom: 4px;">
                Proposed SVC-Hash Architecture
            </div>
            <div style="font-size: 12px; color: #68758A; margin-bottom: 6px;">
                <code>Unified 4-Way Bucketed Array + Stash</code>
            </div>
            <p style="font-size: 13px; color: #68758A; line-height: 1.5; margin: 0;">
                Virtualizes all scopes in one table via composite keys <code>(identifier, scope_id)</code>. Uses 4 slots per bucket and an 8-slot stash to absorb collisions, with O(1) scope-exit deactivation.
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 2. Flat vs Nested Scope Performance Comparison
    st.markdown("### Flat vs Nested Scoping Performance")
    st.caption("Median throughput (k-ops/sec) in synthetic workloads (N=36 independent units) comparing single flat tables against nested lexical scopes.")

    df_synth = load_synthetic_analysis()
    base_fams = ["chaining", "cuckoo", "hopscotch", "svc_hash"]
    disp_names = ["Chaining", "Cuckoo", "Hopscotch", "SVC-Hash"]

    scope_data = []
    for bfam, dname in zip(base_fams, disp_names):
        flat_tp = df_synth[(df_synth["baseline_family"] == bfam) & (df_synth["scope_mode"] == "flat")]["tp_median"].median()
        nest_tp = df_synth[(df_synth["baseline_family"] == bfam) & (df_synth["scope_mode"] == "nested")]["tp_median"].median()
        pct_chg = ((nest_tp - flat_tp) / flat_tp * 100.0) if flat_tp > 0 else 0.0

        scope_data.append({
            "Algorithm": dname,
            "Flat TP (k-ops/s)": round(flat_tp / 1000.0, 1),
            "Nested TP (k-ops/s)": round(nest_tp / 1000.0, 1),
            "Change (%)": round(pct_chg, 1)
        })

    df_scope = pd.DataFrame(scope_data)

    chart_col, tbl_col = st.columns([2.2, 1])

    with chart_col:
        fig_scope = go.Figure()
        fig_scope.add_trace(go.Bar(
            x=df_scope["Algorithm"],
            y=df_scope["Flat TP (k-ops/s)"],
            name="Flat Scope (Single Table)",
            marker_color="#65A6D9"
        ))
        fig_scope.add_trace(go.Bar(
            x=df_scope["Algorithm"],
            y=df_scope["Nested TP (k-ops/s)"],
            name="Nested Scope (Scoped / SVC)",
            marker_color="#4F6BED"
        ))
        fig_scope.update_layout(
            barmode="group",
            template="plotly_white",
            paper_bgcolor="#FFFFFF",
            plot_bgcolor="#FFFFFF",
            font=dict(family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif", size=12, color="#263247"),
            yaxis=dict(title="Throughput (k-ops/sec)", gridcolor="#E1E7F0", linecolor="#E1E7F0"),
            xaxis=dict(linecolor="#E1E7F0"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=None),
            height=300,
            margin=dict(l=40, r=20, t=20, b=30)
        )
        st.plotly_chart(fig_scope, use_container_width=True)

    with tbl_col:
        st.markdown("<div style='font-size: 13px; font-weight: 700; color: #263247; margin-bottom: 6px;'>Scope Degradation</div>", unsafe_allow_html=True)
        st.dataframe(
            df_scope[["Algorithm", "Nested TP (k-ops/s)", "Change (%)"]],
            column_config={
                "Algorithm": "Algorithm",
                "Nested TP (k-ops/s)": st.column_config.NumberColumn("Nested TP", format="%.1f"),
                "Change (%)": st.column_config.NumberColumn("Degradation", format="%+.1f%%"),
            },
            use_container_width=True,
            hide_index=True,
            height=250
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # 3. Real-Source Case Study (cJSON v1.7.18) Inversion Result
    st.markdown("### Authentic Nested AST Case Study (cJSON v1.7.18)")
    st.caption("Authentic C code containing 1,002 operations and 128 lexical scopes extracted from cJSON AST.")

    df_cjson = load_cjson_summary()
    cjson_nest = df_cjson[df_cjson["scope_mode"] == "nested"].sort_values("throughput_ops_sec", ascending=False)

    cj_col1, cj_col2 = st.columns([1.5, 2])

    with cj_col1:
        st.markdown("""
        <div class="research-card" style="height: 100%;">
            <div style="font-weight: 700; font-size: 14px; color: #39A985; margin-bottom: 6px;">Authentic Nested AST Leader</div>
            <div style="font-size: 26px; font-weight: 800; color: #263247; margin-bottom: 4px;">734.9k op/s</div>
            <div style="font-size: 12.5px; color: #68758A; line-height: 1.5;">
                • <strong>1.76x</strong> over Scoped Chaining (418.4k)<br>
                • <strong>2.64x</strong> over Scoped Hopscotch (278.5k)<br>
                • <strong>3.71x</strong> over Scoped Cuckoo (197.9k)<br>
                • Peak memory: <strong>8.0 KB</strong> (lowest of all)
            </div>
        </div>
        """, unsafe_allow_html=True)

    with cj_col2:
        fig_cj = go.Figure()
        fig_cj.add_trace(go.Bar(
            x=cjson_nest["algorithm_name"],
            y=cjson_nest["throughput_ops_sec"] / 1000.0,
            marker_color=["#39A985", "#4F6BED", "#8B79D9", "#E8A34A"]
        ))
        fig_cj.update_layout(
            template="plotly_white",
            paper_bgcolor="#FFFFFF",
            plot_bgcolor="#FFFFFF",
            font=dict(family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif", size=12, color="#263247"),
            yaxis=dict(title="Throughput (k-ops/sec)", gridcolor="#E1E7F0", linecolor="#E1E7F0"),
            xaxis=dict(linecolor="#E1E7F0"),
            height=200,
            margin=dict(l=40, r=20, t=10, b=30)
        )
        st.plotly_chart(fig_cj, use_container_width=True)

    # 4. Expanders for Deep Dives and Caveats
    with st.expander("🔬 Scope Degradation Mechanism & Cache Dynamics", expanded=False):
        st.markdown("""
        **Why Multi-Table Wrappers Degrade by 61%–64%:**
        1. **Sequential Miss Cascades:** An identifier declared in outer Scope 0 but referenced inside Scope 3 triggers 3 successive table misses (`Scope 3 -> Scope 2 -> Scope 1 -> Scope 0`).
        2. **Heap Indirection:** Multiple small hash tables cause scattered heap allocations, destroying hardware prefetcher efficiency.
        3. **SVC-Hash Virtualization:** Directly hashes `(identifier, active_scope)` into 2 candidate buckets. If missing, hashes parent scope `(identifier, parent_scope)`. Bounded by 4 slots per bucket, preventing full-table linear scans.
        """)

    with st.expander("📐 Scientific Boundary Conditions & Limitations", expanded=False):
        st.markdown("""
        **Objective Assessment:**
        - **Flat Code Advantage of Baselines:** On flat code without scoping, Separate Chaining (1.82M op/s) and Hopscotch (1.84M op/s) lead due to L1 cache residency for frequently referenced symbols. SVC-Hash is optimized specifically for lexically scoped languages.
        - **Single Real-Source Codebase:** The cJSON benchmark evaluates **one software codebase** under **two representations** (flat vs AST). It serves as descriptive case-study evidence.
        - **Lookup Depth:** Nested lookups remain bounded by the active lexical block depth (maximum depth 6 in cJSON).
        """)
