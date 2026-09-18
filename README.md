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
1. **Workload-Aware Experimental Framework:** A systematic evaluation methodology that characterizes compiler-like workloads across identifier distributions (real open-source C/C++, Zipf-like synthetic, and uniform random), lexical scoping dimensions (flat vs. nested), operation mixes (declaration-heavy, lookup-heavy, mixed), and configurable load factors.
2. **SVC-Hash (Scope-Aware Variant Cuckoo Hash):** A novel, scope-aware extension of cuckoo hashing engineered specifically for compiler symbol-table operations, featuring bucketized storage, lexical hierarchy tracking, and efficient shadowing resolution.

### Benchmark Set
- **Baselines:**
  1. Separate Chaining
  2. Plain Cuckoo Hashing (critical ablation baseline)
  3. Hopscotch Hashing
- **Proposed:**
  4. SVC-Hash (Scope-aware Variant Cuckoo Hash)

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
|   `-- svc_hash/        # Scope-Aware Cuckoo Hash (SVC-Hash)
|-- workloads/           # Workload extraction and trace generation
|   |-- traces/          # Deterministic machine-readable execution traces
|   |-- real_source/     # Real C/C++ corpora and provenance documentation
|   `-- generators/      # Random, frequency-matched, and matrix generators
|-- benchmarks/          # Trace-driven benchmark runner and experiment engine
|-- tests/               # Test suites
|   |-- cpp/             # C++ correctness and unit tests
|   `-- python/          # Python pytest suite
|-- analysis/            # Statistical analysis (mean, stdev, CI, p95/p99, effect sizes)
|-- dashboard/           # Interactive Streamlit + Plotly research dashboard
|-- results/             # Raw experiment logs, CSV/JSON runs, and report assets
|-- docs/                # Architectural specs, audit reports, and design decisions
|-- CMakeLists.txt       # Root CMake build definition
|-- requirements.txt     # Python dependencies
`-- README.md            # Project documentation
```

---

## Build and Test Instructions

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
# Using MinGW Makefiles (adjust compiler path if needed)
cmake -B build -G "MinGW Makefiles" -DCMAKE_CXX_COMPILER="g++"
cmake --build build
```

To run C++ unit tests:
```powershell
ctest --test-dir build --output-on-failure
# Or directly run the test binary:
./build/tests/test_scaffolding.exe
```

### 3. Python Tests
Execute the Python test suite using pytest:
```powershell
python -m pytest tests/python -v
```

---

## Research Integrity & Provenance
ColliScope strictly enforces research integrity:
- Every workload labeled **REAL** originates directly from documented open-source C/C++ repositories with recorded repository URLs, commit hashes, licenses, and file lists.
- Synthetic workloads are explicitly labeled as **SYNTHETIC** or **FREQUENCY-MATCHED SYNTHETIC**.
- Performance metrics are gathered across repeated trials with confidence intervals and verified against an oracle implementation before evaluation.
