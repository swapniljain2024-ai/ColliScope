"""
Phase 1 Python Tests: Config Schema & Trace Validator
"""

import pytest
import json
from workloads.config_schema import (
    BenchmarkConfig,
    IdentifierDimension,
    ScopeDimension,
    WorkloadType,
    OperationMix
)
from workloads.trace_validator import TraceValidator

def test_python_benchmark_config_valid():
    cfg = BenchmarkConfig(
        identifier_dimension=IdentifierDimension.REAL_SOURCE,
        scope_dimension=ScopeDimension.NESTED,
        workload_type=WorkloadType.LOOKUP_HEAVY,
        load_factor=0.80,
        operation_mix=OperationMix(insert_ratio=0.3, lookup_ratio=0.6, scope_ratio=0.1),
        algorithms=["cuckoo", "svc_hash"],
        repetitions=20,
        num_operations=25000,
        max_scope_depth=12
    )
    cfg.validate()
    
    # Test JSON round-trip
    json_str = cfg.to_json()
    loaded = BenchmarkConfig.from_dict(json.loads(json_str))
    assert loaded.identifier_dimension == IdentifierDimension.REAL_SOURCE
    assert loaded.scope_dimension == ScopeDimension.NESTED
    assert loaded.load_factor == 0.80
    assert loaded.repetitions == 20

def test_python_benchmark_config_invalid():
    with pytest.raises(ValueError, match="Load factor"):
        BenchmarkConfig(load_factor=1.5).validate()

    with pytest.raises(ValueError, match="Operation mix ratios must sum to 1.0"):
        BenchmarkConfig(
            operation_mix=OperationMix(insert_ratio=0.5, lookup_ratio=0.8, scope_ratio=0.1)
        ).validate()

    with pytest.raises(ValueError, match="Unsupported algorithm"):
        BenchmarkConfig(algorithms=["linear_probing"]).validate()

def test_python_trace_validator_valid():
    trace_text = """
    # Sample valid trace
    ENTER_SCOPE 0
    DECLARE global_item 1 0
    ENTER_SCOPE 1 0
    DECLARE inner_item 2 1
    REFERENCE global_item 1
    EXIT_SCOPE 1
    EXIT_SCOPE 0
    """
    cmds = TraceValidator.parse_string(trace_text)
    assert len(cmds) == 7
    assert cmds[0].op == "ENTER_SCOPE"
    assert cmds[0].scope_id == 0
    assert cmds[1].op == "DECLARE"
    assert cmds[1].identifier == "global_item"
    assert cmds[4].op == "REFERENCE"
    assert cmds[5].op == "EXIT_SCOPE"

def test_python_trace_validator_invalid():
    with pytest.raises(ValueError, match="Unknown operation"):
        TraceValidator.parse_string("INVALID_OP something")

    with pytest.raises(ValueError, match="missing identifier"):
        TraceValidator.parse_string("DECLARE")

    with pytest.raises(ValueError, match="Invalid identifier"):
        TraceValidator.parse_string("DECLARE 9invalid_id 1 0")

    with pytest.raises(ValueError, match="missing scope_id"):
        TraceValidator.parse_string("ENTER_SCOPE")
