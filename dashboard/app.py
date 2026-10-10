"""
ColliScope Research Dashboard — Main Application Entry Point
Clean, light, modern analytics interface designed for university faculty demonstration.
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
        page_title="ColliScope — Compiler Symbol Table Research",
        page_icon="🔬",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Clean, Light, Professional Research Analytics Theme
    st.markdown("""
    <style>
        /* Base typography & page canvas */
        .stApp {
            background-color: #F5F7FB;
            color: #263247;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        }

        .main .block-container {
            padding-top: 1.25rem;
            padding-bottom: 2.5rem;
            max-width: 1260px;
        }

        /* Headings & Text */
        h1, h2, h3, h4, h5, h6 {
            color: #263247 !important;
            font-weight: 700;
            letter-spacing: -0.01em;
        }
        p, span, label {
            color: #263247;
        }
        .stCaption, caption, .caption-text {
            color: #68758A !important;
            font-size: 13px !important;
        }

        /* Metric card styling — Crisp White on Cool Canvas */
        div[data-testid="stMetric"] {
            background-color: #FFFFFF;
            border: 1px solid #E1E7F0;
            padding: 14px 18px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(38, 50, 71, 0.04);
        }
        div[data-testid="stMetricLabel"] {
            font-size: 12.5px !important;
            font-weight: 600 !important;
            color: #68758A !important;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }
        div[data-testid="stMetricValue"] {
            font-size: 26px !important;
            font-weight: 700 !important;
            color: #263247 !important;
            margin-top: 2px;
        }

        /* Sidebar styling — Soft pale blue-grey */
        section[data-testid="stSidebar"] {
            background-color: #EAF0F8;
            border-right: 1px solid #E1E7F0;
        }
        section[data-testid="stSidebar"] .block-container {
            padding-top: 1.25rem;
            padding-bottom: 1.5rem;
        }

        /* Sidebar radio navigation */
        section[data-testid="stSidebar"] div[data-testid="stRadio"] label {
            background-color: transparent;
            padding: 8px 12px;
            border-radius: 6px;
            margin-bottom: 3px;
            border: 1px solid transparent;
            transition: all 0.15s ease;
        }
        section[data-testid="stSidebar"] div[data-testid="stRadio"] label:hover {
            background-color: rgba(79, 107, 237, 0.08);
            border-color: rgba(79, 107, 237, 0.15);
        }
        section[data-testid="stSidebar"] div[data-testid="stRadio"] label p {
            font-weight: 500 !important;
            font-size: 13.5px !important;
            color: #263247 !important;
        }

        /* Primary Button */
        div.stButton > button {
            background-color: #4F6BED;
            color: #FFFFFF;
            font-weight: 600;
            border: none;
            border-radius: 6px;
            padding: 8px 18px;
            transition: background-color 0.15s ease;
        }
        div.stButton > button:hover {
            background-color: #3E56D0;
            color: #FFFFFF;
            border: none;
        }

        /* Reusable Card Components */
        .research-card {
            background-color: #FFFFFF;
            border: 1px solid #E1E7F0;
            border-radius: 8px;
            padding: 16px 20px;
            margin-bottom: 14px;
            box-shadow: 0 1px 3px rgba(38, 50, 71, 0.03);
            color: #263247;
        }
        .research-callout {
            background-color: #FFFFFF;
            border: 1px solid #E1E7F0;
            border-left: 4px solid #4F6BED;
            border-radius: 0 8px 8px 0;
            padding: 12px 18px;
            margin: 10px 0 14px 0;
            color: #263247;
        }
        .research-callout-success {
            background-color: #FFFFFF;
            border: 1px solid #E1E7F0;
            border-left: 4px solid #39A985;
            border-radius: 0 8px 8px 0;
            padding: 12px 18px;
            margin: 10px 0 14px 0;
            color: #263247;
        }
        .research-callout-warning {
            background-color: #FFFFFF;
            border: 1px solid #E1E7F0;
            border-left: 4px solid #E6B65C;
            border-radius: 0 8px 8px 0;
            padding: 12px 18px;
            margin: 10px 0 14px 0;
            color: #263247;
        }

        /* Table header enhancements */
        thead tr th {
            font-weight: 600 !important;
            background-color: #EAF0F8 !important;
            color: #263247 !important;
            border-bottom: 1px solid #E1E7F0 !important;
            font-size: 13px !important;
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid #E1E7F0;
            border-radius: 6px;
            background-color: #FFFFFF;
        }

        /* Expanders styling */
        div[data-testid="stExpander"] {
            border: 1px solid #E1E7F0 !important;
            border-radius: 8px !important;
            background-color: #FFFFFF !important;
            margin-bottom: 10px !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # Sidebar Header & Branding
    st.sidebar.markdown("""
    <div style="padding-bottom: 12px; margin-bottom: 12px; border-bottom: 1px solid #E1E7F0;">
        <div style="font-size: 19px; font-weight: 800; color: #263247; letter-spacing: -0.02em;">
            🔬 ColliScope
        </div>
        <div style="font-size: 12px; color: #68758A; font-weight: 500; margin-top: 1px;">
            Compiler Symbol Table Research
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 5 Streamlined Navigation Sections
    nav_options = [
        "1. Overview",
        "2. Interactive Symbol Table Lab",
        "3. Algorithm Comparison",
        "4. Scope & SVC-Hash",
        "5. Experimental Results & Provenance"
    ]

    # Handle intra-page CTA routing seamlessly
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

    # Compact Status Indicator (no clutter)
    st.sidebar.markdown("<br>", unsafe_allow_html=True)
    st.sidebar.markdown("""
    <div style="padding: 8px 12px; border-radius: 6px; background-color: #FFFFFF; border: 1px solid #E1E7F0; text-align: center;">
        <span style="font-size: 11.5px; font-weight: 600; color: #68758A;">
            38 Traces · 4 Algorithms · 1,520 Trials
        </span>
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
    elif selected_page == "5. Experimental Results & Provenance":
        render_experimental_results()


if __name__ == "__main__":
    main()
