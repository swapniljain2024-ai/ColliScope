"""
ColliScope Dashboard: Page 2 - Dataset Explorer
Interactive inspection of the 38 authoritative workload traces, filters, and metadata.
"""

import streamlit as st
import plotly.express as px
import pandas as pd
from dashboard.data_loader import load_operation_composition, load_manifest


def render_dataset_explorer():
    st.title("Dataset Explorer")
    st.markdown("Inspect the 38 authoritative workload traces comprising the ColliScope experimental corpus.")

    df_comp = load_operation_composition()
    manifest_data = load_manifest()

    # Filter Sidebar / Controls in Expander
    with st.expander("Filter Workload Traces", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            cat_filter = st.multiselect("Category", options=sorted(df_comp["category"].unique()), default=sorted(df_comp["category"].unique()))
        with col2:
            scope_filter = st.multiselect("Scope Mode", options=sorted(df_comp["scope_mode"].unique()), default=sorted(df_comp["scope_mode"].unique()))
        with col3:
            dist_filter = st.multiselect("Identifier Distribution", options=sorted(df_comp["identifier_distribution"].unique()), default=sorted(df_comp["identifier_distribution"].unique()))
        with col4:
            mix_filter = st.multiselect("Nominal Workload Mix", options=sorted(df_comp["nominal_workload_type"].unique()), default=sorted(df_comp["nominal_workload_type"].unique()))

    # Apply filters
    filtered = df_comp[
        (df_comp["category"].isin(cat_filter)) &
        (df_comp["scope_mode"].isin(scope_filter)) &
        (df_comp["identifier_distribution"].isin(dist_filter)) &
        (df_comp["nominal_workload_type"].isin(mix_filter))
    ]

    # Quick Summary KPIs
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric("Traces Displayed", f"{len(filtered)} / 38")
    with kpi2:
        st.metric("Total Operations", f"{filtered['total_operations'].sum():,}")
    with kpi3:
        st.metric("Total Declarations", f"{filtered['declaration_count'].sum():,}")
    with kpi4:
        st.metric("Total References", f"{filtered['reference_count'].sum():,}")

    st.markdown("---")

    # Table of traces
    st.subheader("Trace Manifest & Operation Breakdown")
    
    display_df = filtered[[
        "trace_name", "category", "identifier_distribution", "scope_mode",
        "nominal_workload_type", "replicate", "seed", "total_operations",
        "declaration_count", "reference_count", "enter_scope_count", "exit_scope_count",
        "pct_declaration", "pct_reference", "pct_scope_ops", "unique_symbols"
    ]].copy()

    st.dataframe(
        display_df,
        column_config={
            "trace_name": st.column_config.TextColumn("Trace File", width="medium"),
            "category": "Category",
            "identifier_distribution": "Distribution",
            "scope_mode": "Scope",
            "nominal_workload_type": "Nominal Mix",
            "replicate": "Replicate",
            "seed": "Seed",
            "total_operations": st.column_config.NumberColumn("Total Ops", format="%d"),
            "declaration_count": st.column_config.NumberColumn("Decl", format="%d"),
            "reference_count": st.column_config.NumberColumn("Ref", format="%d"),
            "enter_scope_count": st.column_config.NumberColumn("Enter", format="%d"),
            "exit_scope_count": st.column_config.NumberColumn("Exit", format="%d"),
            "pct_declaration": st.column_config.NumberColumn("Decl %", format="%.1f%%"),
            "pct_reference": st.column_config.NumberColumn("Ref %", format="%.1f%%"),
            "pct_scope_ops": st.column_config.NumberColumn("Scope %", format="%.1f%%"),
            "unique_symbols": st.column_config.NumberColumn("Unique Symbols", format="%d")
        },
        use_container_width=True,
        hide_index=True
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # Visual distribution chart
    st.subheader("Workload Matrix Distribution")
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        fig1 = px.histogram(
            filtered,
            x="identifier_distribution",
            color="scope_mode",
            barmode="group",
            title="Traces by Identifier Distribution and Scope Mode",
            color_discrete_map={"flat": "#4575b4", "nested": "#d73027"}
        )
        fig1.update_layout(template="plotly_white", margin=dict(l=40, r=40, t=50, b=40))
        st.plotly_chart(fig1, use_container_width=True)

    with chart_col2:
        fig2 = px.histogram(
            filtered,
            x="nominal_workload_type",
            color="category",
            barmode="stack",
            title="Traces by Nominal Workload Mix and Category",
            color_discrete_map={"synthetic": "#74add1", "real-source": "#fdae61"}
        )
        fig2.update_layout(template="plotly_white", margin=dict(l=40, r=40, t=50, b=40))
        st.plotly_chart(fig2, use_container_width=True)

    # Provenance details
    st.markdown("""
    > [!NOTE]
    > **Real-Source Provenance:** The 2 real-source traces (`trace_real-source_flat.trace` and `trace_real-source_nested.trace`) originate from the authentic **cJSON v1.7.18** repository (Git commit `acc76239bee01d8e9c858ae2cab296704e52d916`, MIT License). They represent **ONE software project** evaluated under **TWO scope representations** (global flat scope vs full Clang AST lexical block scopes).
    """)
