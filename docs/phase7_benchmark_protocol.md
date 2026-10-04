# ColliScope: Phase 7 Benchmark Protocol & Execution Specification

**Document Version:** 2.0.0 (Phase 7)  
**Status:** Approved Benchmark Specification  
**Related Components:** `benchmarks/colliscope_bench`, `benchmarks/run_benchmarks.py`, `benchmarks/audit_phase7_results.py`, `workloads/traces/manifest.json`

---

## 1. Executive Summary

Phase 7 executes the standardized empirical benchmarking campaign of the ColliScope compiler symbol-table collision-resolution study across the corrected 38-trace workload matrix. This document outlines the execution protocol, timing invariants, replicate structures, and data preservation standards.

---

## 2. Experimental Workload Matrix

The Phase 7 campaign evaluates exactly **38 authoritative workload traces** defined in `manifest.json`:

1. **Synthetic Factorial Matrix (36 Traces):**
   - **Identifier Distributions (2):** `random` vs `frequency-matched` (Zipf $s \approx 1.1$)
   - **Scope Modes (2):** `flat` (global scope 0, depth 2) vs `nested` (depth 7–9, active lexical block scoping)
   - **Operation Mixes (3):** `declaration-heavy` (~60/30/10), `mixed` (~40/50/10), `lookup-heavy` (~10/80/10)
   - **Deterministic Seed Replicates (3):** `rep1` (seed 42), `rep2` (seed 43), `rep3` (seed 44)
   - Total synthetic cells: $2 \times 2 \times 3 = 12$ conditions $\times$ 3 replicates = **36 traces**.

2. **Real-Source Project Case Study (2 Traces):**
   - **Source Code:** `cJSON` v1.7.18 (`workloads/sources/cJSON/cJSON.c`, commit `acc7623`)
   - **Representations (2):** Flattened translation unit (`trace_real-source_flat.trace`) vs AST-preserving lexical block scopes (`trace_real-source_nested.trace`).
   - Modeled via AST extraction (`real_source_extractor.py`), capturing in-unit declarations, lexical scopes, and authentic standard library unresolved external lookups (~25% miss rate).
   - **Scope:** Evaluated as an authentic real-world case study, not pooled as independent factorial cells.

3. **Excluded Test Fixtures:**
   - `sample_lexical.trace` is a Phase 4 functional test fixture and is strictly excluded from the experimental dataset.

---

## 3. Evaluated Collision-Resolution Algorithms

All 38 traces are evaluated across 4 collision-resolution algorithms:

1. **Separate Chaining (`chaining` / `scoped_chaining`):**
   - Dynamic linked lists per bucket slot with incremental load factor scaling.
2. **Plain Cuckoo Hashing (`cuckoo` / `scoped_cuckoo`):**
   - Two hash functions ($h_1, h_2$) with recursive kick-displacement eviction chains.
3. **Hopscotch Hashing (`hopscotch` / `scoped_hopscotch`):**
   - Linear probing with bounded neighborhood swapping ($H=32$ bitmask).
4. **SVC-Hash (`svc_hash`):**
   - Scope Virtualization Cuckoo Hash with native multi-scope intervals, epoch tagging, and stash fallback.

### Scoped Table Wrapper Architecture
For nested traces, baseline algorithms (`chaining`, `cuckoo`, `hopscotch`) execute inside `ScopedTableWrapper<T>`, maintaining a stack of scope tables where `enterScope` instantiates/activates child tables and `exitScope` deallocates them. `SVC-Hash` natively executes all scopes within its virtualized single-structure design.

---

## 4. Phase 7 Benchmark Execution Protocol

For every trace and algorithm combination:

