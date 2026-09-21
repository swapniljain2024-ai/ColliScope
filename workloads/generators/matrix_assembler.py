"""
ColliScope Workload Matrix Assembler

Orchestrates the generation of the full experimental matrix:
Identifier Dimension x Scope Dimension x Workload Type x Load Factor.
Serializes generated traces to workloads/traces/ and writes a structured manifest.json.
"""

import os
import json
import argparse
from typing import List, Dict, Any, Optional

from workloads.config_schema import (
    IdentifierDimension, ScopeDimension, WorkloadType, BenchmarkConfig
)
from workloads.generators.random_generator import RandomTraceGenerator
from workloads.generators.real_source_extractor import RealSourceExtractor
from workloads.generators.frequency_matched_generator import FrequencyMatchedTraceGenerator
from workloads.trace_validator import TraceValidator

class WorkloadMatrixAssembler:
    def __init__(
        self,
        output_dir: str = "workloads/traces",
        real_source_file: str = "workloads/real_source/cJSON/cJSON.c",
        base_seed: int = 42
    ):
        self.output_dir = output_dir
        self.real_source_file = real_source_file
        self.base_seed = base_seed
        os.makedirs(output_dir, exist_ok=True)

    def assemble_matrix(
        self,
        identifier_dims: Optional[List[IdentifierDimension]] = None,
        scope_dims: Optional[List[ScopeDimension]] = None,
        workload_types: Optional[List[WorkloadType]] = None,
        load_factors: Optional[List[float]] = None,
        num_operations: int = 1000
    ) -> Dict[str, Any]:
        """
        Generates the cross-product matrix of traces and writes manifest.json.
        """
        if identifier_dims is None:
            identifier_dims = [
                IdentifierDimension.RANDOM,
                IdentifierDimension.REAL_SOURCE,
                IdentifierDimension.FREQUENCY_MATCHED
            ]
        if scope_dims is None:
            scope_dims = [ScopeDimension.FLAT, ScopeDimension.NESTED]
        if workload_types is None:
            workload_types = [
                WorkloadType.DECLARATION_HEAVY,
                WorkloadType.LOOKUP_HEAVY,
                WorkloadType.MIXED
            ]
        if load_factors is None:
            # Core standard benchmark load factors
            load_factors = [0.50, 0.70, 0.90]

        manifest_entries: List[Dict[str, Any]] = []
        seed_offset = 0

        # Pre-extract real source if needed
        real_extractor = None
        if IdentifierDimension.REAL_SOURCE in identifier_dims or IdentifierDimension.FREQUENCY_MATCHED in identifier_dims:
            if os.path.exists(self.real_source_file):
                real_extractor = RealSourceExtractor(self.real_source_file)
                # Run extraction to compute statistics and Zipf parameter
                real_extractor.extract(max_operations=num_operations, flat_scope=False)

        for ident_dim in identifier_dims:
            for scope_dim in scope_dims:
                for w_type in workload_types:
                    for lf in load_factors:
                        seed = self.base_seed + seed_offset
                        seed_offset += 1

                        lf_str = f"{int(lf * 100):02d}"
                        filename = f"trace_{ident_dim.value}_{scope_dim.value}_{w_type.value}_lf{lf_str}.trace"
                        filepath = os.path.join(self.output_dir, filename)

                        # Generate trace commands
                        if ident_dim == IdentifierDimension.RANDOM:
                            gen = RandomTraceGenerator(
                                seed=seed,
                                num_operations=num_operations,
                                scope_dimension=scope_dim,
                                workload_type=w_type,
                                load_factor=lf
                            )
                            cmds = gen.generate()

                        elif ident_dim == IdentifierDimension.REAL_SOURCE:
                            if real_extractor is None:
                                raise FileNotFoundError(f"Real source corpus not found: {self.real_source_file}")
                            is_flat = (scope_dim == ScopeDimension.FLAT)
                            cmds = real_extractor.extract(max_operations=num_operations, flat_scope=is_flat)

                        elif ident_dim == IdentifierDimension.FREQUENCY_MATCHED:
                            gen = FrequencyMatchedTraceGenerator(
                                seed=seed,
                                num_operations=num_operations,
                                scope_dimension=scope_dim,
                                workload_type=w_type,
                                load_factor=lf,
                                zipf_s=1.244
                            )
                            cmds = gen.generate()

                        # Write trace file
                        with open(filepath, "w", encoding="utf-8") as f:
                            f.write("\n".join(cmds))

                        # Validate generated trace
                        parsed_cmds = TraceValidator.parse_file(filepath)

                        # Compute trace statistics
                        decl_count = sum(1 for c in parsed_cmds if c.op == "DECLARE")
                        ref_count = sum(1 for c in parsed_cmds if c.op == "REFERENCE")
                        enter_count = sum(1 for c in parsed_cmds if c.op == "ENTER_SCOPE")
                        exit_count = sum(1 for c in parsed_cmds if c.op == "EXIT_SCOPE")
                        unique_symbols = len(set(c.identifier for c in parsed_cmds if c.identifier))

                        entry = {
                            "trace_file": filename,
                            "identifier_dimension": ident_dim.value,
                            "scope_dimension": scope_dim.value,
                            "workload_type": w_type.value,
                            "load_factor": lf,
                            "seed": seed,
                            "total_commands": len(parsed_cmds),
                            "declaration_count": decl_count,
                            "reference_count": ref_count,
                            "enter_scope_count": enter_count,
                            "exit_scope_count": exit_count,
                            "unique_symbols": unique_symbols,
                        }
                        manifest_entries.append(entry)

        manifest = {
            "version": "1.0.0",
            "total_traces": len(manifest_entries),
            "traces": manifest_entries
        }

        manifest_path = os.path.join(self.output_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return manifest

def main():
    parser = argparse.ArgumentParser(description="ColliScope Workload Matrix Generator")
    parser.add_argument("--output-dir", default="workloads/traces", help="Target trace directory")
    parser.add_argument("--num-ops", type=int, default=1000, help="Operation count per trace")
    parser.add_argument("--full-matrix", action="store_true", help="Generate 6 load factors (full 108 traces)")
    args = parser.parse_args()

    load_factors = [0.25, 0.40, 0.55, 0.70, 0.80, 0.90] if args.full_matrix else [0.50, 0.70, 0.90]
    assembler = WorkloadMatrixAssembler(output_dir=args.output_dir)
    manifest = assembler.assemble_matrix(load_factors=load_factors, num_operations=args.num_ops)
    print(f"Successfully generated {manifest['total_traces']} traces in {args.output_dir}.")

if __name__ == "__main__":
    main()
