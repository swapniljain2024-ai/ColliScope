"""
ColliScope Workload Matrix Assembler

Orchestrates the generation of the authoritative experimental matrix:
- 36 synthetic traces:
  2 identifier distributions (random, frequency-matched)
  x 2 scope modes (flat, nested)
  x 3 workload types (declaration-heavy, lookup-heavy, mixed)
  x 3 deterministic seed replicates (rep1, rep2, rep3)
- 2 authentic real-source traces:
  cJSON flat + cJSON nested

Total: 38 authoritative experimental traces.
Serializes generated traces to workloads/traces/ and writes a structured manifest.json.
"""

import os
import json
import argparse
from typing import List, Dict, Any, Optional

from workloads.config_schema import (
    IdentifierDimension, ScopeDimension, WorkloadType
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
        num_replicates: int = 3,
        num_operations: int = 1000,
        load_factors: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """
        Generates the authoritative experimental matrix of traces and writes manifest.json.
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

        manifest_entries: List[Dict[str, Any]] = []

        # 1. Real-Source Workloads (authentic extracted C corpus: exactly 1 trace per scope mode)
        if IdentifierDimension.REAL_SOURCE in identifier_dims:
            if not os.path.exists(self.real_source_file):
                raise FileNotFoundError(f"Real source corpus not found: {self.real_source_file}")
            real_extractor = RealSourceExtractor(self.real_source_file)

            for scope_dim in scope_dims:
                is_flat = (scope_dim == ScopeDimension.FLAT)
                filename = f"trace_real-source_{scope_dim.value}.trace"
                filepath = os.path.join(self.output_dir, filename)

                cmds = real_extractor.extract(max_operations=num_operations, flat_scope=is_flat)

                with open(filepath, "w", encoding="utf-8") as f:
                    f.write("\n".join(cmds))

                parsed_cmds = TraceValidator.parse_file(filepath)

                decl_count = sum(1 for c in parsed_cmds if c.op == "DECLARE")
                ref_count = sum(1 for c in parsed_cmds if c.op == "REFERENCE")
                enter_count = sum(1 for c in parsed_cmds if c.op == "ENTER_SCOPE")
                exit_count = sum(1 for c in parsed_cmds if c.op == "EXIT_SCOPE")
                unique_symbols = len(set(c.identifier for c in parsed_cmds if c.identifier))

                entry = {
                    "trace_file": filename,
                    "identifier_dimension": "real-source",
                    "scope_dimension": scope_dim.value,
                    "source_corpus": "cJSON",
                    "source_repository": "https://github.com/DaveGamble/cJSON.git",
                    "source_version": "v1.7.18",
                    "source_commit": "acc76239bee01d8e9c858ae2cab296704e52d916",
                    "license": "MIT",
                    "total_commands": len(parsed_cmds),
                    "declaration_count": decl_count,
                    "reference_count": ref_count,
                    "enter_scope_count": enter_count,
                    "exit_scope_count": exit_count,
                    "unique_symbols": unique_symbols,
                }
                manifest_entries.append(entry)

        # 2. Synthetic Workloads (random and frequency-matched parameterized by scope, mix, and seed replicates)
        synthetic_dims = [d for d in identifier_dims if d != IdentifierDimension.REAL_SOURCE]
        reps = len(load_factors) if (load_factors is not None and num_replicates == 3) else num_replicates

        seed_offset = 0
        for ident_dim in synthetic_dims:
            for scope_dim in scope_dims:
                for w_type in workload_types:
                    for rep_idx in range(1, reps + 1):
                        seed = self.base_seed + seed_offset
                        seed_offset += 1

                        filename = f"trace_{ident_dim.value}_{scope_dim.value}_{w_type.value}_rep{rep_idx}.trace"
                        filepath = os.path.join(self.output_dir, filename)

                        if ident_dim == IdentifierDimension.RANDOM:
                            gen = RandomTraceGenerator(
                                seed=seed,
                                num_operations=num_operations,
                                scope_dimension=scope_dim,
                                workload_type=w_type,
                                replicate_index=rep_idx
                            )
                            cmds = gen.generate()
                        elif ident_dim == IdentifierDimension.FREQUENCY_MATCHED:
                            gen = FrequencyMatchedTraceGenerator(
                                seed=seed,
                                num_operations=num_operations,
                                scope_dimension=scope_dim,
                                workload_type=w_type,
                                replicate_index=rep_idx,
                                zipf_s=1.244
                            )
                            cmds = gen.generate()

                        with open(filepath, "w", encoding="utf-8") as f:
                            f.write("\n".join(cmds))

                        parsed_cmds = TraceValidator.parse_file(filepath)

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
                            "replicate_index": rep_idx,
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
            "version": "2.0.0",
            "matrix_specification": "36 synthetic traces (2 distributions x 2 scopes x 3 mixes x 3 seed replicates) + 2 authentic real-source traces (cJSON flat + nested)",
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
    parser.add_argument("--replicates", type=int, default=3, help="Seed replicates per condition")
    args = parser.parse_args()

    assembler = WorkloadMatrixAssembler(output_dir=args.output_dir)
    manifest = assembler.assemble_matrix(num_replicates=args.replicates, num_operations=args.num_ops)
    print(f"Successfully generated {manifest['total_traces']} traces in {args.output_dir}.")

if __name__ == "__main__":
    main()
