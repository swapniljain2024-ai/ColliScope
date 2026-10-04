"""
ColliScope Workload Generators and Matrix Assembly Tests (Phase 5)
"""

import os
import json
import pytest
from collections import Counter

from workloads.config_schema import (
    IdentifierDimension, ScopeDimension, WorkloadType, BenchmarkConfig
)
from workloads.generators.random_generator import RandomTraceGenerator
from workloads.generators.real_source_extractor import RealSourceExtractor
from workloads.generators.frequency_matched_generator import FrequencyMatchedTraceGenerator
from workloads.generators.matrix_assembler import WorkloadMatrixAssembler
from workloads.trace_validator import TraceValidator

def test_random_generator_flat_and_nested():
    # 1. Flat scope test
    gen_flat = RandomTraceGenerator(
        num_operations=300,
        scope_dimension=ScopeDimension.FLAT,
        workload_type=WorkloadType.MIXED,
        seed=101
    )
    cmds_flat = gen_flat.generate()
    parsed_flat = TraceValidator.parse_string("\n".join(cmds_flat))
    assert len(parsed_flat) > 0
    # On flat scope, only scope 0 should be entered/exited
    assert all(c.scope_id == 0 for c in parsed_flat if c.op in ("ENTER_SCOPE", "EXIT_SCOPE"))

    # 2. Nested scope test
    gen_nested = RandomTraceGenerator(
        num_operations=300,
        scope_dimension=ScopeDimension.NESTED,
        workload_type=WorkloadType.DECLARATION_HEAVY,
        max_scope_depth=6,
        seed=202
    )
    cmds_nested = gen_nested.generate()
    parsed_nested = TraceValidator.parse_string("\n".join(cmds_nested))
    assert len(parsed_nested) > 0
    enter_scopes = [c for c in parsed_nested if c.op == "ENTER_SCOPE"]
    exit_scopes = [c for c in parsed_nested if c.op == "EXIT_SCOPE"]
    assert len(enter_scopes) > 1
    assert len(enter_scopes) == len(exit_scopes)

def test_real_source_extractor_cjson():
    cjson_path = os.path.join("workloads", "real_source", "cJSON", "cJSON.c")
    assert os.path.exists(cjson_path), "cJSON.c corpus file must exist"

    extractor = RealSourceExtractor(cjson_path)
    cmds = extractor.extract(max_operations=500, flat_scope=False)
    assert len(cmds) > 0

    parsed = TraceValidator.parse_string("\n".join(cmds))
    assert len(parsed) > 0

    stats = extractor.statistics
    assert stats["extraction_method"] == "pycparser_ast_visitor"
    assert stats["unique_identifiers"] > 50
    assert stats["max_scope_depth"] >= 3
    assert stats["total_declarations"] > 0
    assert stats["total_references"] > 0
    assert stats["total_declarations"] < stats["total_references"]
    assert stats["in_unit_declarations"] == stats["total_declarations"]
    assert stats["external_symbols_count"] > 0
    assert stats["unresolved_external_references"] > 0
    assert stats["resolved_references"] > 0
    assert stats["resolved_references"] + stats["unresolved_external_references"] == stats["total_references"]


    # Also verify flat extraction mode (all operations at scope 0)
    cmds_flat = extractor.extract(max_operations=300, flat_scope=True)
    parsed_flat = TraceValidator.parse_string("\n".join(cmds_flat))
    assert len(parsed_flat) > 0
    assert all(c.scope_id == 0 for c in parsed_flat if c.op in ("ENTER_SCOPE", "EXIT_SCOPE"))
    assert all(c.scope_id == 0 for c in parsed_flat if c.op in ("DECLARE", "REFERENCE"))


