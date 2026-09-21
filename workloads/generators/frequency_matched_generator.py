"""
ColliScope Frequency-Matched Synthetic Workload Generator

Produces synthetic execution traces whose identifier frequency distribution
is fit to match the empirical Zipf-like rank-frequency distribution observed
in real-world C/C++ compiler workloads, without reusing real identifiers verbatim.
"""

import random
import string
import numpy as np
from typing import List, Optional, Set, Dict
from workloads.config_schema import BenchmarkConfig, ScopeDimension, WorkloadType, OperationMix

class FrequencyMatchedTraceGenerator:
    def __init__(
        self,
        config: Optional[BenchmarkConfig] = None,
        seed: int = 42,
        num_operations: int = 1000,
        scope_dimension: ScopeDimension = ScopeDimension.FLAT,
        workload_type: WorkloadType = WorkloadType.MIXED,
        load_factor: float = 0.70,
        max_scope_depth: int = 8,
        zipf_s: float = 1.244,
        num_symbols: int = 300,
        miss_rate: float = 0.15
    ):
        if config is not None:
            self.num_operations = config.num_operations
            self.scope_dimension = config.scope_dimension
            self.workload_type = config.workload_type
            self.load_factor = config.load_factor
            self.max_scope_depth = config.max_scope_depth
            self.operation_mix = config.operation_mix
        else:
            self.num_operations = num_operations
            self.scope_dimension = scope_dimension
            self.workload_type = workload_type
            self.load_factor = load_factor
            self.max_scope_depth = max_scope_depth
            self.operation_mix = self._preset_operation_mix(workload_type)

        self.seed = seed
        self.zipf_s = zipf_s
        self.num_symbols = num_symbols
        self.miss_rate = miss_rate
        self.rng = random.Random(seed)
        self.np_rng = np.random.default_rng(seed)

        # Precompute Zipf sampling probabilities for synthetic symbols
        ranks = np.arange(1, self.num_symbols + 1)
        weights = 1.0 / (ranks ** self.zipf_s)
        self.zipf_probs = weights / np.sum(weights)

    @staticmethod
    def _preset_operation_mix(workload_type: WorkloadType) -> OperationMix:
        if workload_type == WorkloadType.DECLARATION_HEAVY:
            return OperationMix(insert_ratio=0.60, lookup_ratio=0.30, scope_ratio=0.10)
        elif workload_type == WorkloadType.LOOKUP_HEAVY:
            return OperationMix(insert_ratio=0.10, lookup_ratio=0.80, scope_ratio=0.10)
        else:
            return OperationMix(insert_ratio=0.40, lookup_ratio=0.50, scope_ratio=0.10)

    def _generate_synthetic_pool(self) -> List[str]:
        # Generate fresh, synthetic identifiers matching rank order
        pool = []
        for i in range(self.num_symbols):
            pool.append(f"sym_k{i:04d}")
        return pool

    def generate(self) -> List[str]:
        self.rng.seed(self.seed)
        self.np_rng = np.random.default_rng(self.seed)

        commands: List[str] = []
        commands.append("# ColliScope Frequency-Matched Synthetic Trace")
        commands.append(f"# Parameters: seed={self.seed}, zipf_s={self.zipf_s:.3f}, "
                        f"scope={self.scope_dimension.value}, type={self.workload_type.value}, "
                        f"load_factor={self.load_factor}")
        commands.append("ENTER_SCOPE 0")

        synthetic_pool = self._generate_synthetic_pool()

        active_scope_stack: List[int] = [0]
        scope_declarations: Dict[int, Set[str]] = {0: set()}
        scope_parents: Dict[int, int] = {0: 0}
        next_scope_id = 1

        # Seed global scope with most frequent symbols (rank 0..10)
        initial_decl_count = max(5, int(self.num_operations * 0.05))
        for i in range(initial_decl_count):
            ident = synthetic_pool[i % self.num_symbols]
            curr_scope = active_scope_stack[-1]
            if ident not in scope_declarations[curr_scope]:
                type_id = (i % 10) + 1
                commands.append(f"DECLARE {ident} {type_id} {curr_scope}")
                scope_declarations[curr_scope].add(ident)

        remaining_ops = self.num_operations - len(scope_declarations[0])

        for _ in range(remaining_ops):
            curr_scope = active_scope_stack[-1]
            curr_depth = len(active_scope_stack)
            is_nested = (self.scope_dimension == ScopeDimension.NESTED)

            roll = self.rng.random()

            if is_nested and roll < self.operation_mix.scope_ratio:
                can_enter = (curr_depth < self.max_scope_depth)
                can_exit = (curr_depth > 1)

                if can_enter and (not can_exit or self.rng.random() < 0.6):
                    new_scope = next_scope_id
                    next_scope_id += 1
                    commands.append(f"ENTER_SCOPE {new_scope} {curr_scope}")
                    active_scope_stack.append(new_scope)
                    scope_declarations[new_scope] = set()
                    scope_parents[new_scope] = curr_scope
                elif can_exit:
                    exiting_scope = active_scope_stack.pop()
                    commands.append(f"EXIT_SCOPE {exiting_scope}")

            elif roll < (self.operation_mix.scope_ratio + self.operation_mix.insert_ratio):
                # Sample identifier according to Zipf distribution
                idx = self.np_rng.choice(self.num_symbols, p=self.zipf_probs)
                ident = synthetic_pool[idx]

                if ident not in scope_declarations[curr_scope]:
                    type_id = (idx % 15) + 1
                    commands.append(f"DECLARE {ident} {type_id} {curr_scope}")
                    scope_declarations[curr_scope].add(ident)
                else:
                    commands.append(f"REFERENCE {ident} {curr_scope}")

            else:
                # Reference operation sampled by Zipf
                visible_identifiers: List[str] = []
                walk = curr_scope
                while True:
                    visible_identifiers.extend(scope_declarations.get(walk, set()))
                    if walk == 0:
                        break
                    walk = scope_parents.get(walk, 0)

                if visible_identifiers and self.rng.random() >= self.miss_rate:
                    # Choose according to Zipf weighting among visible symbols
                    idx = self.np_rng.choice(self.num_symbols, p=self.zipf_probs)
                    candidate = synthetic_pool[idx]
                    if candidate in visible_identifiers:
                        target = candidate
                    else:
                        target = self.rng.choice(visible_identifiers)
                    commands.append(f"REFERENCE {target} {curr_scope}")
                else:
                    miss_target = f"missing_{self.rng.randint(1000, 9999)}"
                    commands.append(f"REFERENCE {miss_target} {curr_scope}")

        while len(active_scope_stack) > 1:
            exiting_scope = active_scope_stack.pop()
            commands.append(f"EXIT_SCOPE {exiting_scope}")

        commands.append("EXIT_SCOPE 0")
        commands.append("")
        return commands

    def write_to_file(self, filepath: str) -> None:
        cmds = self.generate()
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(cmds))
