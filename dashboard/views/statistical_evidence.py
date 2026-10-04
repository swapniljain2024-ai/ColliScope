"""
ColliScope Dashboard: Page 7 - Statistical Evidence
Hypothesis testing results, Holm-Bonferroni corrections, effect sizes, and bootstrap confidence intervals.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from dashboard.data_loader import load_statistical_tests, load_effect_sizes


def render_statistical_evidence():
    st.title("Statistical Evidence & Hypothesis Testing")
    st.markdown("Formal non-parametric hypothesis tests, multiple-comparison corrections, and effect sizes evaluated across independent workload replicates.")

    st.info("""
    **Methodological Integrity Note:**  
    - **Inferential Sample Size ($N$):** In the tables below, $N$ represents the number of **independent workload replicates** (e.g. $N=36$ across the synthetic matrix, $N=18$ per scope mode, $N=12$ per mix).  
    - **No Pseudo-Replication:** The 10 benchmark repetitions are repeated measurements of the same workload and were aggregated via median prior to statistical testing.  
    - **Multiple-Testing Control:** The **Holm-Bonferroni step-down correction** was applied within each orthogonal comparison family to strictly preserve family-wise error rates.
    """)

    df_tests = load_statistical_tests()
    df_effects = load_effect_sizes()

    # Filters for tests
    col1, col2 = st.columns(2)
    with col1:
        fam_options = ["All Families"] + sorted(df_tests["family"].unique().tolist())
        sel_fam = st.selectbox("Hypothesis Comparison Family", options=fam_options, index=0)
    with col2:
        sig_only = st.checkbox("Show Only Statistically Significant Results (Holm-adj p < 0.05)", value=False)

    filtered_tests = df_tests.copy()
    if sel_fam != "All Families":
        filtered_tests = filtered_tests[filtered_tests["family"] == sel_fam]
    if sig_only:
        filtered_tests = filtered_tests[filtered_tests["sig_alpha_05"] == True]

    st.subheader(f"Paired Wilcoxon Signed-Rank Test Results ({len(filtered_tests)} tests)")

    st.dataframe(
        filtered_tests,
        column_config={
            "family": "Hypothesis Family",
            "baseline_family": "Baseline",
            "n_pairs": st.column_config.NumberColumn("N Pairs", format="%d"),
            "metric_diff": "Metric",
            "median_svc": st.column_config.NumberColumn("Median SVC", format="%.1f"),
            "median_baseline": st.column_config.NumberColumn("Median Base", format="%.1f"),
            "median_diff": st.column_config.NumberColumn("Median Diff", format="%+.1f"),
            "wilcoxon_stat": st.column_config.NumberColumn("Wilcoxon W", format="%.1f"),
            "raw_p_value": st.column_config.NumberColumn("Raw p-value", format="%.6f"),
            "adjusted_p_value_holm": st.column_config.NumberColumn("Holm-Adj p", format="%.6f"),
            "rank_biserial_r": st.column_config.NumberColumn("Rank-Biserial r", format="%+.4f"),
            "sig_alpha_05": st.column_config.CheckboxColumn("p < 0.05"),
            "sig_alpha_01": st.column_config.CheckboxColumn("p < 0.01"),
        },
        use_container_width=True,
        hide_index=True
    )

    st.markdown("---")

    # Effect Sizes & Bootstrap CIs Forest Plot
    st.subheader("Effect Sizes: Speedup Ratios with 95% Bootstrap Confidence Intervals")
    st.markdown("Forest plot of median speedup ratios ($\text{SVC} / \text{Baseline}$). Values $> 1.0$ indicate SVC-Hash advantage.")

    sel_stratum = st.selectbox(
        "Select Stratum for Effect Sizes",
        options=sorted(df_effects["stratum"].unique().tolist()),
        index=0
    )

    eff_sub = df_effects[df_effects["stratum"] == sel_stratum]

    fig_forest = go.Figure()

    for _, r in eff_sub.iterrows():
        base = r["baseline_family"]
        med = r["median_speedup_ratio"]
        low = r["speedup_ratio_ci95_low"]
        high = r["speedup_ratio_ci95_high"]
        color = "#15803d" if low > 1.0 else ("#b91c1c" if high < 1.0 else "#b45309")

        fig_forest.add_trace(go.Scatter(
            x=[med],
            y=[base],
            error_x=dict(type='data', symmetric=False, array=[high - med], arrayminus=[med - low], color=color, thickness=2.5, width=8),
            mode='markers',
            marker=dict(size=12, color=color),
            name=base,
            text=f"Median: {med:.2f}x [{low:.2f}x, {high:.2f}x]"
        ))

    fig_forest.add_vline(x=1.0, line_dash="dash", line_color="black", annotation_text="Parity (1.0x)")
    fig_forest.update_layout(
        template="plotly_white",
        title=f"95% Bootstrap CI for Speedup Ratio — {sel_stratum}",
        xaxis_title="Throughput Speedup Ratio (SVC / Baseline)",
        yaxis_title="Baseline Compared",
        showlegend=False,
        height=320,
        margin=dict(l=40, r=40, t=50, b=40)
    )
    st.plotly_chart(fig_forest, use_container_width=True)

    # Effect Sizes Table
    st.dataframe(
        eff_sub[[
            "stratum", "baseline_family", "n_workload_replicates",
            "median_speedup_ratio", "speedup_ratio_ci95_low", "speedup_ratio_ci95_high",
            "mean_speedup_ratio", "ratio_min", "ratio_max", "rank_biserial_r"
        ]],
        column_config={
            "stratum": "Stratum",
            "baseline_family": "Baseline",
            "n_workload_replicates": "N",
            "median_speedup_ratio": st.column_config.NumberColumn("Median Ratio", format="%.2fx"),
            "speedup_ratio_ci95_low": st.column_config.NumberColumn("95% CI Low", format="%.2fx"),
            "speedup_ratio_ci95_high": st.column_config.NumberColumn("95% CI High", format="%.2fx"),
            "mean_speedup_ratio": st.column_config.NumberColumn("Mean Ratio", format="%.2fx"),
            "ratio_min": st.column_config.NumberColumn("Min Ratio", format="%.2fx"),
            "ratio_max": st.column_config.NumberColumn("Max Ratio", format="%.2fx"),
            "rank_biserial_r": st.column_config.NumberColumn("Rank-Biserial r", format="%+.4f"),
        },
        use_container_width=True,
        hide_index=True
    )
