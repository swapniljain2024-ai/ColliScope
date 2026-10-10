"""
ColliScope Dashboard: Section 1 — Overview
Executive overview of the compiler symbol table problem, evaluated algorithms,
key empirical findings, and primary cross-family comparison.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from dashboard.data_loader import load_trace_summary


def render_overview():
    # Hero Header Banner
    st.markdown("""
    <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%); padding: 26px 30px; border-radius: 12px; margin-bottom: 24px; border-left: 6px solid #3b82f6; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
            <div>
                <h1 style="color: #f8fafc; margin: 0 0 6px 0; font-size: 28px; font-weight: 800; letter-spacing: -0.02em;">
                    🔬 ColliScope Research Dashboard
                </h1>
                <p style="color: #94a3b8; margin: 0; font-size: 15px; font-weight: 400;">
                    Workload-Aware Evaluation and Scope-Aware Cuckoo Hashing for Compiler Symbol Tables
                </p>
            </div>
            <div>
                <span style="background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(96, 165, 250, 0.4); font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: 20px;">
                    Compiler Design Research
                </span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 1. Problem Statement & Evaluated Approaches
    st.markdown("""
    <div class="research-callout" style="margin-top: 0; margin-bottom: 24px;">
        <h4 style="margin: 0 0 8px 0; color: #3b82f6; font-size: 16px;">The Compiler Symbol Table Challenge</h4>
        <p style="margin: 0; font-size: 14px; line-height: 1.6;">
            Compiler frontends require microsecond-scale identifier resolution under <strong>lexical scoping</strong>, 
            <strong>variable shadowing</strong>, and highly skewed reference patterns. 
            Standard implementations rely on <em>Separate Chaining</em> or wrap flat open-addressed tables inside a dynamic scope stack. 
            However, multi-table baseline wrappers experience severe <strong>61%–64% throughput degradation</strong> under nested scopes 
            due to repeated lookup traversals along parent scope chains. <strong>SVC-Hash</strong> investigates whether 
            virtualized composite-key hashing can eliminate wrapper overhead while preserving open-addressing cache efficiency.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Four Evaluated Approaches Cards
    st.markdown("### Evaluated Collision-Resolution Approaches")
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown("""
        <div class="research-card" style="height: 100%; border-top: 3px solid #2563eb;">
            <div style="font-weight: 700; color: #2563eb; font-size: 15px; margin-bottom: 6px;">Separate Chaining</div>
            <div style="font-size: 12px; opacity: 0.7; margin-bottom: 8px;">Industry Standard Baseline</div>
            <p style="font-size: 13px; line-height: 1.5; margin: 0;">
                Closed addressing with linked-list buckets. Excels in flat code when hot symbols stay in L1 cache, but suffers pointer chasing and heap fragmentation.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown("""
        <div class="research-card" style="height: 100%; border-top: 3px solid #f97316;">
            <div style="font-weight: 700; color: #f97316; font-size: 15px; margin-bottom: 6px;">Cuckoo Hashing</div>
            <div style="font-size: 12px; opacity: 0.7; margin-bottom: 8px;">2-Choice Relocation Baseline</div>
            <p style="font-size: 13px; line-height: 1.5; margin: 0;">
                Guarantees O(1) worst-case lookup by checking exactly 2 candidate positions. However, dense insertions trigger cascading eviction kicks and expensive table rehashes.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown("""
        <div class="research-card" style="height: 100%; border-top: 3px solid #059669;">
            <div style="font-weight: 700; color: #059669; font-size: 15px; margin-bottom: 6px;">Hopscotch Hashing</div>
            <div style="font-size: 12px; opacity: 0.7; margin-bottom: 8px;">Bounded Neighborhood Baseline</div>
            <p style="font-size: 13px; line-height: 1.5; margin: 0;">
                Constrains collisions to a 32-slot neighborhood bitmask for high cache locality. Delivers high flat throughput, but wrapping for nested scopes incurs substantial lookup penalties.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with c4:
        st.markdown("""
        <div class="research-card" style="height: 100%; border-top: 3px solid #dc2626;">
            <div style="font-weight: 700; color: #dc2626; font-size: 15px; margin-bottom: 6px;">SVC-Hash (Proposed)</div>
            <div style="font-size: 12px; opacity: 0.7; margin-bottom: 8px;">Scope-Virtualized Cuckoo Table</div>
            <p style="font-size: 13px; line-height: 1.5; margin: 0;">
                Single table virtualizing multiple scopes via composite keys <code>(identifier, scope_id)</code>, 4-slot buckets, an 8-slot stash, and O(1) tombstone deactivation on scope exit.
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 2. Authoritative Campaign KPI Cards
    st.markdown("### Authoritative Empirical Campaign Metrics")
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    with kpi1:
        st.metric(label="Authoritative Traces", value="38", help="36 synthetic traces across 12 conditions + 2 authentic cJSON traces")
    with kpi2:
        st.metric(label="Algorithm Families", value="4", help="Separate Chaining, Cuckoo, Hopscotch, and SVC-Hash")
    with kpi3:
        st.metric(label="Measured Trials", value="1,520", help="152 trace-algorithm pairs x 10 repetitions (+456 warmups = 1,976 total executions)")
    with kpi4:
        st.metric(label="Nested SVC Speedup", value="+70.8%", help="Median throughput speedup of SVC-Hash over Scoped Cuckoo in nested synthetic traces (Holm p = 0.00193)")
    with kpi5:
        st.metric(label="cJSON Nested Peak TP", value="734.9k op/s", help="Highest throughput among all algorithms on authentic nested cJSON AST with lowest memory (8.0 KB)")

    st.markdown("<br>", unsafe_allow_html=True)

    # 3. Call to Action: Interactive Symbol Table Lab
    cta_col1, cta_col2 = st.columns([3, 1])
    with cta_col1:
        st.markdown("""
        <div style="background: rgba(59, 130, 246, 0.08); border: 1px solid rgba(59, 130, 246, 0.3); border-radius: 8px; padding: 14px 18px;">
            <div style="font-weight: 700; font-size: 14.5px; color: #3b82f6;">Interactive Demonstration Available</div>
            <div style="font-size: 13px; opacity: 0.85; margin-top: 2px;">
                Experience step-by-step scope entry, variable shadowing, duplicate rejection, cuckoo kicks, and native C++ engine verification in the live demonstration tool.
            </div>
        </div>
        """, unsafe_allow_html=True)
    with cta_col2:
        if st.button("🚀 Launch Interactive Lab", type="primary", use_container_width=True):
            st.session_state["nav_selection"] = "Interactive Symbol Table Lab"
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # 4. Core Research Questions & Evidence-Based Findings
    st.markdown("### Research Questions & Primary Findings")
    rq_col1, rq_col2 = st.columns(2)

    with rq_col1:
        st.markdown("""
        <div class="research-card" style="height: 100%;">
            <h4 style="margin-top: 0; color: #3b82f6; font-size: 15px; border-bottom: 2px solid rgba(59,130,246,0.3); padding-bottom: 6px;">
                RQ1: Collision Resolution Under Compiler Workloads
            </h4>
            <p style="font-size: 13.5px; opacity: 0.9; margin-bottom: 10px;">
                <em>How do classical collision-resolution techniques behave under realistic symbol-table workloads compared with synthetic baselines?</em>
            </p>
            <ul style="font-size: 13px; opacity: 0.95; padding-left: 18px; line-height: 1.6; margin: 0;">
                <li><strong>Cache Locality Dominates Flat Workloads:</strong> On flat, frequency-skewed traces, Separate Chaining (<strong>1.82M op/s</strong>) and Hopscotch (<strong>1.84M op/s</strong>) outperform open addressing due to hot L1 CPU cache residency for frequently referenced identifiers.</li>
                <li><strong>Cuckoo Relocation Pathology:</strong> Plain Cuckoo hashing degrades severely (<strong>166k–353k op/s</strong>) under dense identifier insertions due to cascading relocation kicks and frequent rehashes.</li>
                <li><strong>SVC-Hash Open-Addressing Robustness:</strong> In frequency-matched synthetic workloads, SVC-Hash significantly outperforms Plain Cuckoo (<strong>39.6% median speedup</strong>, Holm-adjusted <em>p</em> = 0.00158).</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    with rq_col2:
        st.markdown("""
        <div class="research-card" style="height: 100%;">
            <h4 style="margin-top: 0; color: #10b981; font-size: 15px; border-bottom: 2px solid rgba(16,185,129,0.3); padding-bottom: 6px;">
                RQ2: Scope-Aware Hashing & Virtualization
            </h4>
            <p style="font-size: 13.5px; opacity: 0.9; margin-bottom: 10px;">
                <em>How does SVC-Hash behave under lexical nesting and variable shadowing compared with multi-table baseline wrappers?</em>
            </p>
            <ul style="font-size: 13px; opacity: 0.95; padding-left: 18px; line-height: 1.6; margin: 0;">
                <li><strong>Baseline Stack Degradation:</strong> Traditional multi-table baseline wrappers degrade by <strong>61.3% to 63.9%</strong> when transitioning from flat to nested scopes due to repeated scope-stack traversal overhead.</li>
                <li><strong>Significant Synthetic Speedup:</strong> Across nested synthetic workloads (N=36), SVC-Hash delivers a statistically significant <strong>70.8% median speedup</strong> over Scoped Cuckoo (Holm-adjusted <em>p</em> = 0.00193).</li>
                <li><strong>Real-Source Inversion on cJSON Nested AST:</strong> On authentic nested C code (1,002 operations, 128 scopes), SVC-Hash achieves <strong>highest throughput of all algorithms (734.9k op/s)</strong>—1.76x over Scoped Chaining, 2.64x over Scoped Hopscotch, 3.71x over Scoped Cuckoo—with the lowest memory (<strong>8.0 KB</strong>).</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 5. Summary Performance Overview Chart
    st.markdown("### Cross-Family Throughput Summary")
    st.caption("Median throughput across major workload families. Observe how Chaining and Hopscotch lead on flat traces, while SVC-Hash leads on authentic nested code.")

    df_summary = load_trace_summary()

    fam_order = [
        ("Random x Flat", ("random", "flat")),
        ("Random x Nested", ("random", "nested")),
        ("Freq-Matched x Flat", ("frequency-matched", "flat")),
        ("Freq-Matched x Nested", ("frequency-matched", "nested")),
        ("cJSON Flat", ("real", "flat")),
        ("cJSON Nested", ("real", "nested"))
    ]

    summary_plot_data = []
    for flabel, (dist, scope) in fam_order:
        sub = df_summary[(df_summary["identifier_distribution"] == dist) & (df_summary["scope_mode"] == scope)]
        for bfam in ["chaining", "cuckoo", "hopscotch", "svc_hash"]:
            sub_b = sub[sub["baseline_family"] == bfam]
            if not sub_b.empty:
                summary_plot_data.append({
                    "Workload Family": flabel,
                    "Algorithm Family": "Chaining / Scoped" if bfam == "chaining" else ("Cuckoo / Scoped" if bfam == "cuckoo" else ("Hopscotch / Scoped" if bfam == "hopscotch" else "SVC-Hash")),
                    "Median Throughput (k-ops/sec)": sub_b["tp_median"].median() / 1000.0
                })

    df_sp = pd.DataFrame(summary_plot_data)

    fig = px.bar(
        df_sp,
        x="Workload Family",
        y="Median Throughput (k-ops/sec)",
        color="Algorithm Family",
        barmode="group",
        color_discrete_map={
            "Chaining / Scoped": "#2563eb",
            "Cuckoo / Scoped": "#f97316",
            "Hopscotch / Scoped": "#059669",
            "SVC-Hash": "#dc2626"
        }
    )
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=12),
        margin=dict(l=40, r=40, t=30, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis_title="Workload Family (Distribution x Scoping)",
        yaxis_title="Median Throughput (Kilo-Operations / Second)"
    )
    st.plotly_chart(fig, use_container_width=True)