def test_ast_extractor_c_constructs(tmp_path):
    """
    Granular verification of AST extraction on C constructs:
    - Global variable declarations
    - Function definitions and parameter declarations
    - Initializer references (int a = b + c;)
    - Compound statement block scopes (ENTER_SCOPE / EXIT_SCOPE)
    - Lexical shadowing (inner scope redeclaring outer identifier)
    - Typedef skipping (typedefs are types, not variable declarations)
    - Type casts (does not treat cast type as a variable declaration)
    - StructRef (does not conflate struct member fields as scope symbols)
    - Initializer lists (does not push false block scopes)
    """
    c_snippet = """
    typedef int my_custom_int;
    typedef struct Point {
        int x;
        int y;
    } Point;

    int g_factor = 10;

    int calculate(int base_val, int multiplier) {
        int initial_sum = base_val + g_factor;
        Point pt;
        pt.x = initial_sum;
        int arr[3] = { 1, 2, 3 };

        {
            int g_factor = 999;
            int inner_calc = (int)base_val * g_factor;
            return inner_calc;
        }

        return pt.x + multiplier;
    }
    """
    snippet_file = str(tmp_path / "snippet.c")
    with open(snippet_file, "w", encoding="utf-8") as f:
        f.write(c_snippet)

    extractor = RealSourceExtractor(snippet_file)
    cmds = extractor.extract(flat_scope=False)
    parsed = TraceValidator.parse_string("\n".join(cmds))

    # Map: (op, identifier, scope_id)
    decls = [(c.identifier, c.scope_id) for c in parsed if c.op == "DECLARE"]
    refs = [(c.identifier, c.scope_id) for c in parsed if c.op == "REFERENCE"]
    enters = [(c.scope_id, c.parent_scope_id) for c in parsed if c.op == "ENTER_SCOPE"]
    exits = [c.scope_id for c in parsed if c.op == "EXIT_SCOPE"]

    # 1. Global declarations
    assert ("g_factor", 0) in decls
    assert ("calculate", 0) in decls
    assert ("Point", 0) not in decls, "Typedef name must not be declared as variable"
    assert ("my_custom_int", 0) not in decls, "Typedef name must not be declared as variable"

    # 2. Function parameters declared in function body scope (scope 1)
    assert ("base_val", 1) in decls
    assert ("multiplier", 1) in decls
    assert ("initial_sum", 1) in decls
    assert ("pt", 1) in decls

    # 3. Initializer references: base_val and g_factor referenced in scope 1
    assert ("base_val", 1) in refs
    assert ("g_factor", 1) in refs

    # 4. Struct member access: pt is referenced, but field x is NOT a scope symbol
    assert ("pt", 1) in refs
    assert ("x", 1) not in decls, "Struct field x must not be a scope declaration"
    assert ("x", 1) not in refs, "Struct field x must not be a scope reference"

    # 5. Nested block scope (scope 2, parent 1)
    assert (2, 1) in enters
    assert 2 in exits

    # 6. Lexical Shadowing: g_factor declared in scope 2 (shadows scope 0)
    assert ("g_factor", 2) in decls
    assert ("inner_calc", 2) in decls
    assert ("g_factor", 2) in refs, "Reference inside scope 2 resolves shadowed g_factor"

    # 7. No duplicate declarations in the exact same scope
    seen_scope_keys = set()
    for ident, sc in decls:
        key = (ident, sc)
        assert key not in seen_scope_keys, f"Duplicate declaration in scope {sc}: {ident}"
        seen_scope_keys.add(key)

def test_frequency_matched_generator():
    gen = FrequencyMatchedTraceGenerator(
        num_operations=400,
        scope_dimension=ScopeDimension.NESTED,
        workload_type=WorkloadType.LOOKUP_HEAVY,
        seed=303,
        zipf_s=1.244
    )
    cmds = gen.generate()
    parsed = TraceValidator.parse_string("\n".join(cmds))
    assert len(parsed) > 0

    # Verify skew: top 10% of referenced identifiers should account for a disproportionate share
    ref_identifiers = [c.identifier for c in parsed if c.op == "REFERENCE" and not c.identifier.startswith("missing_")]
    counts = Counter(ref_identifiers).most_common()
    if len(counts) >= 10:
        top_2_count = sum(c for _, c in counts[:2])
        total_refs = len(ref_identifiers)
        assert top_2_count / total_refs > 0.05

def test_no_duplicate_declarations_in_same_scope():
    """
    Guarantees strict compliance with the Phase 4 / Phase 2 duplicate declaration prohibition contract.
    No trace should ever declare the same (identifier, scope_id) twice.
    """
    for gen in [
        RandomTraceGenerator(num_operations=500, scope_dimension=ScopeDimension.NESTED, seed=42),
        FrequencyMatchedTraceGenerator(num_operations=500, scope_dimension=ScopeDimension.NESTED, seed=42),
    ]:
        cmds = gen.generate()
        parsed = TraceValidator.parse_string("\n".join(cmds))
        seen_declarations = set()
        for cmd in parsed:
            if cmd.op == "DECLARE":
                key = (cmd.identifier, cmd.scope_id)
                assert key not in seen_declarations, f"Duplicate declaration detected: {key}"
                seen_declarations.add(key)

