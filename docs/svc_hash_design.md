# SVC-Hash Design Decision Log

**Document Version:** 2.2.0 (Phase 2 — Design Correction)  
**Status:** Design Contract — Write Before Coding  
**Related Components:** `src/svc_hash/`, `src/common/symbol_table.hpp`, `docs/architecture.md`  
**Revision History:**
- v1.0.0: Initial design. Identified critical issues with key-only hashing, Euler-tour
  sentinel correctness, stale insertion records, stash scope ownership, ambiguous hash
  functions, and unsupported performance claims.
- v2.0.0: Redesign introducing composite-key hashing, formalizing hash functions, and
  simplifying insertion records.
- v2.1.0: Corrected stash lookup behavior to probe stash per ancestor scope (enforcing
  shadowing correctness where inner scope stash entries shadow outer scope bucket entries).
  Removed Euler interval metadata (`euler_in`, `euler_out`, `euler_counter`, `UINT32_MAX` sentinel,
  and interval tests) in favor of explicit parent-chain (`parent_id`) traversal as the
  intentional scope-resolution mechanism. Defined strict duplicate declaration semantics
  (at most one declaration per `(key, scope_id)` pair). Corrected hash stream language to
  technically conservative wording. Updated worst-case lookup complexity to $O(d \times (2B + S)) = 16d$.
- v2.2.0: Formalized the explicit Scope Entry/Exit Contract requiring strict proper nesting
  (`enterScope` valid only under current active parent; `exitScope` valid only on current innermost
  active scope; invalid transitions rejected). Refined composite-key hashing language to conservative
  wording ("Different (key, scope_id) pairs are hashed as distinct composite keys, so declarations of the same identifier in different scopes are not forced to share the same candidate bucket pair") avoiding any implication of statistical independence. Preserved all v2.1 architecture.

---

## 0. Phase 1 Interface Compatibility Assessment

**Result: No changes to the common interface are required.**

The `ISymbolTable` interface from Phase 1 provides:
- `insert(key, value, scope_id)` → SVC-Hash declaration into composite-key-hashed bucket/stash
- `lookup(key, scope_id)` → scope-chain walk with per-ancestor bucket & stash probing
- `enterScope(scope_id, parent_scope_id)` → scope registration in scope registry
- `exitScope(scope_id)` → scope inactivation & tombstoning via per-scope log

All SVC-Hash internals (composite-key hashing, parent-chain scope traversal, scope registry, per-scope
logs, stash) are implementation details hidden behind this interface.

---

## 1. The Repeated-Shadowing Problem and Composite-Key Hashing

### The Problem (v1.0.0 Flaw)

In the original design, candidate buckets were computed from the identifier string alone:
`h1(key) % num_buckets` and `h2(key) % num_buckets`. This means that **all declarations
of the same identifier across all scopes** (e.g., `count` declared in scopes 0, 1, 2, 3,
4, 5, 6, 7, 8...) map to the **same two cuckoo buckets** — at most 8 slots. Rehashing
does not resolve this because identical keys continue to produce the same two candidate
locations regardless of table size.

With even moderate shadowing depth (9+ scopes declaring the same identifier), the table
overflows in a way that no amount of rehashing can fix.

### Alternatives Considered

| Alternative | Description | Verdict |
|---|---|---|
| **A. Key-only hashing (v1.0.0)** | `h(key)` → 2 buckets. All scopes share slots. | **Rejected.** Fundamentally capacity-limited at `2 × BUCKET_SIZE + STASH_SIZE` declarations per identifier. Rehash cannot fix same-key collisions. |
| **B. Composite-key hashing** | `h(key, scope_id)` → 2 buckets. Different `(key, scope_id)` pairs are hashed as distinct composite keys. Lookup walks ancestor chain. | **Selected.** No shadowing depth limit. Clean cuckoo semantics preserved. Lookup cost is O(depth) per-ancestor probes, which is exactly the cost-of-scope-awareness the ablation should measure. |
| **C. Per-scope sub-tables** | One cuckoo table per scope. Lookup walks scope chain checking each sub-table. | **Rejected.** Memory-inefficient, not a monolithic scope-aware table, would make the SVC-Hash vs Plain Cuckoo ablation less meaningful. |
| **D. Bucket chain extension** | Allow buckets to chain when same-key entries overflow. | **Rejected.** Breaks the fundamental cuckoo property of bounded probe sequences. |

### Selected Design: Composite-Key Hashing

