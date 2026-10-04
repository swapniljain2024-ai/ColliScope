"""
ColliScope Research Dashboard — Main Application Entry Point
Workload-Aware Evaluation and Scope-Aware Cuckoo Hashing for Compiler Symbol Tables
"""

import sys
import os

# Ensure repository root is in python path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import streamlit as st

from dashboard.views.overview import render_overview
from dashboard.views.dataset_explorer import render_dataset_explorer
from dashboard.views.workload_explorer import render_workload_explorer
from dashboard.views.algorithm_comparison import render_algorithm_comparison
from dashboard.views.svc_analysis import render_svc_analysis
from dashboard.views.scope_analysis import render_scope_analysis
from dashboard.views.statistical_evidence import render_statistical_evidence
from dashboard.views.cjson_case_study import render_cjson_case_study
from dashboard.views.trace_explorer import render_trace_explorer
from dashboard.views.methodology import render_methodology


def main():
    st.set_page_config(
        page_title="ColliScope Research Dashboard",
        page_icon="🔬",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Custom styling for research aesthetic
    st.markdown("""
    <style>
        /* Base typography & layout adjustments */
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
            max-width: 1300px;
        }
        
        /* Metric card styling */
        div[data-testid="stMetric"] {
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            padding: 12px 16px;
            border-radius: 8px;
            box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        }
        div[data-testid="stMetricLabel"] {
            font-size: 13px !important;
            font-weight: 600 !important;
            color: #475569 !important;
        }
        div[data-testid="stMetricValue"] {
            font-size: 24px !important;
            font-weight: 700 !important;
            color: #0f172a !important;
        }

        /* Sidebar styling */
        section[data-testid="stSidebar"] {
            background-color: #f8fafc;
            border-right: 1px solid #e2e8f0;
        }
        section[data-testid="stSidebar"] .block-container {
            padding-top: 2rem;
        }

        /* Table header enhancements */
        thead tr th {
            font-weight: 700 !important;
            background-color: #f1f5f9 !important;
            color: #1e293b !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # Sidebar Header & Navigation
    st.sidebar.markdown("""
    <div style="padding-bottom: 15px; margin-bottom: 15px; border-bottom: 1px solid #e2e8f0;">
        <h2 style="margin: 0; font-size: 20px; font-weight: 800; color: #0f172a;">🔬 ColliScope</h2>
        <span style="font-size: 12px; color: #64748b; font-weight: 500;">Symbol Table Research Dashboard</span>
    </div>
    """, unsafe_allow_html=True)

    nav_options = [
        "1. Overview",
        "2. Dataset Explorer",
        "3. Workload Explorer",
        "4. Algorithm Comparison",
        "5. SVC-Hash Analysis",
        "6. Scope Analysis",
        "7. Statistical Evidence",
        "8. Real-Source Case Study",
        "9. Trace / Operation Explorer",
        "10. Methodology / About"
    ]

    selected_page = st.sidebar.radio(
        "Navigation",
        options=nav_options,
        index=0,
        label_visibility="collapsed"
    )

    # Sidebar Provenance Metadata
    st.sidebar.markdown("---")
    st.sidebar.markdown("""
    <div style="font-size: 11.5px; color: #64748b; line-height: 1.5;">
        <strong>Authoritative Dataset:</strong> Phase 7 Campaign<br>
        <strong>Statistical Suite:</strong> Phase 8 Locked<br>
        <strong>Traces:</strong> 38 (36 Synthetic + 2 cJSON)<br>
        <strong>Trials:</strong> 1,520 Measured (+456 Warmups)<br>
        <strong>Timer:</strong> Windows QPC (10 MHz Monotonic)<br>
        <strong>Compiler:</strong> GCC 8.1.0 (-O3)
    </div>
    """, unsafe_allow_html=True)

    # Route to selected page
    if selected_page == "1. Overview":
        render_overview()
    elif selected_page == "2. Dataset Explorer":
        render_dataset_explorer()
    elif selected_page == "3. Workload Explorer":
        render_workload_explorer()
    elif selected_page == "4. Algorithm Comparison":
        render_algorithm_comparison()
    elif selected_page == "5. SVC-Hash Analysis":
        render_svc_analysis()
    elif selected_page == "6. Scope Analysis":
        render_scope_analysis()
    elif selected_page == "7. Statistical Evidence":
        render_statistical_evidence()
    elif selected_page == "8. Real-Source Case Study":
        render_cjson_case_study()
    elif selected_page == "9. Trace / Operation Explorer":
        render_trace_explorer()
    elif selected_page == "10. Methodology / About":
        render_methodology()


if __name__ == "__main__":
    main()
