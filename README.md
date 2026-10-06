# ColliScope: Workload-Aware Evaluation and Scope-Aware Cuckoo Hashing for Compiler Symbol Tables

[![C++17](https://img.shields.io/badge/standard-C%2B%2B17-blue.svg)](https://en.wikipedia.org/wiki/C%2B%2B17)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Academic Topic:** Performance Evaluation of Compiler Symbol Table Implementations — Collision Resolution  
**Repository:** [https://github.com/swapniljain2024-ai/ColliScope](https://github.com/swapniljain2024-ai/ColliScope)

---

## Overview

Compiler symbol tables encounter distinct access patterns characterized by non-uniform identifier frequencies, bursty declaration/reference ratios, and deep lexical scope hierarchies with shadowing and scope exits. Traditional collision resolution studies often rely on uniform random keys in flat namespaces, obscuring real-world compiler performance dynamics.

**ColliScope** addresses this gap through two connected contributions:
1. **Workload-Aware Experimental Framework:** A systematic evaluation methodology characterizing compiler-like workloads across identifier distributions (authentic open-source C/C++, Zipfian frequency-matched synthetic, and uniform random), lexical scoping dimensions (flat vs. nested), operation mixes (declaration-heavy, lookup-heavy, mixed), and observed emergent load factors.
2. **SVC-Hash (Scope-Versioned Cuckoo Hash):** A scope-aware extension of cuckoo hashing engineered specifically for compiler symbol-table operations, featuring bucketized storage, parent-chain scope traversal, and deferred tombstone compaction.

### Benchmark Set
- **Baselines:**
  1. Separate Chaining (`chaining` / `scoped_chaining`)
  2. Plain Cuckoo Hashing (`cuckoo` / `scoped_cuckoo`) (critical ablation baseline)
  3. Hopscotch Hashing (`hopscotch` / `scoped_hopscotch`)
- **Proposed:**
  4. SVC-Hash (`svc_hash`) (Scope-Versioned Cuckoo Hash)

*(Note: Linear Probing, Quadratic Probing, Double Hashing, and Robin Hood Hashing are explicitly excluded.)*

---

## Repository Structure

```
ColliScope/
|-- src/                 # Performance-critical C++ implementations
|   |-- common/          # Shared interfaces, configuration, metrics contracts
|   |-- chaining/        # Separate Chaining baseline
|   |-- cuckoo/          # Plain Cuckoo baseline
|   |-- hopscotch/       # Hopscotch baseline
|   `-- svc_hash/        # Scope-Versioned Cuckoo Hash (SVC-Hash)
|-- workloads/           # Workload extraction and trace generation
|   |-- traces/          # Deterministic machine-readable execution traces (38 authoritative)
|   |-- real_source/     # Real C/C++ corpora and provenance documentation (cJSON v1.7.18)
|   `-- generators/      # Random, frequency-matched, and matrix generators
|-- benchmarks/          # Trace-driven benchmark runner and experiment engine
|-- tests/               # Test suites
|   |-- cpp/             # C++ correctness and Catch2 unit tests (32 test cases, 6,449 assertions)
|   `-- python/          # Python pytest suite (28 tests)
|-- analysis/            # Statistical analysis (Wilcoxon signed-rank, Holm correction, bootstrap CIs)
|-- dashboard/           # Interactive Streamlit + Plotly research dashboard (10 pages)
|-- results/             # Authoritative benchmark results (Phase 7) and statistical outputs (Phase 8)
|-- docs/                # Architectural specs, audit reports, and methodology documentation
|-- CMakeLists.txt       # Root CMake build definition
|-- requirements.txt     # Python dependencies
`-- README.md            # Project documentation
```

---

## Build, Test, and Execution Instructions

### Prerequisites
- C++17 compatible compiler (e.g., MinGW-W64 GCC 8.1+ or Clang/MSVC)
- CMake 3.20+
- Python 3.10+

### 1. Python Environment Setup
Install the required Python tools and packages:
```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 2. C++ Build (MinGW / CMake)
Configure and compile the project using CMake:
```powershell
cmake -B build -G "MinGW Makefiles" -DCMAKE_CXX_COMPILER="g++"
cmake --build build
```

To run C++ unit tests (32 test cases, 6,449 assertions):
```powershell
# Run with CTest:
ctest --test-dir build --output-on-failure

# Or run the Catch2 binary directly:
.\build\tests\colliscope_tests.exe
```

### 3. Python Tests
Execute the Python test suite (28 tests across baselines, generators, traces, and dashboard):
```powershell
python -m pytest tests/python -v
```

### 4. Running the Benchmark Engine
To benchmark algorithms on a workload trace using the compiled benchmark executable:
```powershell
python benchmarks/run_benchmarks.py --trace workloads/traces/trace_real-source_nested.trace --repetitions 10 --warmup 3
```

### 5. Reproducing Statistical Analysis
To run the full Phase 8 non-parametric statistical hypothesis testing pipeline:
```powershell
python analysis/phase8_statistical_analysis.py
```
*(Produces all tables, Wilcoxon test results, Holm corrections, effect sizes, and publication figures in `results/phase8/`)*.

### 6. Launching the Interactive Research Dashboard
To explore the authoritative benchmark data, statistical tests, and case studies:
```powershell
python -m streamlit run dashboard/app.py
# Or if streamlit is on your PATH:
streamlit run dashboard/app.py
```

---

## Research Invariants & Key Findings

1. **Experimental Workload Dataset:**
   - **38 Authoritative Traces:** 36 synthetic factorial traces (2 identifier distributions $\times$ 2 scope modes $\times$ 3 operation mixes $\times$ 3 deterministic seed replicates) + 2 authentic real-source traces (`cJSON` v1.7.18 flat and nested).
   - **Unit of Inference:** $N=36$ independent workload units (replicates). The 10 timed repetitions per trace are aggregated via median to estimate measurement variance and are **not** treated as independent observations.
   - **Observed Load Factor:** Load factor is strictly an emergent output metric, not an experimental input.

2. **Core Research Findings:**
   - **Where Baselines Excel:** Under flat, lookup-heavy workloads with Zipfian frequency skew, Separate Chaining (median 445,959 ops/sec) and Hopscotch (median 554,809 ops/sec) significantly outperform SVC-Hash (median 221,243 ops/sec) due to low per-probe overhead and cache locality.
   - **Where SVC-Hash Excels:** Under hierarchical nested scopes, SVC-Hash significantly outperforms Scoped Cuckoo ($p < 0.001$, $r = 1.0$), Scoped Chaining ($p = 0.0269$, $r = 0.608$), and Scoped Hopscotch ($p = 0.0383$, $r = 0.569$) because its virtualized scope-interval mechanism eliminates the allocation and deallocation overheads of recursive table wrappers.
   - **Real-Source Case Study:** On nested `cJSON` v1.7.18, SVC-Hash achieves 734,949 ops/sec (a 1.76$\times$ speedup over Scoped Chaining and 3.71$\times$ over Scoped Cuckoo) while maintaining a compact memory footprint. On flat `cJSON`, Chaining and Hopscotch achieve ~5.6$\times$ higher throughput. Evaluated strictly as a descriptive case study of one real project under two scope representations.