**Candidate bucket locations are computed from `(key, scope_id)` jointly**, not from
`key` alone. Different `(key, scope_id)` pairs are hashed as distinct composite keys, so declarations of the same identifier in different scopes are not forced to share the same candidate bucket pair.

```
bucket_1 = hash1(key, scope_id) % num_buckets
bucket_2 = hash2(key, scope_id) % num_buckets
```

#### Implications for the Ablation Study

This design makes the Plain Cuckoo vs. SVC-Hash ablation cleanly interpretable:

| Property | Plain Cuckoo (Phase 3) | SVC-Hash |
|---|---|---|
| Hash input | `key` only | `(key, scope_id)` |
| Lookup cost | O(1): probe 2 buckets | O(d × (2B + S)): probe 2 buckets + stash per ancestor level |
| Scope awareness | None (flat key-value) | Native (ancestor-chain resolution, shadowing) |
| Scope exit cost | None | O(m): tombstone m declarations via scope log |
| Memory overhead | Base table only | Base table + scope registry + per-scope logs + stash |

The ablation directly measures what scope-awareness adds to a cuckoo-based design: the
per-lookup cost of ancestor probing, the per-scope-exit cost of tombstoning, and the
memory overhead of scope metadata.

---

## 2. Bucket Size and Layout (Flat Bucketized Storage)

### Decision
**Bucket size: 4 slots per bucket.** The table is a flat, contiguous array of `Bucket`
structs, each containing 4 `BucketEntry` slots.

### Reasoning
- Matches the prior design sketch in PROJECT CONTEXT (bucket size 4).
- With 2 hash functions and 4 slots per bucket, each `(key, scope_id)` pair has 8
  candidate slots before eviction is required.
- The achievable maximum load factor for bucketized cuckoo hashing with b=4 is an
  empirical question that will be evaluated experimentally in Phase 7. No a priori
  performance claims are made.

### Layout
```cpp
struct BucketEntry {
    std::string key{""};
    SymbolValue value{};
    uint32_t scope_id{0};
    bool occupied{false};
    bool tombstoned{false};
};

struct Bucket {
    static constexpr size_t BUCKET_SIZE = 4;
    BucketEntry entries[BUCKET_SIZE];
};
```

### Deviation from Prior Sketch
**None.** Bucket size 4 with flat bucketized storage matches the prior sketch.

---

## 3. Hash Functions — Deterministic Specification

### Decision
**Two FNV-1a 64-bit hash functions with different offset bases, both incorporating the
identifier string and the scope_id as input.**

### Exact Specification

```cpp
static uint64_t computeHash(const std::string& key, uint32_t scope_id,
                             uint64_t offset_basis) {
    constexpr uint64_t FNV_PRIME = 1099511628211ULL;
    uint64_t hash = offset_basis;

    // Hash the key bytes
    for (unsigned char c : key) {
        hash ^= static_cast<uint64_t>(c);
        hash *= FNV_PRIME;
    }

    // Mix in scope_id as 4 individual bytes (little-endian order)
    for (int i = 0; i < 4; i++) {
        hash ^= static_cast<uint64_t>((scope_id >> (i * 8)) & 0xFF);
        hash *= FNV_PRIME;
    }

    return hash;
}

// Hash function 1: standard FNV-1a 64-bit offset basis
static constexpr uint64_t HASH_SEED_1 = 14695981039346656037ULL;

// Hash function 2: distinct fixed FNV-1a offset basis
static constexpr uint64_t HASH_SEED_2 = 0x6c62272e07bb0142ULL;

size_t bucket1 = computeHash(key, scope_id, HASH_SEED_1) % num_buckets_;
size_t bucket2 = computeHash(key, scope_id, HASH_SEED_2) % num_buckets_;
```

### Hash Stream Properties

- FNV-1a is a well-studied, non-cryptographic hash with good distribution properties.
- Two deterministic candidate hash streams are generated using distinct fixed FNV-1a 64-bit offset bases.
- The same FNV prime is used in both (this is standard; the prime controls avalanche
  behavior, while the basis controls the starting state).
- Both functions are fully deterministic, reproducible, and trivially implementable
  without external dependencies. No claims of statistical independence are made.

### Bucket Index Collision Handling

If `bucket1 == bucket2` after the modulo operation:
```cpp
if (bucket2 == bucket1) {
    bucket2 = (bucket1 + 1) % num_buckets_;
}
```
This guarantees two distinct candidate buckets per `(key, scope_id)` pair.

