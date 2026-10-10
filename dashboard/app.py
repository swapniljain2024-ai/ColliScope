"""
ColliScope Research Dashboard — Main Application Entry Point
Workload-Aware Evaluation and Scope-Aware Cuckoo Hashing for Compiler Symbol Tables
Redesigned 5-Section Architecture for Faculty Demonstration & Research Exploration.
"""

import sys
import os

# Ensure repository root is in python path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import streamlit as st

from dashboard.views.overview import render_overview
from dashboard.views.interactive_lab import render_interactive_lab
from dashboard.views.algorithm_comparison import render_algorithm_comparison
from dashboard.views.scope_and_svc import render_scope_and_svc
from dashboard.views.experimental_results import render_experimental_results


def main():
    st.set_page_config(
        page_title="ColliScope Research Dashboard",
        page_icon="🔬",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Scientific Computing Research Aesthetic (Theme-Adaptive)
    st.markdown("""
    <style>
        /* Base typography & layout adjustments */
        .main .block-container {
            padding-top: 1.5rem;
            padding-bottom: 3rem;
            max-width: 1300px;
        }

        /* Metric card styling — theme adaptive */
        div[data-testid="stMetric"] {
            background-color: var(--secondary-background-color);
            border: 1px solid rgba(128, 128, 128, 0.2);
            padding: 12px 16px;
            border-radius: 8px;
            box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        }
        div[data-testid="stMetricLabel"] {
            font-size: 13px !important;
            font-weight: 600 !important;
            color: var(--text-color) !important;
            opacity: 0.8;
        }
        div[data-testid="stMetricValue"] {
            font-size: 24px !important;
            font-weight: 700 !important;
            color: var(--text-color) !important;
        }

        /* Sidebar styling — inherit theme colors naturally */
        section[data-testid="stSidebar"] {
            border-right: 1px solid rgba(128, 128, 128, 0.2);
        }
        section[data-testid="stSidebar"] .block-container {
            padding-top: 1.5rem;
        }

        /* Sidebar radio navigation — crisp text in both light and dark modes */
        section[data-testid="stSidebar"] div[data-testid="stRadio"] label {
            padding: 8px 12px;
            border-radius: 6px;
            margin-bottom: 2px;
            transition: background-color 0.15s ease;
        }
        section[data-testid="stSidebar"] div[data-testid="stRadio"] label:hover {
            background-color: rgba(128, 128, 128, 0.12);
        }
        section[data-testid="stSidebar"] div[data-testid="stRadio"] label p {
            font-weight: 600 !important;
            font-size: 14px !important;
            color: var(--text-color) !important;
        }

        /* Table header enhancements */
        thead tr th {
            font-weight: 700 !important;
            background-color: var(--secondary-background-color) !important;
            color: var(--text-color) !important;
            border-bottom: 2px solid rgba(128, 128, 128, 0.2) !important;
        }

        /* Reusable research UI cards */
        .research-card {
            background-color: var(--secondary-background-color);
            border: 1px solid rgba(128, 128, 128, 0.2);
            border-radius: 8px;
            padding: 16px 20px;
            margin-bottom: 16px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        }
        .research-callout {
            background-color: rgba(59, 130, 246, 0.08);
            border-left: 4px solid #3b82f6;
            border-radius: 0 8px 8px 0;
            padding: 14px 18px;
            margin: 14px 0;
            color: var(--text-color);
        }
        .research-callout-warning {
            background-color: rgba(245, 158, 11, 0.08);
            border-left: 4px solid #f59e0b;
            border-radius: 0 8px 8px 0;
            padding: 14px 18px;
            margin: 14px 0;
            color: var(--text-color);
        }
    </style>
    """, unsafe_allow_html=True)

    # Sidebar Header & Branding
    st.sidebar.markdown("""
    <div style="padding-bottom: 14px; margin-bottom: 14px; border-bottom: 1px solid rgba(128,128,128,0.2);">
        <h2 style="margin: 0; font-size: 21px; font-weight: 800; letter-spacing: -0.02em;">🔬 ColliScope</h2>
        <span style="font-size: 12px; opacity: 0.75; font-weight: 500;">Compiler Symbol Table Research</span>
    </div>
    """, unsafe_allow_html=True)

    # Streamlined 5-Section Navigation
    nav_options = [
        "1. Overview",
        "2. Interactive Symbol Table Lab",
        "3. Algorithm Comparison",
        "4. Scope & SVC-Hash",
        "5. Experimental Results"
    ]

    # Synchronize session state navigation
    if "nav_selection" not in st.session_state:
        st.session_state["nav_selection"] = nav_options[0]
    elif st.session_state["nav_selection"] not in nav_options:
        for opt in nav_options:
            if st.session_state["nav_selection"] in opt or opt in st.session_state["nav_selection"]:
                st.session_state["nav_selection"] = opt
                break
        else:
            st.session_state["nav_selection"] = nav_options[0]

    current_idx = nav_options.index(st.session_state["nav_selection"])

    selected_page = st.sidebar.radio(
        "Navigation",
        options=nav_options,
        index=current_idx,
        label_visibility="collapsed"
    )
    st.session_state["nav_selection"] = selected_page

    # Minimal secondary information in sidebar
    st.sidebar.markdown("---")
    with st.sidebar.expander("ℹ️ Experiment Specs & Provenance", expanded=False):
        st.markdown("""
        <div style="font-size: 11.5px; opacity: 0.85; line-height: 1.6;">
            <strong>Authoritative Traces:</strong> 38 (36 Synthetic + 2 cJSON)<br>
            <strong>Algorithm Families:</strong> 4 (Chaining, Cuckoo, Hopscotch, SVC)<br>
            <strong>Total Executions:</strong> 1,976 (1,520 Measured + 456 Warmups)<br>
            <strong>Hardware Timer:</strong> Windows QPC (10.0 MHz Monotonic)<br>
            <strong>Compiler:</strong> MinGW GCC 8.1.0 (-O3 -std=c++17)
        </div>
        """, unsafe_allow_html=True)

    # Route to selected 5 sections
    if selected_page == "1. Overview":
        render_overview()
    elif selected_page == "2. Interactive Symbol Table Lab":
        render_interactive_lab()
    elif selected_page == "3. Algorithm Comparison":
        render_algorithm_comparison()
    elif selected_page == "4. Scope & SVC-Hash":
        render_scope_and_svc()
    elif selected_page == "5. Experimental Results":
        render_experimental_results()


if __name__ == "__main__":
    main()