def test_matrix_assembler_cross_product(tmp_path):
    output_dir = str(tmp_path / "test_traces")
    assembler = WorkloadMatrixAssembler(output_dir=output_dir)

    manifest = assembler.assemble_matrix(
        identifier_dims=[IdentifierDimension.RANDOM, IdentifierDimension.FREQUENCY_MATCHED],
        scope_dims=[ScopeDimension.FLAT, ScopeDimension.NESTED],
        workload_types=[WorkloadType.DECLARATION_HEAVY, WorkloadType.LOOKUP_HEAVY],
        num_replicates=2,
        num_operations=100
    )

    # 2 ID dims x 2 scope dims x 2 workload types x 2 replicates = 16 traces expected
    assert manifest["total_traces"] == 16
    assert len(manifest["traces"]) == 16

    manifest_file = os.path.join(output_dir, "manifest.json")
    assert os.path.exists(manifest_file)

    for entry in manifest["traces"]:
        trace_path = os.path.join(output_dir, entry["trace_file"])
        assert os.path.exists(trace_path)
        cmds = TraceValidator.parse_file(trace_path)
        assert len(cmds) > 0

def test_manifest_integrity():
    manifest_path = os.path.join("workloads", "traces", "manifest.json")
    assert os.path.exists(manifest_path), "manifest.json must exist in workloads/traces/"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # 1. Total authoritative matrix trace count must be exactly 38
    assert manifest["total_traces"] == 38
    assert len(manifest["traces"]) == 38

    traces = manifest["traces"]
    synthetic_traces = [t for t in traces if t.get("identifier_dimension") != "real-source"]
    real_traces = [t for t in traces if t.get("identifier_dimension") == "real-source"]
    random_traces = [t for t in traces if t.get("identifier_dimension") == "random"]
    freq_traces = [t for t in traces if t.get("identifier_dimension") == "frequency-matched"]

    # 2. Partition counts: 36 synthetic (18 random + 18 freq-matched) + 2 real-source
    assert len(synthetic_traces) == 36
    assert len(real_traces) == 2
    assert len(random_traces) == 18
    assert len(freq_traces) == 18

    # 3. No synthetic or real trace has a nominal load-factor field
    for t in traces:
        assert "load_factor" not in t, f"Nominal load_factor found in {t['trace_file']}"

    # 4. Real-source traces are not assigned synthetic workload types
    for t in real_traces:
        assert "workload_type" not in t, f"Synthetic workload_type found on real-source {t['trace_file']}"
        assert "replicate_index" not in t, f"Synthetic replicate_index found on real-source {t['trace_file']}"
        assert t.get("source_corpus") == "cJSON"

    # 5. Each synthetic condition has exactly 3 deterministic replicates (rep1, rep2, rep3)
    conditions = {}
    for t in synthetic_traces:
        cond_key = (t["identifier_dimension"], t["scope_dimension"], t["workload_type"])
        conditions.setdefault(cond_key, []).append(t["replicate_index"])
        assert "seed" in t

    assert len(conditions) == 12  # 2 ID dims x 2 scope dims x 3 workload mixes = 12 conditions
    for cond_key, reps in conditions.items():
        assert sorted(reps) == [1, 2, 3], f"Condition {cond_key} does not have exactly rep1, rep2, rep3"

    # 6. Verify distinct trace contents and absence of duplicates
    trace_hashes = {}
    for entry in traces:
        trace_file = os.path.join("workloads", "traces", entry["trace_file"])
        assert os.path.exists(trace_file), f"Trace file {trace_file} listed in manifest but not found"
        with open(trace_file, "rb") as fp:
            import hashlib
            h = hashlib.sha256(fp.read()).hexdigest()
        assert h not in trace_hashes, f"Duplicate trace content detected between {entry['trace_file']} and {trace_hashes[h]}"
        trace_hashes[h] = entry["trace_file"]

    # 7. sample_lexical.trace remains outside the authoritative experimental matrix
    manifest_filenames = set(t["trace_file"] for t in traces)
    assert "sample_lexical.trace" not in manifest_filenames
    sample_path = os.path.join("workloads", "traces", "sample_lexical.trace")
    assert os.path.exists(sample_path), "sample_lexical.trace must exist as a functional unit-test fixture"