### Hash Seeds Are Fixed Constants

Hash seeds do **not** change at rehash. Rehash only changes `num_buckets_`. Since bucket
indices are `hash % num_buckets_`, doubling `num_buckets_` redistributes entries. Using
fixed seeds ensures deterministic, reproducible behavior across rebuild events.

### Deviation from Prior Sketch
**Clarification, not deviation.** The prior sketch says "two hash functions / cuckoo
candidate locations." This design specifies them precisely rather than leaving them
ambiguous.

---

## 4. Scope Hierarchy Management and Scope Semantics

### Decision
**Scope hierarchy is maintained explicitly via parent pointers (`parent_id`) in a scope registry.**

### Data Structure
```cpp
struct ScopeInfo {
    uint32_t scope_id{0};
    uint32_t parent_id{0};
    bool active{true};
};

std::unordered_map<uint32_t, ScopeInfo> scope_registry_;
uint32_t current_scope_id_{0};
std::vector<uint32_t> scope_stack_;
```

### Rationale: Explicit Parent-Chain Traversal (`parent_id`)

The lookup mechanism resolves visible declarations by explicitly walking up the lexical hierarchy using `parent_id` pointers (`current_scope = scope_registry[current_scope].parent_id`).

Because candidate bucket locations are computed from `(key, current_scope)` composite keys, the candidate buckets differ for each ancestor scope. Thus, lookup must visit each ancestor scope sequentially. Consequently, Euler-tour interval metadata (`euler_in`, `euler_out`, `euler_counter`, and active-scope sentinel values) are unnecessary for bucket and stash resolution and are intentionally removed from the core SVC-Hash scope data structures.

### Scope Entry/Exit Contract

**Invariant / Contract:**
1. **Proper Nesting:** Scope entry and exit operations must strictly follow lexical (stack-based) proper nesting.
2. **Valid Scope Entry:** `enterScope(S, parent)` is valid only when `parent` is the current active scope (`current_scope_id_ == parent`), except for root-scope initialization (where `parent` is self or 0).
3. **Valid Scope Exit:** `exitScope(S)` is valid only when `S` is the current innermost active scope (`current_scope_id_ == S`).
4. **No Exiting Active Parents:** A scope cannot be exited while any child scope is still active.
5. **Rejection of Invalid Transitions:** Any invalid scope transition (e.g., entering under an inactive parent, exiting out-of-order, or exiting an already-inactive scope) MUST be rejected rather than producing undefined behavior.
6. **State Transition:** Upon successful `exitScope(S)`, scope `S` is marked inactive (`active = false`), popped from `scope_stack_`, and `current_scope_id_` is restored to `S`'s parent scope.
7. **Trace Enforcement:** The Phase 4 trace executor will enforce these same proper-nesting rules when executing input traces.

### Duplicate Declaration Semantics (Project Contract)

**Assumption / Contract:** A `(key, scope_id)` pair may be declared at most once. A duplicate declaration of the same identifier within the same scope is rejected by the symbol-table insertion contract / trace executor.

Under this contract, any valid trace or caller guarantees that within a single scope `S`, at most one entry exists for identifier `K` across all buckets and the stash. Shadowing between different scopes remains fully supported and is resolved by ancestor order.

---

## 5. Lookup Algorithm — Complete Specification

### 5.1. Design Decision: Scope Resolution via Parent-Chain Traversal

Under composite-key hashing, `hash(key, scope_id)` maps each `(key, scope)` pair to its own bucket pair. Declarations of the same identifier in **different scopes** reside in **different buckets**. 

Lookup resolves symbol visibility by starting at `lookup_scope_id` and ascending the ancestor tree via `parent_id` links. At each ancestor level `current_scope`, the algorithm inspects candidate buckets and the stash for entries matching `(key, current_scope)`. The first matching entry encountered is returned immediately, guaranteeing that inner-scope declarations shadow outer-scope declarations.

### 5.2. Integrated Per-Ancestor Bucket and Stash Probing

To enforce shadowing correctness, **stash lookup MUST occur per ancestor scope during the ancestor walk**, rather than globally after the entire ancestor walk completes.

If the stash were scanned only after probing all ancestor buckets, a bucket-resident declaration in an outer scope (e.g., global scope 0) would be returned before inspecting a stash-resident declaration in an inner scope (e.g., scope 2). To prevent this correctness flaw:

> For EACH ancestor scope `current_scope` on the path from `lookup_scope_id` to the root:
> 1. Compute candidate buckets `b1` and `b2` for `(key, current_scope)`.
> 2. Probe slots in `b1` and `b2` for `(key, current_scope)`.
> 3. Probe occupied stash slots for `(key, current_scope)`.
> 4. If found in either bucket or stash, return the symbol value immediately.
> 5. Otherwise, advance to `parent_id`.

Because stash entries are checked per exact scope `(key, current_scope)`, no Euler interval filtering or timestamp comparisons are required.

### 5.3. Complete Lookup Pseudocode

```
FUNCTION lookup(key, lookup_scope_id) -> Optional<SymbolValue>:

    // ── Per-Ancestor Scope Traversal ─────────────────────────────
    //
    // Walk from lookup_scope_id toward the root scope. At each ancestor
    // scope, probe both composite-key candidate buckets AND the stash
    // for exact (key, current_scope) matches.
    // The first match found is the innermost (shadowing) declaration.

    current_scope ← lookup_scope_id
    visited_root  ← false

    WHILE NOT visited_root:
        // 1. Compute candidate buckets for current_scope
        b1 ← hash1(key, current_scope) MOD num_buckets
        b2 ← hash2(key, current_scope) MOD num_buckets
        IF b2 == b1:
            b2 ← (b1 + 1) MOD num_buckets

        // 2. Probe candidate buckets (2 buckets × BUCKET_SIZE slots)
        FOR slot IN buckets[b1].entries ∪ buckets[b2].entries:
            IF slot.occupied
               AND NOT slot.tombstoned
               AND slot.key == key
               AND slot.scope_id == current_scope:
                RETURN slot.value           // ◄ FOUND in bucket for current_scope

        // 3. Probe stash for exact (key, current_scope) match
        FOR i ← 0 TO STASH_SIZE − 1:
            entry ← stash[i]
            IF entry.occupied
               AND NOT entry.tombstoned
               AND entry.key == key
               AND entry.scope_id == current_scope:
                RETURN entry.value          // ◄ FOUND in stash for current_scope

        // 4. Advance to parent scope
        IF current_scope is root scope (scope 0 or scope_registry[current_scope].parent_id == current_scope):
            visited_root ← true
        ELSE:
            current_scope ← scope_registry[current_scope].parent_id

    RETURN nullopt                          // ◄ NOT FOUND in any ancestor scope
```

### 5.4. Concrete Traced Scenarios

All scenarios use this scope tree:
```
Scope 0 (global, root)
├── Scope 1 (parent = 0)
│   ├── Scope 2 (parent = 1)
│   └── Scope 3 (parent = 1)
└── Scope 4 (parent = 0)
```

Declarations:
- `insert("x", val_0, scope_id=0)` — "x" declared at global scope (resides in bucket `hash("x", 0)`)
- `insert("x", val_2, scope_id=2)` — "x" re-declared in scope 2 (resides in stash due to cuckoo eviction displacement)
- `insert("y", val_1, scope_id=1)` — "y" declared only in scope 1

---

#### Scenario A: Identifier exists in candidate bucket of current scope

**Call:** `lookup("y", scope_id=1)`

**Trace:**
```
Step 1: current_scope = 1
        b1 = hash1("y", 1) % N,  b2 = hash2("y", 1) % N
        Scan bucket[b1] and bucket[b2]:
          → FOUND: slot with key="y", scope_id=1, occupied, not tombstoned
        RETURN val_1
```
**Result:** `val_1`.  
**Slot comparisons:** ≤ 8 bucket slots.

---

#### Scenario B: Identifier exists in parent scope

**Call:** `lookup("y", scope_id=2)`

"y" was declared in scope 1. Scope 2 is a child of scope 1.

**Trace:**
```
Step 1: current_scope = 2
        b1 = hash1("y", 2) % N,  b2 = hash2("y", 2) % N
        Scan bucket[b1] and bucket[b2] → no match for ("y", 2)
        Scan stash → no match for ("y", 2)
Step 2: current_scope = parent(2) = 1
        b1 = hash1("y", 1) % N,  b2 = hash2("y", 1) % N
        Scan bucket[b1] and bucket[b2]:
          → FOUND: slot with key="y", scope_id=1, occupied, not tombstoned
        RETURN val_1
```
**Result:** `val_1`.  
**Slot comparisons:** 16 (scope 2: 8 bucket + 8 stash) + ≤ 8 (scope 1 bucket) = ≤ 24.

