import json
import os
import pytest
from workloads.trace_validator import TraceValidator

def test_python_parse_sample_lexical_trace():
    trace_path = os.path.join("workloads", "traces", "sample_lexical.trace")
    assert os.path.exists(trace_path)

    commands = TraceValidator.parse_file(trace_path)
    assert len(commands) > 0

    op_counts = {}
    for cmd in commands:
        op_counts[cmd.op] = op_counts.get(cmd.op, 0) + 1

    assert op_counts["ENTER_SCOPE"] == 3
    assert op_counts["EXIT_SCOPE"] == 3
    assert op_counts["DECLARE"] == 5
    assert op_counts["REFERENCE"] == 12

def test_python_sample_lexical_expected_json():
    json_path = os.path.join("workloads", "traces", "sample_lexical.expected.json")
    assert os.path.exists(json_path)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["trace_file"] == "sample_lexical.trace"
    assert data["total_references"] == 12
    assert data["successful_references"] == 10
    assert data["failed_references"] == 2
    assert len(data["expected_references"]) == 12

def test_python_trace_validator_malformed_rejection():
    with pytest.raises(ValueError, match="missing scope_id"):
        TraceValidator.parse_string("ENTER_SCOPE\n")

    with pytest.raises(ValueError, match="missing identifier"):
        TraceValidator.parse_string("DECLARE\n")

    with pytest.raises(ValueError, match="Unknown operation"):
        TraceValidator.parse_string("UNKNOWN_OP foo\n")

    with pytest.raises(ValueError, match="Invalid identifier"):
        TraceValidator.parse_string("DECLARE 99bad\n")
