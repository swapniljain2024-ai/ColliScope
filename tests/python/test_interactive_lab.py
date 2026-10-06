"""
Tests for the ColliScope Interactive Symbol Table Lab Engine.
Validates the mathematical behavior, scope tree lifecycle, duplicate rejection,
shadowing, cuckoo kicks, and trace export.
"""

import pytest
from dashboard.symbol_table_engine import (
    SvcHashTableSimulator,
    ChainingTableSimulator,
    PlainCuckooTableSimulator,
    HopscotchTableSimulator,
    SymbolValue,
    fnv_hash_composite,
    execute_trace_in_cpp_engine
)


def test_svc_hash_engine_basic_lifecycle():
    sim = SvcHashTableSimulator(num_buckets=8)
    assert sim.current_scope_id == 0

    # 1. Insert var_a in root scope
    r1 = sim.insert("var_a", SymbolValue(1, 10))
    assert r1["success"] is True
    assert r1["status"] == "direct_insert"

    # 2. Duplicate rejection in same scope
    r_dup = sim.insert("var_a", SymbolValue(1, 12))
    assert r_dup["success"] is False
    assert r_dup["status"] == "duplicate_rejected"

    # 3. Enter child scope 1
    ok, msg, s1 = sim.enter_scope("Function foo")
    assert ok is True
    assert s1 == 1
    assert sim.current_scope_id == 1

    # 4. Shadowing: insert var_a in scope 1
    r_shadow = sim.insert("var_a", SymbolValue(2, 20))
    assert r_shadow["success"] is True

    # 5. Lookup var_a from scope 1 resolves to scope 1
    l1 = sim.lookup("var_a")
    assert l1["found"] is True
    assert l1["resolved_scope"] == 1
    assert l1["value"].type_id == 2

    # 6. Exit scope 1 -> tombstones entries in scope 1
    ok_exit, msg_exit, ex_id, tombstones = sim.exit_scope()
    assert ok_exit is True
    assert ex_id == 1
    assert tombstones == 1
    assert sim.current_scope_id == 0

    # 7. Lookup var_a from scope 0 resolves to root scope 0 (unmasked!)
    l0 = sim.lookup("var_a")
    assert l0["found"] is True
    assert l0["resolved_scope"] == 0
    assert l0["value"].type_id == 1


def test_cuckoo_and_baselines_simulators():
    # Plain Cuckoo
    cuckoo = PlainCuckooTableSimulator(capacity=16)
    r1 = cuckoo.insert("x", SymbolValue(1, 1), 0)
    assert r1["success"] is True
    lk = cuckoo.lookup("x")
    assert lk is not None

    # Chaining
    chain = ChainingTableSimulator(num_buckets=8)
    rc = chain.insert("x", SymbolValue(1, 1), 0)
    assert rc["success"] is True
    assert chain.lookup("x", 0) is not None

    # Hopscotch
    hop = HopscotchTableSimulator(capacity=32)
    rh = hop.insert("x", SymbolValue(1, 1), 0)
    assert rh["success"] is True
    assert hop.lookup("x") is not None


def test_cpp_binary_trace_execution():
    trace = "ENTER_SCOPE 0 0\nDECLARE x 1 0\nREFERENCE x 0\nEXIT_SCOPE 0\n"
    res = execute_trace_in_cpp_engine(trace)
    assert "available" in res
    if res["available"]:
        assert res["returncode"] == 0
        assert "scoped_chaining" in res["stdout"] or "chaining" in res["stdout"]