---

#### Scenario C: Inner-scope stash declaration shadows outer-scope bucket declaration

**Call:** `lookup("x", scope_id=2)`

"x" is in stash for scope 2 (`val_2`) and in bucket for scope 0 (`val_0`).

**Trace:**
```
Step 1: current_scope = 2
        b1 = hash1("x", 2) % N,  b2 = hash2("x", 2) % N
        Scan bucket[b1] and bucket[b2] → no match for ("x", 2)
        Scan stash:
          → FOUND: stash slot with key="x", scope_id=2, occupied, not tombstoned
        RETURN val_2
```
**Result:** `val_2` (scope 2 stash declaration correctly shadows scope 0 bucket declaration).  
**Slot comparisons:** 8 bucket slots + ≤ 8 stash slots = ≤ 16.  
**Key Property:** The scope 0 bucket entry for "x" is never inspected because scope 2 produces an immediate match in the stash.

---

#### Scenario D: No declaration exists

**Call:** `lookup("z", scope_id=2)`

"z" was never declared in any scope.

**Trace:**
```
Step 1: current_scope = 2: check buckets (8) + stash (8) → no match
Step 2: current_scope = parent(2) = 1: check buckets (8) + stash (8) → no match
Step 3: current_scope = parent(1) = 0: check buckets (8) + stash (8) → no match
        visited_root = true → exit loop
RETURN nullopt
```
**Result:** `nullopt`.  
**Slot comparisons:** 3 ancestor levels × (8 bucket + 8 stash) = 48 slot checks.

---

### 5.5. Complexity Analysis

Let:
- $d$ = the number of scopes on the ancestor path from `lookup_scope_id` to the root (inclusive). This equals `nesting depth + 1`.
- $B$ = `BUCKET_SIZE` = 4 (slots per bucket, so 2 candidate buckets = 8 slots per scope).
- $S$ = `STASH_SIZE` = 8 (stash slots checked per scope).

#### Worst-Case Complexity (identifier not found)

At each ancestor level on the path of depth $d$, the lookup probes 2 candidate buckets ($2B = 8$ slots) and the stash ($S = 8$ slots).

$$T_{\text{worst}} = d \times (2B + S) = d \times (8 + 8) = 16d$$

Per-slot work is O(1): string comparison + integer comparisons + boolean checks. Total worst-case is **O(d)** with a tight upper bound of 16 slot checks per ancestor level.

| Nesting depth $d$ | Worst-case slot comparisons ($16d$) |
|---|---|
| 1 (global only) | 16 |
| 4 | 64 |
| 8 | 128 |
| 16 | 256 |
| 32 | 512 |
| 64 | 1024 |

#### Found Complexity (identifier declared $k$ ancestor levels above lookup scope)

Let $k$ be the number of ancestor steps traversed before reaching the scope containing the target declaration ($k = 0$ for current scope, $k = 1$ for immediate parent, etc.).

For the preceding $k$ ancestor levels, the algorithm probes both candidate buckets ($2B$) and the stash ($S$), incurring $k \times (2B + S) = 16k$ checks. At the matching level $k$, it probes candidate buckets (up to $2B$) or stash (up to $S$), taking up to $2B + S = 16$ checks.

Thus, the worst-case found cost for a declaration located $k$ levels up is:

$$T_{\text{found}}(k) \le (k + 1) \times (2B + S) = 16(k + 1)$$

| Declaration location | $k$ | Max slot comparisons |
|---|---|---|
| Current scope | 0 | ≤ 16 |
| Immediate parent | 1 | ≤ 32 |
| Grandparent | 2 | ≤ 48 |
| Global (from depth 8) | 7 | ≤ 128 |

#### Comparison with Plain Cuckoo Hashing

| Property | Plain Cuckoo | SVC-Hash |
|---|---|---|
| Lookup cost | O(2B) = O(8), independent of scope | O(d × (2B + S)) = O(16d) |
| Scope awareness | None | Innermost-visible declaration resolution |
| Shadowing | Not supported | Correct by construction (inside-out walk) |

**This cost difference is exactly what the Phase 7 ablation study measures.**

---

### 5.6. Stash Interaction Details

Under v2.2.0, stash entries interact with lookup as follows:

