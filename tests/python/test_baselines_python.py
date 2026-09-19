import pytest
from workloads.config_schema import BenchmarkConfig

def test_python_baseline_algorithms_valid():
    for algo in ["chaining", "cuckoo", "hopscotch", "svc_hash"]:
        config_data = {
            "identifier_dimension": "random",
            "scope_dimension": "flat",
            "workload_type": "mixed",
            "load_factor": 0.75,
            "algorithms": [algo],
            "repetitions": 10,
            "num_operations": 500
        }
        cfg = BenchmarkConfig.from_dict(config_data)
        assert cfg.algorithms == [algo]

def test_python_all_baselines_in_config():
    config_data = {
        "identifier_dimension": "frequency-matched",
        "scope_dimension": "nested",
        "workload_type": "lookup-heavy",
        "load_factor": 0.80,
        "algorithms": ["chaining", "cuckoo", "hopscotch", "svc_hash"],
        "repetitions": 30,
        "num_operations": 10000
    }
    cfg = BenchmarkConfig.from_dict(config_data)
    assert len(cfg.algorithms) == 4
    assert "chaining" in cfg.algorithms
    assert "cuckoo" in cfg.algorithms
    assert "hopscotch" in cfg.algorithms
    assert "svc_hash" in cfg.algorithms
