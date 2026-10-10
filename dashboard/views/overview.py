"""
ColliScope Dashboard: Section 1 — Overview
Concise, light, professional landing page designed for rapid 10-15 second faculty scanning.
"""

import streamlit as st
import plotly.express as px
import pandas as pd
from dashboard.data_loader import load_trace_summary

# Standard light palette
ALGO_PALETTE = {
    "Chaining / Scoped": "#4F6BED",
    "Cuckoo / Scoped": "#E8A34A",
    "Hopscotch / Scoped": "#8B79D9",
    "SVC-Hash": "#39A985"
}


def render_overview():
    # Header & One-Sentence Pitch
    st.markdown("""
    <div style="margin-bottom: 18px;">
        <h1 style="margin: 0 0 4px 0; font-size: 26px; font-weight: 800; color: #263247;">
            ColliScope
        </h1>
        <p style="margin: 0; font-size: 15px; color: #68758A; font-weight: 400;">
            Workload-aware evaluation and scope-aware cuckoo hashing for compiler symbol tables.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # 1. Five Core KPI Cards
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    with kpi1:
        st.metric(label="Authoritative Traces", value="38", help="36 synthetic traces + 2 authentic cJSON AST traces")
    with kpi2:
        st.metric(label="Synthetic Conditions", value="12", help="2 identifier distributions × 2 scope modes × 3 operation mixes")
    with kpi3:
        st.metric(label="Algorithm Families", value="4", help="Separate Chaining, Cuckoo Hashing, Hopscotch Hashing, SVC-Hash")
    with kpi4:
        st.metric(label="Measured Trials", value="1,520", help="152 trace-algorithm pairs × 10 repetitions (+456 unmeasured warmups)")
    with kpi5:
        st.metric(label="Nested SVC Speedup", value="+70.8%", help="Median throughput speedup over Scoped Cuckoo in nested synthetic workloads (Holm p = 0.00193)")

    st.markdown("<br>", unsafe_allow_html=True)

    # 2. Hero Interactive Lab CTA
    cta_col1, cta_col2 = st.columns([3, 1])
    with cta_col1:
        st.markdown("""
        <div style="background-color: #FFFFFF; border: 1px solid #E1E7F0; border-left: 4px solid #4F6BED; border-radius: 6px; padding: 12px 16px;">
            <div style="font-weight: 700; font-size: 14px; color: #263247;">Interactive Symbol Table Lab</div>
            <div style="font-size: 12.5px; color: #68758A; margin-top: 2px;">
                Step through lexical scope entry/exit, variable shadowing, duplicate rejection, and live bucket slot states.
            </div>
        </div>
        """, unsafe_allow_html=True)
    with cta_col2:
        if st.button("🚀 Open Interactive Lab", use_container_width=True):
            st.session_state["nav_selection"] = "2. Interactive Symbol Table Lab"
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # 3. Clean Primary Comparative Visualization
    st.markdown("### Throughput Comparison Across Workload Families")
    st.caption("Median throughput (kilo-ops/sec) under 10 MHz monotonic hardware timing across flat and nested scopes.")

    df_summary = load_trace_summary()

    fam_order = [
        ("Random Flat", ("random", "flat")),
        ("Random Nested", ("random", "nested")),
        ("Zipfian Flat", ("frequency-matched", "flat")),
        ("Zipfian Nested", ("frequency-matched", "nested")),
        ("cJSON Flat AST", ("real", "flat")),
        ("cJSON Nested AST", ("real", "nested"))
    ]

    summary_rows = []
    for flabel, (dist, scope) in fam_order:
        sub = df_summary[(df_summary["identifier_distribution"] == dist) & (df_summary["scope_mode"] == scope)]
        for bfam in ["chaining", "cuckoo", "hopscotch", "svc_hash"]:
            sub_b = sub[sub["baseline_family"] == bfam]
            if not sub_b.empty:
                disp_fam = "Chaining / Scoped" if bfam == "chaining" else ("Cuckoo / Scoped" if bfam == "cuckoo" else ("Hopscotch / Scoped" if bfam == "hopscotch" else "SVC-Hash"))
                summary_rows.append({
                    "Workload Family": flabel,
                    "Algorithm": disp_fam,
                    "Throughput (k-ops/s)": round(sub_b["tp_median"].median() / 1000.0, 1)
                })

    df_plot = pd.DataFrame(summary_rows)

    fig = px.bar(
        df_plot,
        x="Workload Family",
        y="Throughput (k-ops/s)",
        color="Algorithm",
        barmode="group",
        color_discrete_map=ALGO_PALETTE
    )
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font=dict(family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif", size=12, color="#263247"),
        margin=dict(l=40, r=20, t=25, b=40),
        height=350,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=None),
        xaxis=dict(title=None, showgrid=False, linecolor="#E1E7F0"),
        yaxis=dict(title="Median Throughput (k-ops/sec)", gridcolor="#E1E7F0", linecolor="#E1E7F0")
    )
    st.plotly_chart(fig, use_container_width=True)

    # 4. Three Concise Takeaways (One-liners)
    st.markdown("### Key Takeaways")
    t1, t2, t3 = st.columns(3)

    with t1:
        st.markdown("""
        <div class="research-card" style="height: 100%; border-top: 3px solid #4F6BED;">
            <div style="font-weight: 700; font-size: 14px; color: #263247; margin-bottom: 4px;">1. Flat Code Cache Locality</div>
            <p style="font-size: 13px; color: #68758A; margin: 0; line-height: 1.5;">
                On flat workloads, <strong>Chaining (1.82M op/s)</strong> and <strong>Hopscotch (1.84M op/s)</strong> lead due to CPU L1 cache residency for hot identifiers.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with t2:
        st.markdown("""
        <div class="research-card" style="height: 100%; border-top: 3px solid #E6B65C;">
            <div style="font-weight: 700; font-size: 14px; color: #263247; margin-bottom: 4px;">2. Multi-Table Wrapper Penalty</div>
            <p style="font-size: 13px; color: #68758A; margin: 0; line-height: 1.5;">
                Traditional scope-stack wrappers degrade by <strong>61%–64%</strong> under nested scopes because outer references incur multiple sequential table misses.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with t3:
        st.markdown("""
        <div class="research-card" style="height: 100%; border-top: 3px solid #39A985;">
            <div style="font-weight: 700; font-size: 14px; color: #263247; margin-bottom: 4px;">3. Authentic Nested Inversion</div>
            <p style="font-size: 13px; color: #68758A; margin: 0; line-height: 1.5;">
                On authentic nested cJSON AST code, <strong>SVC-Hash achieves 734.9k op/s</strong> (1.76x–3.71x over baselines) while maintaining the lowest memory (8.0 KB).
            </p>
        </div>
        """, unsafe_allow_html=True)

    # 5. Background in Expander (clean, non-cluttering)
    with st.expander("📖 Background & Problem Formulation", expanded=False):
        st.markdown("""
        Compiler frontends require fast symbol declaration and lookup under block scoping, identifier shadowing, and skewed Zipfian identifier reference distributions.
        
        **Four Evaluated Approaches:**
        1. **Separate Chaining (Baseline):** Industry standard; linked-list closed addressing. High flat cache locality, but pointer chasing and heap fragmentation.
        2. **Cuckoo Hashing (Baseline):** 2-choice open addressing with O(1) worst-case lookups, but cascading relocation kicks under dense declarations.
        3. **Hopscotch Hashing (Baseline):** Open addressing constrained to a 32-slot neighborhood bitmask for high cache locality.
        4. **SVC-Hash (Proposed):** Scope-virtualized single table using composite-key tagging `(identifier, scope_id)`, 4 slots/bucket, an 8-slot overflow stash, and O(1) tombstone deactivation on scope exits.
        """)