1. **Per-Ancestor Probing:** The stash is checked during each iteration of the ancestor walk for entries matching `entry.scope_id == current_scope` and `entry.key == key`.
2. **Shadowing Preservation:** Because scope 2's stash entries are checked before scope 1's or scope 0's candidate buckets are computed, an inner-scope stashed symbol correctly shadows any outer-scope symbol.
3. **No Duplicate Stash Entries:** Under the duplicate declaration contract, at most one entry (bucket or stash) exists for `(key, scope_id)`.
4. **Scope Exit Cleans Stash:** When `exitScope(S)` is executed, `scope_entries_[S]` is used to locate and tombstone matching `(key, S)` entries in both buckets and the stash.

---

## 6. Scope Entry and Exit Implementation

### Scope Entry (`enterScope(scope_id, parent_scope_id)`)

1. **Validation:** Check the Scope Entry/Exit Contract.
   - For non-root scopes, verify `parent_scope_id == current_scope_id_` and `scope_registry_.find(scope_id) == scope_registry_.end()`.
   - If invalid (e.g. `parent_scope_id` is inactive or not the current scope), reject the call (return `false` / throw exception) rather than producing undefined behavior.
2. Create a `ScopeInfo` entry in `scope_registry_`:
   - `scope_id`, `parent_id = parent_scope_id`
   - `active = true`
3. Push `scope_id` onto `scope_stack_`.
4. Set `current_scope_id_ = scope_id`.
5. Initialize an empty entry in `scope_entries_[scope_id]` (the per-scope insertion log).

**Cost:** O(1) — validation, map insertion, stack push.

### Scope Exit (`exitScope(scope_id)`)

1. **Validation:** Check the Scope Entry/Exit Contract.
   - Verify `scope_id == current_scope_id_` (i.e. `scope_id` is the current innermost active scope at top of `scope_stack_`).
   - If invalid (e.g. child scopes are still active or `scope_id` is not the current active scope), reject the call rather than producing undefined behavior.
2. Mark scope inactive: `scope_registry_[scope_id].active = false`.
3. **Tombstone all declarations in this scope:**
   For each key `K` recorded in `scope_entries_[scope_id]`:
   - Compute `b1 = hash1(K, scope_id) % num_buckets_` and
     `b2 = hash2(K, scope_id) % num_buckets_`.
   - Scan bucket `b1` and bucket `b2` for an entry with
     `key == K AND scope_id == scope_id AND occupied AND NOT tombstoned`.
   - If found, set `tombstoned = true` and increment `tombstone_count_`.
   - Also scan the stash for matching `(K, scope_id)` entries and tombstone them.
4. Pop `scope_id` from `scope_stack_`.
5. Set `current_scope_id_` to the new stack top (the parent scope).

**Cost:** Let $m$ be the number of declarations recorded in the exiting scope. The cost is $O(m \times (2 \times \text{BUCKET\_SIZE} + \text{STASH\_SIZE})) = O(16m)$.

---

## 7. Per-Scope Insertion Log Design

### Decision

The per-scope insertion log stores **only the identifier strings**, not physical
(bucket_index, slot_index) pairs.

```cpp
std::unordered_map<uint32_t, std::vector<std::string>> scope_entries_;
```

### Why Not Store Physical Locations?

1. **Cuckoo relocations invalidate physical locations.** Displacing an entry during eviction makes physical indices stale.
2. **Rehash invalidates all physical locations.** Table capacity changes alter `hash % num_buckets`.
3. **Stash entries have no bucket index.**

### Why Key-Only Logs Work

Under composite-key hashing, the physical location of any entry can be recomputed at any time from its `(key, scope_id)` pair:
```
b1 = hash1(key, scope_id) % num_buckets_
b2 = hash2(key, scope_id) % num_buckets_
```
The entry must be in bucket `b1`, bucket `b2`, or the stash. A linear scan of at most `2 × BUCKET_SIZE + STASH_SIZE = 16` slots finds it.

---

## 8. Stash/Overflow Handling

### Decision
**A small, fixed-size overflow stash of 8 entries.** When a cuckoo eviction chain exceeds
the maximum displacement depth without finding a vacant or tombstoned slot, the displaced
entry is placed in the stash.

### Structure
```cpp
static constexpr size_t STASH_SIZE = 8;
BucketEntry stash_[STASH_SIZE];
size_t stash_count_{0};
```

### Stash Entries and Scope Ownership

Each stash entry stores `scope_id` alongside `key`, `value`, `occupied`, and `tombstoned`.

