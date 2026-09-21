"""
ColliScope Random Workload Generator

Produces deterministic, schema-valid execution traces (.trace) using synthetic
random identifiers, configurable scope nesting, operation mix ratios, and load factors.
Strictly adheres to the Phase 4 Trace Contract (no duplicate declarations within the same scope).
"""

import random
import string
from typing import List, Optional, Set, Dict
from workloads.config_schema import BenchmarkConfig, ScopeDimension, WorkloadType, OperationMix

class RandomTraceGenerator:
    def __init__(
        self,
        config: Optional[BenchmarkConfig] = None,
        seed: int = 42,
        num_operations: int = 1000,
        scope_dimension: ScopeDimension = ScopeDimension.FLAT,
        workload_type: WorkloadType = WorkloadType.MIXED,
        load_factor: float = 0.70,
        max_scope_depth: int = 8,
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
        self.miss_rate = miss_rate
        self.rng = random.Random(seed)

    @staticmethod
    def _preset_operation_mix(workload_type: WorkloadType) -> OperationMix:
        if workload_type == WorkloadType.DECLARATION_HEAVY:
            return OperationMix(insert_ratio=0.60, lookup_ratio=0.30, scope_ratio=0.10)
        elif workload_type == WorkloadType.LOOKUP_HEAVY:
            return OperationMix(insert_ratio=0.10, lookup_ratio=0.80, scope_ratio=0.10)
        else: # MIXED
            return OperationMix(insert_ratio=0.40, lookup_ratio=0.50, scope_ratio=0.10)

    def _generate_identifier(self, index: int) -> str:
        prefix = "".join(self.rng.choices(string.ascii_lowercase, k=3))
        return f"{prefix}_{index:05d}"

    def generate(self) -> List[str]:
        self.rng.seed(self.seed)
        commands: List[str] = []

        next_scope_id = 1
        active_scope_stack: List[int] = [0]
        scope_declarations: Dict[int, Set[str]] = {0: set()}
        scope_parents: Dict[int, int] = {0: 0}

        identifier_pool: List[str] = []
        global_id_counter = 0

        commands.append("# ColliScope Generated Random Trace")
        commands.append(f"# Parameters: seed={self.seed}, scope={self.scope_dimension.value}, "
                        f"type={self.workload_type.value}, load_factor={self.load_factor}")
        commands.append("ENTER_SCOPE 0")

        initial_decl_count = max(5, int(self.num_operations * 0.05))
        for _ in range(initial_decl_count):
            ident = self._generate_identifier(global_id_counter)
            global_id_counter += 1
            identifier_pool.append(ident)
            curr_scope = active_scope_stack[-1]
            type_id = self.rng.randint(1, 20)
            commands.append(f"DECLARE {ident} {type_id} {curr_scope}")
            scope_declarations[curr_scope].add(ident)

        remaining_ops = self.num_operations - initial_decl_count

        for _ in range(remaining_ops):
            curr_scope = active_scope_stack[-1]
            curr_depth = len(active_scope_stack)

            roll = self.rng.random()
            is_nested = (self.scope_dimension == ScopeDimension.NESTED)

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
                curr_scope = active_scope_stack[-1]
                can_shadow = False
                shadow_candidate = None
                if is_nested and curr_scope != 0 and self.rng.random() < 0.25:
                    ancestor = scope_parents.get(curr_scope, 0)
                    while ancestor != curr_scope:
                        ancestor_decls = scope_declarations.get(ancestor, set()) - scope_declarations[curr_scope]
                        if ancestor_decls:
                            shadow_candidate = self.rng.choice(list(ancestor_decls))
                            can_shadow = True
                            break
                        if ancestor == 0:
                            break
                        ancestor = scope_parents.get(ancestor, 0)

                if can_shadow and shadow_candidate:
                    ident = shadow_candidate
                else:
                    ident = self._generate_identifier(global_id_counter)
                    global_id_counter += 1
                    identifier_pool.append(ident)

                if ident not in scope_declarations[curr_scope]:
                    type_id = self.rng.randint(1, 20)
                    commands.append(f"DECLARE {ident} {type_id} {curr_scope}")
                    scope_declarations[curr_scope].add(ident)
                else:
                    commands.append(f"REFERENCE {ident} {curr_scope}")

            else:
                curr_scope = active_scope_stack[-1]
                visible_identifiers: List[str] = []
                walk = curr_scope
                visited_root = False
                while not visited_root:
                    visible_identifiers.extend(scope_declarations.get(walk, set()))
                    if walk == 0:
                        visited_root = True
                    else:
                        walk = scope_parents.get(walk, 0)

                if visible_identifiers and self.rng.random() >= self.miss_rate:
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
