"""
ColliScope Dashboard Data Loader
Loads and caches verified Phase 8 statistical outputs, manifest metadata, and Phase 7 diagnostics.
"""

import os
import json
import pandas as pd
import streamlit as st

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHASE8_DIR = os.path.join(BASE_DIR, "results", "phase8")
PHASE7_DIR = os.path.join(BASE_DIR, "results", "phase7")
MANIFEST_PATH = os.path.join(BASE_DIR, "workloads", "traces", "manifest.json")


@st.cache_data
def load_trace_summary() -> pd.DataFrame:
    path = os.path.join(PHASE8_DIR, "phase8_trace_level_summary.csv")
    return pd.read_csv(path)


@st.cache_data
def load_synthetic_analysis() -> pd.DataFrame:
    path = os.path.join(PHASE8_DIR, "phase8_synthetic_analysis.csv")
    return pd.read_csv(path)


@st.cache_data
def load_pairwise_comparisons() -> pd.DataFrame:
    path = os.path.join(PHASE8_DIR, "phase8_pairwise_comparisons.csv")
    return pd.read_csv(path)


@st.cache_data
def load_statistical_tests() -> pd.DataFrame:
    path = os.path.join(PHASE8_DIR, "phase8_statistical_tests.csv")
    return pd.read_csv(path)


@st.cache_data
def load_effect_sizes() -> pd.DataFrame:
    path = os.path.join(PHASE8_DIR, "phase8_effect_sizes.csv")
    return pd.read_csv(path)


@st.cache_data
def load_operation_composition() -> pd.DataFrame:
    path = os.path.join(PHASE8_DIR, "phase8_operation_composition.csv")
    return pd.read_csv(path)


@st.cache_data
def load_cjson_summary() -> pd.DataFrame:
    path = os.path.join(PHASE8_DIR, "phase8_real_cjson_summary.csv")
    return pd.read_csv(path)


@st.cache_data
def load_manifest() -> dict:
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


@st.cache_data
def load_svc_diagnostics() -> pd.DataFrame:
    json_path = os.path.join(PHASE7_DIR, "phase7_benchmark_results.json")
    if not os.path.exists(json_path):
        return pd.DataFrame()
        
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    diag_rows = []
    for run in data.get("runs", []):
        tname = run.get("trace_file", "")
        if "svc_hash" in run.get("algorithms", {}):
            trials = run["algorithms"]["svc_hash"].get("trials", [])
            if trials:
                t0 = trials[0]
                cms = dict(t0.get("custom_metrics", {}))
                cms["trace_name"] = tname
                diag_rows.append(cms)
                
    return pd.DataFrame(diag_rows)


@st.cache_data
def load_analysis_report_text() -> str:
    path = os.path.join(PHASE8_DIR, "phase8_analysis_report.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""