1. **Lookup correctness:** Scanned during per-ancestor probe step for exact `(key, current_scope)` match.
2. **Scope exit correctness:** Scanned during `exitScope` for exact `(key, scope_id)` match to mark `tombstoned = true`.
3. **No special InsertionRecord format needed:** Covered by key-only insertion log.

### Stash Overflow Trigger
If the stash is full (all 8 slots occupied by non-tombstoned entries) and another entry needs to be stashed, a full rehash/rebuild is triggered.

---

## 9. Tombstone Strategy

### Decision
**Tombstoning with deferred compaction.** Exited scope entries are marked `tombstoned = true` but not physically removed.

### Tombstoned Slot Behavior

| Operation | Treatment of Tombstoned Slots |
|---|---|
| **Lookup** | Skipped (invisible). |
| **Insertion** | Treated as vacant — a tombstoned slot can be overwritten by a new entry. |
| **Cuckoo eviction** | A tombstoned slot can absorb a displaced entry without triggering further evictions. |
| **Rebuild** | Tombstoned entries are permanently removed; only occupied, non-tombstoned entries are re-inserted. |

### Tombstone Accumulation Threshold
If `tombstone_count_ / total_capacity > 0.25`, a compaction rebuild is triggered.

---

## 10. Rehash/Rebuild/Compaction Triggers and Behavior

### Triggers
1. **Stash overflow:** The stash is full and another entry needs to be stashed.
2. **Tombstone saturation:** `tombstone_count_ / total_capacity > 0.25`.
3. **Load factor threshold:** Effective load factor `(occupied_count_ - tombstone_count_) / total_capacity > 0.90`.

### Rebuild Procedure
1. Collect all occupied, non-tombstoned entries from all buckets and the stash.
2. Double the number of buckets (`num_buckets_ *= 2`).
3. Clear all bucket entries and the stash.
4. Reset `tombstone_count_ = 0`, `stash_count_ = 0`.
5. Re-insert all collected entries using the same fixed hash seeds but new `num_buckets_`.

---

## 11. Cuckoo Eviction (Kick Chain) Procedure

When inserting `(key, scope_id)` and both candidate buckets are full (all 8 slots occupied and non-tombstoned):

1. Select one of the two candidate buckets.
2. Select a victim entry from that bucket.
3. Displace the victim and place the new entry in its slot.
4. Compute the victim's other candidate bucket (`hash(victim.key, victim.scope_id)`).
5. If the other bucket has a vacant or tombstoned slot, place the victim there.
6. Otherwise, recursively displace another entry.
7. If chain length exceeds `MAX_KICK_DEPTH` (default: 500), place victim in stash.

---

## 12. Summary of Deviations from Prior Design Sketch

| Design Element | Prior Sketch | v2.2.0 Decision | Status |
|---|---|---|---|
| Bucket size | 4 | 4 | **Matches** |
| Hash functions | Two hash functions | Two FNV-1a with distinct fixed seeds | **Matches** (clarified) |
| Hash description | Independent hash sequences | Two deterministic candidate streams with distinct fixed FNV-1a offset bases | **Refined** (conservative language) |
| Scope representation | Scope interval / Euler-style | Parent-chain traversal (`parent_id`), Euler intervals removed | **Refined** (simplified) |
| Scope contract | Not specified | Strict proper nesting (`enterScope` under active parent, `exitScope` on active innermost) | **Contract defined** |
| Stash lookup | Global stash scan | Per-ancestor scope stash probe | **Corrected** (shadowing fix) |
| Worst-case lookup | Not analyzed | $O(d \times (2B + S)) = 16d$ | **Updated** |
| Duplicate declaration | Not specified | At most one declaration per `(key, scope_id)` pair | **Contract defined** |

### Key Architectural Corrections in v2.2.0

1. **Scope Entry/Exit Contract:** Strict proper-nesting invariant enforced; invalid scope transitions rejected.
2. **Conservative Hash Wording:** `(key, scope_id)` pairs hashed as distinct composite keys without claiming statistical independence.
3. **Per-ancestor stash lookup:** Inner-scope stashed symbol shadows outer-scope bucket symbol.
4. **Euler intervals removed:** Scope resolution relies on explicit `parent_id` traversal.
5. **Complexity bounded:** Worst-case lookup bounded by $16d$ slot checks.
6. **Duplicate declaration semantics:** Declaring `(key, scope_id)` twice in the same scope is prohibited by contract.
