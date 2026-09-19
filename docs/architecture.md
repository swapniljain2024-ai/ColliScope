# ColliScope: System Architecture & Design Contracts

**Document Version:** 1.0.0 (Phase 1)  
**Status:** Approved Architectural Contract  
**Related Components:** `src/common/`, `src/chaining/`, `src/cuckoo/`, `src/hopscotch/`, `src/svc_hash/`, `benchmarks/`, `workloads/`

---

## 1. System Overview and Layering

ColliScope is partitioned into distinct, decoupled subsystems to maintain scientific rigor, prevent cross-contamination of concerns, and ensure high experimental throughput:

```
+-------------------------------------------------------------+
|               Streamlit Research Dashboard (Phase 9)        |
+-------------------------------------------------------------+
                              | reads
                              v
+-------------------------------------------------------------+
|          Statistical Analysis Pipeline (Phase 8)            |
+-------------------------------------------------------------+
                              | processes
                              v
+-------------------------------------------------------------+
|          Benchmark Output Results (results/*.json, *.csv)   |
+-------------------------------------------------------------+
                              ^ produces
                              |
+-------------------------------------------------------------+
|          Benchmark Engine (Phase 6) & Replayer (Phase 4)    |
+-------------------------------------------------------------+
        | drives traces                      | invokes
        v                                    v
+------------------------+        +---------------------------+
| Workload Traces (.trace)|       | ISymbolTable Implementations|
|  (Phases 4, 5)          |       | - Separate Chaining       |
+------------------------+        | - Plain Cuckoo Hashing    |
                                  | - Hopscotch Hashing       |
                                  | - SVC-Hash                |
                                  +---------------------------+
```

---

## 2. Common Symbol Table Interface (`ISymbolTable`)

All collision-resolution data structures implement the pure virtual interface defined in `src/common/symbol_table.hpp`:

```cpp
namespace colliscope {

struct SymbolValue {
    int64_t type_id{0};
    uint32_t line_declared{0};
    std::string metadata{};
    
    bool operator==(const SymbolValue& other) const;
};

class ISymbolTable {
public:
    virtual ~ISymbolTable() = default;

    // Declarations & Lookups
    virtual bool insert(const std::string& key, const SymbolValue& value, uint32_t scope_id) = 0;
    virtual std::optional<SymbolValue> lookup(const std::string& key, uint32_t scope_id) = 0;

    // Scope Lifecycle Management
    virtual void enterScope(uint32_t scope_id, uint32_t parent_scope_id) = 0;
    virtual void exitScope(uint32_t scope_id) = 0;

    // State Reset
    virtual void reset() = 0;

    // Instrumentation & Diagnostics
    virtual TableMetrics getMetrics() const = 0;
    virtual std::string getAlgorithmName() const = 0;
};

} // namespace colliscope
```

---

## 3. Scope Abstraction & Baseline Adaptation Policy

### The Challenge
Symbol tables in actual compilers operate within lexical scopes where an identifier lookup must find the nearest active declaration in the scope ancestor chain.
- **SVC-Hash** natively embodies scope awareness: its internal bucketized cuckoo layout and scope metadata resolve lexical queries and scope exits directly within the collision-resolution scheme.
- **Baselines (Separate Chaining, Plain Cuckoo, Hopscotch)** are classic, flat collision-resolution tables designed for flat key-value pairs without inherent notion of scope hierarchies.

### Explicit Design Decision: Avoid "Forced Abstraction"
To ensure fair and interpretable evaluation without contaminating baseline performance or building artificial hacks:

1. **Dual Evaluation Modes**:
   - **Flat Benchmark Workloads (Scope Dimension = Flat)**:
     All operations occur in global scope (`scope_id = 0`). Baselines execute pure key-value operations. Calls to `enterScope` and `exitScope` are implemented as zero-cost inline no-ops in baseline implementations.
   - **Lexical Scoped Workloads (Scope Dimension = Nested)**:
     To evaluate how compilers traditionally use flat hash tables for scoped languages, baselines are paired with standard compiler scoping strategies:
     - **Strategy A (Scoped-Wrapper Stack):** A standard compiler pattern using a linked or stacked hierarchy of hash tables (one table per scope level), traversing upward during lookup.
     - **Strategy B (Compound-Key Lexical Prefix):** Identifiers are scoped or mangled with lexical indices.
   In Phase 3 and Phase 7, baseline implementations remain pristine, clean, and non-scope-aware in their core data structure. The scoped evaluation harness uses the standard, documented scoped wrapper to compare against SVC-Hash's monolithic scope-aware cuckoo table.

2. **No Scope Contamination in Baselines**:
   We **never** retroactively inject cuckoo-specific or SVC-specific scope-tombstoning logic into baseline chaining or hopscotch algorithms. Baselines represent their true, canonical computer science definitions.

3. **Optional Algorithm Exclusion Decision (Coalesced Hashing)**:
   Per Step 5 of the Master Agent Execution Manual, optional Coalesced Hashing is skipped to focus experimental resources strictly on the three canonical primary baseline families (Separate Chaining, Plain Cuckoo Hashing, Hopscotch Hashing) and prevent schedule/implementation risk. Linear Probing, Quadratic Probing, Double Hashing, and Robin Hood Hashing remain explicitly excluded.


---

## 4. Configuration Contract

System execution parameters are governed by a uniform, validated configuration model:
- **`BenchmarkConfig`**:
  - `identifier_dimension`: Enum (`Random`, `RealSource`, `FrequencyMatched`)
  - `scope_dimension`: Enum (`Flat`, `Nested`)
  - `workload_type`: Enum (`DeclarationHeavy`, `LookupHeavy`, `Mixed`)
  - `load_factor`: Double ($0.0 < \text{load\_factor} \le 1.0$)
  - `operation_mix`: Map specifying relative operation weights (`insert_ratio`, `lookup_ratio`, `scope_ratio`)
  - `algorithms`: Array of strings (`chaining`, `cuckoo`, `hopscotch`, `svc_hash`)
  - `repetitions`: Positive integer (default 30 for statistically rigorous sweeps)

This schema is implemented in `src/common/config.hpp` and mirrored in Python (`workloads/config_schema.py`) to guarantee identical configuration parsing across all tooling.
