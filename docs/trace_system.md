# ColliScope: Trace System & Deterministic Replay Engine

**Document Version:** 1.0.0 (Phase 4)  
**Status:** Implemented & Verified Specification  
**Components:** `src/common/trace_parser.hpp`, `src/common/trace_executor.hpp`, `src/common/trace_oracle.hpp`, `workloads/traces/`

---

## 1. Overview & Fairness Contract

The ColliScope Trace System provides deterministic execution and replay of compiler-like operation streams against all symbol table implementations.

To satisfy the **Critical Fairness Requirement**:
- Every candidate symbol table (`ChainingHashTable`, `CuckooHashTable`, `HopscotchHashTable`, and `SvcHashTable`) receives the **exact same ordered sequence of logical trace operations**.
- The trace executor does not mutate or alter trace commands between algorithms.
- Logical lookup outcomes are cross-validated against an independent, ground-truth reference model (`TraceOracle`).

---

## 2. Trace Format & Grammar

Traces are line-oriented UTF-8 text files (`.trace`). Blank lines and lines prefixed with `#` (as well as inline comments) are ignored.

### Formal Grammar (EBNF)
```ebnf
TraceFile       ::= { Line }
Line            ::= [ Comment | Operation ] ( "\n" | "\r\n" )
Comment         ::= "#" { AnyCharacter }
Operation       ::= EnterScopeOp | ExitScopeOp | DeclareOp | ReferenceOp

EnterScopeOp    ::= "ENTER_SCOPE" WS ScopeId [ WS ParentScopeId ]
ExitScopeOp     ::= "EXIT_SCOPE" WS ScopeId
DeclareOp       ::= "DECLARE" WS Identifier [ WS TypeId [ WS ScopeId ] ]
ReferenceOp     ::= "REFERENCE" WS Identifier [ WS ScopeId ]

Identifier      ::= ( Letter | "_" ) { Letter | Digit | "_" }
ScopeId         ::= NonNegativeInteger
ParentScopeId   ::= NonNegativeInteger
TypeId          ::= Integer
WS              ::= { " " | "\t" }+
```

### Operation Semantics & Default Scoping
1. **`ENTER_SCOPE <scope_id> [parent_scope_id]`**:
   - Opens a lexical scope.
   - If `parent_scope_id` is omitted, the parent defaults to the currently active scope at the top of the stack.
   - Scope `0` represents the root global scope.
2. **`EXIT_SCOPE <scope_id>`**:
   - Closes the active scope.
   - Symbols declared in this scope become inaccessible to subsequent lookups.
3. **`DECLARE <identifier> [type_id] [scope_id]`**:
   - Inserts `identifier` into `scope_id` (or active scope if omitted).
   - `type_id` defaults to `1` if omitted.
4. **`REFERENCE <identifier> [scope_id]`**:
   - Performs a lookup for `identifier` starting from `scope_id` (or active scope).
   - Resolves to the nearest active declaration in the lexical ancestor chain (shadowing).
   - Returns not found (`std::nullopt`) if undeclared or in an exited scope.

---

## 3. Core Components

### Trace Parser (`colliscope::TraceParser`)
- **C++:** Reads `.trace` streams into `std::vector<TraceCommand>`.
- **Validation:** Rejects malformed input deterministically with line-numbered exceptions for syntax errors, invalid identifiers, or missing tokens.
- **Python:** [`workloads/trace_validator.py`](file:///c:/Users/Hp/Desktop/ColliScope/workloads/trace_validator.py) provides equivalent schema validation for authoring and tooling.

### Trace Executor (`colliscope::TraceExecutor`)
- Replays a parsed trace vector against any `ISymbolTable&`.
- Maintains active scope stack hierarchy during execution.
- Returns `ExecutionResult` containing:
  - Command counts (`declare_count`, `reference_count`, `enter_scope_count`, `exit_scope_count`).
  - Reference outcomes (`reference_results`).
  - Final metrics (`final_metrics`).

### Independent Correctness Oracle (`colliscope::TraceOracle`)
- Implements `ISymbolTable` without utilizing any hash table under test.
- Implements explicit lexical scope trees:
  - Scope nodes track `scope_id`, `parent_id`, `active` status, and an isolated symbol map.
  - Scope resolution walks the active scope's parent chain toward the root and resolves the first active declaration found, thereby implementing lexical shadowing.
  - Enforces scope-transition invariants: parent must be active, scope IDs must not duplicate active scopes, and exits must match active stack discipline.

---

## 4. Deterministic Replay Definition

- **Logical Determinism:** Identical traces produce identical logical operation and reference results across repeated runs. Runtime-dependent timings and OS metrics are not required to be identical.
- **Flat Trace Agreement:** Flat traces (`scope_id = 0`) execute identically across `ChainingHashTable`, `CuckooHashTable`, `HopscotchHashTable`, `SvcHashTable`, and `TraceOracle`.
- **Scoped Trace Agreement:** Nested scoped traces execute identically across `SvcHashTable` and `TraceOracle`.