| Protocol Parameter | Specification | Implementation & Rationale |
|---|---|---|
| **Warmup Trials** | **3 warmups** | Executed prior to timing data collection to prime CPU instruction cache, branch predictors, and OS virtual memory pages. Warmup results are strictly excluded from reported measured trial datasets. |
| **Measured Repetitions** | **10 repetitions** | 10 independent measured trials per trace $\times$ algorithm to calculate robust sample means, standard deviations, and 95% confidence intervals. |
| **State Isolation** | **Table Reset per Trial** | `table.reset()` is invoked before every trial run. A fresh table instance is allocated per trial to guarantee complete independence and zero residual state carryover. |
| **Paired Workload Execution** | **Identical Command Sequences** | All 4 algorithms receive the exact same parsed `TraceCommand` sequence for a given trace. |
| **Execution Ordering** | **Alternating / Randomized** | To eliminate systematic ordering bias (e.g. thermal throttling, CPU frequency scaling, cache warming favoring earlier algorithms), algorithm execution order is permuted across repetitions using a deterministic PRNG seed (`order_seed = 42`). The exact execution order ($1 \dots 4$) is recorded in every raw trial record. |
| **Scale of Execution** | **1,520 Measured + 456 Warmups** | $38\text{ traces} \times 4\text{ algorithms} \times 10\text{ repetitions} = \mathbf{1,520}\text{ measured trials}$.<br>$38 \times 4 \times 3 = \mathbf{456}\text{ warmup executions}$.<br>Total trial executions = **1,976**. |

---

## 5. Timing Methodology & Metric Semantics

1. **High-Precision Monotonic Timing:**
   - Measured exclusively via the benchmark engine using Windows `QueryPerformanceCounter` (QPC, frequency $\approx 10$ MHz, resolution $\approx 100$ ns).
   - Algorithm internal instrumentation timers are disabled during wall-clock benchmarking (`table.setTimingEnabled(false)`).

2. **Amortized Batch Latency per Operation:**
   - Due to sub-tick CPU execution durations of in-memory hash table operations ($< 100$ ns), consecutive operations are sampled in runs (up to 16 ops) and calibrated against total verified wall-clock time.
   - All latency statistics (min, mean, p50, p95, p99, max) are explicitly defined and reported as **amortized batch latency per operation**, not individually measured per-operation hardware latency.

3. **Load Factor Interpretation:**
   - **Load factor is strictly an observed output metric.** Traces do not possess nominal load factors (all obsolete `lf50/70/90` targets have been eliminated).
   - Peak load factor reflects the empirical capacity utilization achieved by each algorithm's respective resize and eviction thresholds.

4. **Primary vs Secondary Metrics:**
   - **Primary:** Throughput (operations / sec), Total Execution Time (ns), Insert Latency (p50 / mean ns), Lookup Latency (p50 / mean ns).
   - **Secondary:** Tail Latencies (p95, p99 ns), Peak Memory Footprint (bytes), Peak Load Factor, Lookup Miss Ratio.
   - **Diagnostics:** Algorithm-specific counters (Cuckoo kicks, Chaining chain lengths, Hopscotch displacements, SVC rebuilds/stash) remain technique-specific diagnostics and are never combined into an artificial universal score.

---

## 6. Statistical Experimental Units (Phase 8 Guidance)

To prevent pseudo-replication in subsequent statistical analysis:

1. **Workload Seed Replicates ($n=3$):**
   - In the synthetic $2 \times 2 \times 3$ factorial design, the **trace seed** (`rep1`, `rep2`, `rep3`) is the independent experimental unit ($n=3$ per condition cell).
2. **Benchmark Repetitions ($R=10$):**
   - The 10 timed repetitions of a single trace represent **repeated timing measurements** to estimate measurement variance, **not** 10 independent workload samples.
   - Analysis must aggregate the 10 repetitions per trace first before evaluating condition-level effects across the 3 seeds.
3. **Real-Source Project ($N=1$):**
   - cJSON flat and nested represent an authentic case study and scope ablation of a single real-world codebase ($N=1$). They must be analyzed descriptively and not pooled into the synthetic factorial ANOVA.
