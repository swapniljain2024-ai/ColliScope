"""
ColliScope Dashboard: Page 3 - Workload Explorer
Visualizing nominal workload labels vs realized operation composition, Zipfian skew, and scope transitions.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from dashboard.data_loader import load_operation_composition


def render_workload_explorer():
    st.title("Workload Explorer")
    st.markdown("Examine the discrepancy between nominal workload labels and authentic realized operation compositions discovered during Phase 7.")

    df_comp = load_operation_composition()

    # Phase 7 Critical Finding Warning Box
    st.warning("""
    **Key Methodological Finding (Phase 7 Audit):**  
    Nominal workload mix labels (`declaration-heavy`, `lookup-heavy`, `mixed`) do **not** perfectly control the realized operation proportions across all experimental conditions.  
    In **frequency-matched flat traces**, even traces nominally designated as *declaration-heavy* realized **87.0% reference operations** (and only 12.8% declarations). This occurs because Zipfian token distributions repeatedly reference a finite vocabulary of declared symbols, reflecting realistic compiler symbol table access patterns.
    """)

    # Filter controls
    col1, col2 = st.columns(2)
    with col1:
        sel_dist = st.multiselect("Filter Distribution", options=sorted(df_comp["identifier_distribution"].unique()), default=sorted(df_comp["identifier_distribution"].unique()))
    with col2:
        sel_scope = st.multiselect("Filter Scope", options=sorted(df_comp["scope_mode"].unique()), default=sorted(df_comp["scope_mode"].unique()))

    filtered = df_comp[
        (df_comp["identifier_distribution"].isin(sel_dist)) &
        (df_comp["scope_mode"].isin(sel_scope))
    ].sort_values(by=["category", "scope_mode", "identifier_distribution", "nominal_workload_type", "replicate"])

    st.markdown("---")

    # Stacked bar chart of realized operation composition
    st.subheader("Realized Operation Composition (%) per Trace")
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=filtered["trace_name"],
        y=filtered["pct_declaration"],
        name="DECLARE (%)",
        marker_color="#1b9e77"
    ))
    fig.add_trace(go.Bar(
        x=filtered["trace_name"],
        y=filtered["pct_reference"],
        name="REFERENCE (%)",
        marker_color="#d95f02"
    ))
    fig.add_trace(go.Bar(
        x=filtered["trace_name"],
        y=filtered["pct_scope_ops"],
        name="SCOPE ENTER/EXIT (%)",
        marker_color="#7570b3"
    ))

    fig.update_layout(
        barmode="stack",
        template="plotly_white",
        yaxis=dict(title="Operation Share (%)", range=[0, 100]),
        xaxis=dict(title="Trace Name", tickangle=-45, tickfont=dict(size=9)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=40, t=50, b=120)
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Comparison Table: Nominal vs Realized by Condition
    st.subheader("Nominal Mix vs Realized Operation Means")

    agg_df = df_comp.groupby(["identifier_distribution", "scope_mode", "nominal_workload_type"]).agg(
        traces=("trace_name", "count"),
        mean_decl_pct=("pct_declaration", "mean"),
        mean_ref_pct=("pct_reference", "mean"),
        mean_scope_pct=("pct_scope_ops", "mean"),
        mean_total_ops=("total_operations", "mean")
    ).reset_index()

    st.dataframe(
        agg_df,
        column_config={
            "identifier_distribution": "Distribution",
            "scope_mode": "Scope",
            "nominal_workload_type": "Nominal Mix Label",
            "traces": "Traces (N)",
            "mean_decl_pct": st.column_config.NumberColumn("Realized Decl %", format="%.1f%%"),
            "mean_ref_pct": st.column_config.NumberColumn("Realized Ref %", format="%.1f%%"),
            "mean_scope_pct": st.column_config.NumberColumn("Realized Scope %", format="%.1f%%"),
            "mean_total_ops": st.column_config.NumberColumn("Avg Operations", format="%d")
        },
        use_container_width=True,
        hide_index=True
    )

    st.markdown("""
    #### Analytical Takeaways:
    1. **Random Identifiers:** Uniform random identifier generation preserves the nominal mix proportions relatively well (~72% declarations in declaration-heavy flat; ~25% in lookup-heavy).
    2. **Frequency-Matched Identifiers:** Zipfian skew from authentic C code heavily skews the operation profile toward references (87% to 92% across all nominal mixes).
    3. **Scope Operations Overhead:** In nested workloads, lexical scope transitions account for 9.0% to 25.5% of all trace commands.
    """)
