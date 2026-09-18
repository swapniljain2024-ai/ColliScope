"""
ColliScope Configuration Schema (Python)
Matches src/common/config.hpp for end-to-end configuration compatibility.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Dict, Any
import json
import os

class IdentifierDimension(str, Enum):
    RANDOM = "random"
    REAL_SOURCE = "real-source"
    FREQUENCY_MATCHED = "frequency-matched"

class ScopeDimension(str, Enum):
    FLAT = "flat"
    NESTED = "nested"

class WorkloadType(str, Enum):
    DECLARATION_HEAVY = "declaration-heavy"
    LOOKUP_HEAVY = "lookup-heavy"
    MIXED = "mixed"

@dataclass
class OperationMix:
    insert_ratio: float = 0.4
    lookup_ratio: float = 0.5
    scope_ratio: float = 0.1

    def validate(self):
        if self.insert_ratio < 0.0 or self.lookup_ratio < 0.0 or self.scope_ratio < 0.0:
            raise ValueError("Operation mix ratios must be non-negative")
        total = self.insert_ratio + self.lookup_ratio + self.scope_ratio
        if abs(total - 1.0) > 1e-4:
            raise ValueError(f"Operation mix ratios must sum to 1.0 (got {total:.4f})")

@dataclass
class BenchmarkConfig:
    identifier_dimension: IdentifierDimension = IdentifierDimension.RANDOM
    scope_dimension: ScopeDimension = ScopeDimension.FLAT
    workload_type: WorkloadType = WorkloadType.MIXED
    load_factor: float = 0.70
    operation_mix: OperationMix = field(default_factory=OperationMix)
    algorithms: List[str] = field(default_factory=lambda: ["chaining", "cuckoo", "hopscotch", "svc_hash"])
    repetitions: int = 30
    num_operations: int = 10000
    max_scope_depth: int = 8

    def validate(self):
        if not (0.0 < self.load_factor <= 1.0):
            raise ValueError(f"Load factor must be in (0.0, 1.0], got {self.load_factor}")
        if self.repetitions < 1:
            raise ValueError("Repetitions must be at least 1")
        if self.num_operations < 1:
            raise ValueError("Number of operations must be at least 1")
        if not self.algorithms:
            raise ValueError("At least one algorithm must be specified")
        valid_algos = {"chaining", "cuckoo", "hopscotch", "svc_hash", "coalesced"}
        for algo in self.algorithms:
            if algo not in valid_algos:
                raise ValueError(f"Unsupported algorithm: '{algo}'")
        self.operation_mix.validate()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "identifier_dimension": self.identifier_dimension.value,
            "scope_dimension": self.scope_dimension.value,
            "workload_type": self.workload_type.value,
            "load_factor": self.load_factor,
            "operation_mix": asdict(self.operation_mix),
            "algorithms": self.algorithms,
            "repetitions": self.repetitions,
            "num_operations": self.num_operations,
            "max_scope_depth": self.max_scope_depth,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BenchmarkConfig":
        op_mix_data = data.get("operation_mix", {})
        op_mix = OperationMix(
            insert_ratio=op_mix_data.get("insert_ratio", 0.4),
            lookup_ratio=op_mix_data.get("lookup_ratio", 0.5),
            scope_ratio=op_mix_data.get("scope_ratio", 0.1),
        )
        cfg = cls(
            identifier_dimension=IdentifierDimension(data["identifier_dimension"]),
            scope_dimension=ScopeDimension(data["scope_dimension"]),
            workload_type=WorkloadType(data["workload_type"]),
            load_factor=float(data["load_factor"]),
            operation_mix=op_mix,
            algorithms=data.get("algorithms", ["chaining", "cuckoo", "hopscotch", "svc_hash"]),
            repetitions=int(data.get("repetitions", 30)),
            num_operations=int(data.get("num_operations", 10000)),
            max_scope_depth=int(data.get("max_scope_depth", 8)),
        )
        cfg.validate()
        return cfg

    @classmethod
    def from_json_file(cls, filepath: str) -> "BenchmarkConfig":
        with open(filepath, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))
