import pytest
from workloads.config_schema import BenchmarkConfig, OperationMix, IdentifierDimension, ScopeDimension, WorkloadType
from workloads.trace_validator import TraceValidator

def test_svc_hash_config_validation():
    config = BenchmarkConfig(
        identifier_dimension=IdentifierDimension.RANDOM,
        scope_dimension=ScopeDimension.NESTED,
        workload_type=WorkloadType.MIXED,
        load_factor=0.75,
        operation_mix=OperationMix(insert_ratio=0.3, lookup_ratio=0.5, scope_ratio=0.2),
        algorithms=["svc_hash"],
        repetitions=10
    )
    # validate() raises ValueError if invalid; if valid, it finishes silently
    config.validate()
    assert "svc_hash" in config.algorithms

def test_svc_hash_trace_validation():
    # Sample trace matching docs/trace_format.md for svc_hash
    sample_trace = (
        "ENTER_SCOPE 0 0\n"
        "DECLARE var_a 1 0\n"
        "ENTER_SCOPE 1 0\n"
        "DECLARE var_b 2 1\n"
        "REFERENCE var_a 1\n"
        "EXIT_SCOPE 1\n"
        "REFERENCE var_a 0\n"
    )
    commands = TraceValidator.parse_string(sample_trace)
    assert len(commands) == 7
    assert commands[0].op == "ENTER_SCOPE"
    assert commands[1].op == "DECLARE"
    assert commands[1].identifier == "var_a"
    assert commands[5].op == "EXIT_SCOPE"
