# ColliScope: Metrics Infrastructure & Specification

**Document Version:** 1.0.0 (Phase 1)  
**Status:** Approved Specification  
**Related Components:** `src/common/metrics.hpp`, `benchmarks/`, `analysis/`

---

## 1. Core Measurement Philosophy

A critical pitfall in collision resolution research is treating algorithm-specific internal counter metrics as equivalent across different collision resolution paradigms.

> [!WARNING]
> **"Probe Count" is NOT Directly Comparable Across Algorithms!**
> - In **Separate Chaining**, a "probe" entails traversing a heap-allocated linked list or bucket vector (incurring potential pointer chasing and cache misses).
> - In **Cuckoo Hashing**, a probe involves evaluating two independent hash functions and inspecting two flat array slots (or bucketed slots). Evictions incur recursive displacement kicks.
> - In **Hopscotch Hashing**, probes check a bounded linear neighborhood using bitmasks, followed by neighborhood displacements when full.
> - In **SVC-Hash**, a probe inspects candidate cuckoo buckets and performs Euler-tour / scope-interval containment tests to verify active lexical visibility.
> 
> Therefore, ColliScope evaluates collision resolution mechanisms using **standardized external performance metrics** (latency distributions, throughput, memory footprint, load factor), while reporting **algorithm-specific internal metrics** in their proper respective contexts.

---

## 2. Common Metrics Schema (`TableMetrics`)

Every implementation of `ISymbolTable` exposes a unified `TableMetrics` struct:

| Metric Field | Type | Description |
|---|---|---|
| `algorithm_name` | `string` | Identifier: `chaining`, `cuckoo`, `hopscotch`, `svc_hash` |
| `num_elements` | `uint64_t` | Number of currently active stored symbols |
| `capacity` | `uint64_t` | Total available table slots / capacity |
| `load_factor` | `double` | Current ratio: $\frac{\text{num\_elements}}{\text{capacity}}$ |
| `insertion_time_ns` | `uint64_t` | Cumulative wall-clock CPU time spent in declarations (nanoseconds) |
| `lookup_time_ns` | `uint64_t` | Cumulative wall-clock CPU time spent in references (nanoseconds) |
| `scope_exit_time_ns`| `uint64_t` | Cumulative time spent exiting scopes (tombstoning/cleanup) |
| `total_operations` | `uint64_t` | Total operations executed ($N_{\text{insert}} + N_{\text{lookup}} + N_{\text{scope}}$) |
| `throughput_ops_sec`| `double` | Aggregated throughput ($\frac{\text{total\_operations}}{\text{total\_time\_sec}}$) |
| `memory_usage_bytes`| `uint64_t` | Measured or calculated memory footprint (bytes) |
| `collision_count` | `uint64_t` | Total primary collision events encountered upon initial insertion |
| `successful_lookups`| `uint64_t` | Count of lookup operations returning an active symbol |
| `failed_lookups` | `uint64_t` | Count of lookup operations resolving to "not found" (undeclared) |

---

## 3. Algorithm-Specific Metrics Extension Points

`TableMetrics` includes structured extension sub-structs and key-value attributes:

### 3.1 Separate Chaining
- `chain_length_max`: Maximum length of any single bucket chain.
- `chain_length_avg`: Mean bucket chain length across populated buckets.
- `comparisons_count`: Total key equality comparisons during lookups and inserts.
- `traversal_length_total`: Sum of all link hops performed during bucket traversals.

### 3.2 Plain Cuckoo Hashing
- `relocations_kicks`: Number of eviction displacements (cuckoo kicks) triggered.
- `rehashes_count`: Number of full table rehashes caused by displacement cycles.
- `max_displacement_depth`: Maximum kick chain length reached during an insertion.

### 3.3 Hopscotch Hashing
- `neighbourhood_movements`: Number of items moved backward to open space within the neighborhood.
- `comparisons_count`: Total key comparisons within the hopscotch window.
- `resize_events`: Number of table resizing operations triggered by neighborhood overflow.

### 3.4 SVC-Hash (Scope-Aware Cuckoo Hash)
- `candidate_locations_examined`: Number of candidate bucket slots evaluated.
- `scope_checks_count`: Number of scope ancestor / visibility checks performed during lookups.
- `scope_exit_cost_ns`: Time consumed specifically by scope exit operations and tombstone invalidations.
- `stash_usage_count`: Number of entries stored in the auxiliary overflow stash (if utilized).
- `relocations_count`: Cuckoo displacement count in the scope-aware table.
- `rebuild_count`: Total rehash / compaction invocations.

---

## 4. Serialization Format

Metrics are serialized into both machine-readable JSON and tabular CSV:
- **JSON**: Used for detailed single-run profiles, full environment metadata, and hierarchical inspection in the dashboard.
- **CSV**: Used for bulk statistical processing, aggregation across 30 repeated trials in Python, and confidence interval calculations.
