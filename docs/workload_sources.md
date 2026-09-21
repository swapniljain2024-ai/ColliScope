# ColliScope Real-Source Corpus Provenance

**Document Version:** 1.2.0 (Phase 5 — AST Extraction & External Symbol Isolation Update)  
**Status:** Permanent Research Provenance Record  
**Related Components:** `workloads/real_source/`, `workloads/generators/real_source_extractor.py`, `workloads/traces/`

---

## 1. Research Integrity & Workload Classification Policy

ColliScope strictly enforces research data integrity and explicit workload categorization:
- **REAL WORKLOAD:** Real open-source C software (`cJSON`) parsed into an Abstract Syntax Tree (AST) using `pycparser`, with AST constructs (`c_ast.Decl`, `c_ast.FuncDef`, `c_ast.Compound`, `c_ast.ID`) mapped to compiler symbol-table operations (`ENTER_SCOPE`, `EXIT_SCOPE`, `DECLARE`, `REFERENCE`). *Note: AST-derived declarations, references, and scopes provide structural reliability over lexical heuristics, but the final trace is a modeled mapping to compiler symbol-table operations representing software input compiled by a frontend, not compiler internal source code.*
- **FREQUENCY-MATCHED SYNTHETIC WORKLOAD:** Synthetic workloads whose identifier frequency distribution is fit to the empirical rank-frequency distribution (Zipfian power law, $s = 1.244$) observed in the real-source AST extraction, using newly synthesized, non-verbatim identifiers.
- **RANDOM SYNTHETIC WORKLOAD:** Controlled synthetic workloads with uniformly generated random alphanumeric identifiers and parameterized operation mixes.

---

## 2. Real-Source Corpus Inventory

### 2.1. cJSON (Ultralightweight ANSI C JSON Parser)

- **Upstream Repository URL:** [https://github.com/DaveGamble/cJSON.git](https://github.com/DaveGamble/cJSON.git)
- **Release Tag:** `v1.7.18`
- **Git Commit Hash:** `acc76239bee01d8e9c858ae2cab296704e52d916`
- **License:** MIT License (retained verbatim in `workloads/real_source/cJSON/LICENSE`)
- **Source Files Extracted:**
  - `workloads/real_source/cJSON/cJSON.c` (78,800 bytes)
  - `workloads/real_source/cJSON/cJSON.h` (16,193 bytes)

#### Extraction Architecture
- **Extractor Implementation:** `workloads/generators/real_source_extractor.py` (`RealSourceExtractor`, `SymbolTableASTVisitor`)
- **Parser Engine:** `pycparser` C99 Abstract Syntax Tree Parser
- **Scope Discipline:** `c_ast.FuncDef` and `c_ast.Compound` AST blocks emit `ENTER_SCOPE` and `EXIT_SCOPE`.
- **Declaration Detection:** `c_ast.Decl` AST nodes (function definitions, function parameters, local/global variable declarations) emit `DECLARE <name> <type_id> <scope_id>`.
- **Reference Detection:** `c_ast.ID` expressions in operand, assignment, and return contexts emit `REFERENCE <name> <scope_id>`.
- **Structural Reliability:** Struct member references (`c_ast.StructRef`) visit the base object without conflating member fields as scope symbols; type casts (`c_ast.Cast`) visit expression operands without generating false-positive declarations; initializer lists (`c_ast.InitList`) do not create phantom scopes.
- **Contract Enforcement:** Strictly enforces at most one declaration per `(identifier, scope_id)` pair.
- **External Symbol Isolation:** External library functions and macros are preserved as `REFERENCE` operations without synthesizing artificial in-unit `DECLARE` operations, accurately isolating in-unit declarations from external lookups.

#### Extraction Statistics (`cJSON.c` AST Traversal)
- **Total Top-Level AST External Nodes:** 139
- **In-Unit Declarations Extracted:** 471 (authentic C99 declarations in translation unit)
- **Total References Extracted:** 2,307
  - **Resolved In-Unit References:** 1,698 (73.6%)
  - **Unresolved External References:** 609 (26.4%)
- **External Symbols Identified:** 58 distinct symbols (standard library functions, external macros)
- **Unique Identifiers in AST:** 281 total (223 in-unit declared + 58 external)
- **Total Lexical Scopes Created:** 468
- **Maximum Scope Nesting Depth:** 6
- **In-Unit Declaration / Reference Ratio:** ~1 : 4.90

#### Empirical Frequency Fit
- **Empirical Rank-Frequency Model:** Power-law / Zipfian distribution ($f(k) \propto k^{-s}$)
- **Fitted Zipf Exponent ($s$):** $1.244$ (ordinary least squares on $\log(\text{rank})$ vs $\log(\text{count})$, $R^2 > 0.94$)
- **Usage:** Calibrates the `FrequencyMatchedTraceGenerator` to produce synthetic traces with matching skew without reusing real identifier names verbatim.

---

## 3. Extraction Methodology & Limitations

1. **Preprocessor Resolution:** Preprocessor directives (`#include`, `#define`, `#ifdef`) are cleaned and standardized. Macro loops (`cJSON_ArrayForEach`) are expanded to canonical C `for` loops before AST construction.
2. **Standard Library Preamble:** Standard types (`size_t`, `FILE`, `uintptr_t`) are defined via an explicit C99 typedef preamble.
3. **External/Unresolved Symbol Isolation:** Symbols referenced in the translation unit without a local declaration (e.g. standard library functions `malloc`, `free`, `memcpy`, standard macros `NULL`, `false`, `true`) are isolated and preserved as unresolved `REFERENCE` operations rather than artificially fabricated `DECLARE` operations. This avoids distorting in-unit declaration statistics while accurately representing the negative lookups encountered by compiler frontends when querying external or unresolved symbols.
4. **Lexical Shadowing:** Variables declared in nested blocks with the same name as outer variables correctly resolve to the inner declaration during active block execution.

