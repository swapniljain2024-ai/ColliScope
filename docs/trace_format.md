# ColliScope: Execution Trace Format Contract

**Document Version:** 1.1.0 (Phase 4 — Reconciled with Phase 2 Duplicate Declaration Contract)  
**Status:** Binding Specification & Contract  
**Related Components:** `workloads/traces/`, `src/common/trace_parser.hpp`, `benchmarks/`

---

## 1. Trace Philosophy & Fairness Requirement

Every collision-resolution algorithm tested in an experimental trial must receive the **exact same stream of commands** without modification. The trace system serves as the immutable contract ensuring repeatable, deterministic execution across all implementations.

---

## 2. Formal Grammar (EBNF)

Traces are line-oriented UTF-8 text files (with extension `.trace`). Empty lines and lines starting with `#` are ignored as comments.

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

---

## 3. Operation Semantics

### `ENTER_SCOPE <scope_id> [parent_scope_id]`
- Signals entry into a new lexical scope identified by `scope_id`.
- If `parent_scope_id` is supplied, sets the parent scope in the lexical hierarchy. If omitted, the parent is the currently open scope on the active scope stack.
- Global scope is defined with `scope_id = 0` (opened at the beginning of execution).

### `EXIT_SCOPE <scope_id>`
- Signals the termination and exit of lexical scope `scope_id`.
- All symbols declared in `scope_id` are no longer visible to subsequent lookup operations.
- The active scope reverts to the parent of `scope_id`.

### `DECLARE <identifier> [type_id] [scope_id]`
- Declares the symbol `identifier` in the specified `scope_id` (or the currently active scope if omitted).
- `type_id` represents semantic compiler information (e.g., integer, float, pointer, struct tag); default is `1`.
- **Duplicate Declarations:** Per the Phase 2 specification (`docs/svc_hash_design.md` Section 4), a `(key, scope_id)` pair may be declared at most once. Duplicate declarations of the same identifier within the exact same scope are prohibited by contract in valid compiler symbol-table traces (reflecting compiler duplicate-definition errors) and are rejected by table insertion. Shadowing across distinct scopes remains fully supported and resolved by ancestor order.

### `REFERENCE <identifier> [scope_id]`
- Performs a symbol table lookup for `identifier` initiating from `scope_id` (or currently active scope).
- Resolves to the declaration with the highest lexical depth in the ancestor chain of `scope_id` (shadowing).
- **Ambiguous Case - Undeclared Identifier:** If `identifier` does not exist in the active scope or any of its ancestors, the lookup returns "not found" (represented as `std::nullopt` in C++ or `None` in Python). This increments `failed_lookups` in metrics.
- **Ambiguous Case - Closed Scope Lookup:** An identifier declared in a scope that has been exited via `EXIT_SCOPE` must not be resolved; the lookup continues searching outer ancestor scopes or reports "not found".

---

## 4. Illustrative Example

```trace
# ColliScope Example Trace
ENTER_SCOPE 0
DECLARE global_var 1 0
ENTER_SCOPE 1 0
DECLARE count 1 1
REFERENCE count 1
ENTER_SCOPE 2 1
DECLARE count 2 2
REFERENCE count 2
EXIT_SCOPE 2
REFERENCE count 1
EXIT_SCOPE 1
REFERENCE count 0
EXIT_SCOPE 0
```

**Expected Oracle Behavior:**
1. `REFERENCE count 1` inside scope 1 resolves to `count` with `type_id = 1`.
2. `REFERENCE count 2` inside scope 2 resolves to the shadowed `count` with `type_id = 2`.
3. After `EXIT_SCOPE 2`, `REFERENCE count 1` resolves back to outer `count` (`type_id = 1`).
4. After `EXIT_SCOPE 1`, `REFERENCE count 0` fails (returns not found) because `count` was only declared in inner scopes.

---

## 5. Revision History
- **v1.0.0 (Phase 1):** Initial execution trace format grammar, semantics, and reference examples.
- **v1.1.0 (Phase 4):** Reconciled duplicate declaration contract with approved Phase 2 design (`docs/svc_hash_design.md` Section 4). Explicitly prohibited same-scope redeclarations in valid compiler symbol-table traces while maintaining multi-scope shadowing.
