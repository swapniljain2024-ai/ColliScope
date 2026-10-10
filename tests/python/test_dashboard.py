"""
Tests for ColliScope Phase 9 Research Dashboard
Validates data loaders, view functions, data integrity, and provenance.
"""

import os
import sys
import pytest
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from dashboard.data_loader import (
    load_trace_summary,
    load_synthetic_analysis,
    load_pairwise_comparisons,
    load_statistical_tests,
    load_effect_sizes,
    load_operation_composition,
    load_cjson_summary,
    load_manifest,
    load_svc_diagnostics,
    load_analysis_report_text
)


def test_data_loader_row_counts():
    """Verify all Phase 8 data artifacts load with exact expected row counts."""
    summary = load_trace_summary()
    assert len(summary) == 152, f"Expected 152 summary rows, got {len(summary)}"

    synth = load_synthetic_analysis()
    assert len(synth) == 144, f"Expected 144 synthetic rows, got {len(synth)}"

    paired = load_pairwise_comparisons()
    assert len(paired) == 108, f"Expected 108 paired rows, got {len(paired)}"

    tests = load_statistical_tests()
    assert len(tests) == 30, f"Expected 30 hypothesis tests, got {len(tests)}"

    effects = load_effect_sizes()
    assert len(effects) == 24, f"Expected 24 effect-size rows, got {len(effects)}"

    comp = load_operation_composition()
    assert len(comp) == 38, f"Expected 38 operation composition rows, got {len(comp)}"

    cjson = load_cjson_summary()
    assert len(cjson) == 8, f"Expected 8 cJSON rows, got {len(cjson)}"


def test_manifest_and_report_loader():
    """Verify manifest and report text load properly."""
    manifest = load_manifest()
    assert "total_traces" in manifest
    assert manifest["total_traces"] == 38

    report_text = load_analysis_report_text()
    assert len(report_text) > 1000
    assert "ColliScope Phase 8: Statistical Analysis Report" in report_text


def test_svc_diagnostics_loader():
    """Verify SVC-Hash diagnostics load from Phase 7 JSON."""
    diag = load_svc_diagnostics()
    assert not diag.empty
    assert "svc_kicks" in diag.columns
    assert "svc_rebuilds" in diag.columns
    assert "svc_stash_count" in diag.columns
    assert "svc_tombstones" in diag.columns
    # Stash and tombstones must be 0
    assert diag["svc_stash_count"].max() == 0.0
    assert diag["svc_tombstones"].max() == 0.0


def test_cjson_case_study_integrity():
    """Verify cJSON summary maintains single project x two scope representations."""
    cjson = load_cjson_summary()
    assert sorted(cjson["scope_mode"].unique().tolist()) == ["flat", "nested"]
    assert len(cjson["trace_name"].unique()) == 2
    # Verify SVC-Hash wins on nested cJSON
    nest_svc = cjson[(cjson["scope_mode"] == "nested") & (cjson["algorithm_name"] == "svc_hash")]
    assert not nest_svc.empty
    svc_tp = nest_svc["throughput_ops_sec"].iloc[0]
    for _, r in cjson[(cjson["scope_mode"] == "nested") & (cjson["algorithm_name"] != "svc_hash")].iterrows():
        assert svc_tp > r["throughput_ops_sec"], f"SVC should outperform {r['algorithm_name']} on cJSON nested"


def test_views_importable():
    """Verify all 5 main section view modules can be imported cleanly."""
    from dashboard.views.overview import render_overview
    from dashboard.views.interactive_lab import render_interactive_lab
    from dashboard.views.algorithm_comparison import render_algorithm_comparison
    from dashboard.views.scope_and_svc import render_scope_and_svc
    from dashboard.views.experimental_results import render_experimental_results

    assert callable(render_overview)
    assert callable(render_interactive_lab)
    assert callable(render_algorithm_comparison)
    assert callable(render_scope_and_svc)
    assert callable(render_experimental_results)


def test_view_functions_execute_directly():
    """Directly execute each section renderer to guarantee zero column KeyErrors or runtime issues."""
    from dashboard.views.overview import render_overview
    from dashboard.views.interactive_lab import render_interactive_lab
    from dashboard.views.algorithm_comparison import render_algorithm_comparison
    from dashboard.views.scope_and_svc import render_scope_and_svc
    from dashboard.views.experimental_results import render_experimental_results

    render_overview()
    render_interactive_lab()
    render_algorithm_comparison()
    render_scope_and_svc()
    render_experimental_results()


def test_all_dashboard_pages_render():
    """Verify that every single dashboard section renders without unhandled exceptions."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(os.path.join(REPO_ROOT, "dashboard", "app.py"), default_timeout=30)
    at.run()
    assert not at.exception, f"Overview section raised exception: {at.exception}"

    nav_options = [
        "1. Overview",
        "2. Interactive Symbol Table Lab",
        "3. Algorithm Comparison",
        "4. Scope & SVC-Hash",
        "5. Experimental Results & Provenance"
    ]

    for page in nav_options:
        at.sidebar.radio[0].set_value(page)
        at.run()
        assert not at.exception, f"Section '{page}' raised exception: {at.exception}"

