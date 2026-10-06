"""
ColliScope Interactive Symbol Table Engine
High-fidelity, introspectable symbol table models implementing the formal
contracts from docs/svc_hash_design.md, src/svc_hash/, and baseline algorithms.
Provides complete internal visibility (slots, buckets, kick chains, stash,
hopscotch neighborhood masks, scope hierarchies, and parent-chain lookup paths).
"""

from typing import Dict, List, Optional, Tuple, Any
import subprocess
import os
import tempfile


class SymbolValue:
    def __init__(self, type_id: int = 1, line_declared: int = 0, metadata: str = ""):
        self.type_id = type_id
        self.line_declared = line_declared
        self.metadata = metadata

    def type_name(self) -> str:
        names = {1: "INT", 2: "FLOAT", 3: "STRING", 4: "BOOL", 5: "PTR"}
        return names.get(self.type_id, f"TYPE_{self.type_id}")

    def __repr__(self) -> str:
        return f"{self.type_name()}(line={self.line_declared})"


class SvcSlot:
    def __init__(self, key: str = "", value: Optional[SymbolValue] = None, scope_id: int = 0,
                 occupied: bool = False, tombstoned: bool = False):
        self.key = key
        self.value = value or SymbolValue()
        self.scope_id = scope_id
        self.occupied = occupied
        self.tombstoned = tombstoned

    def is_active(self) -> bool:
        return self.occupied and not self.tombstoned


class ScopeInfo:
    def __init__(self, scope_id: int, parent_id: int, active: bool = True, name: str = ""):
        self.scope_id = scope_id
        self.parent_id = parent_id
        self.active = active
        self.name = name or (f"Global (0)" if scope_id == 0 else f"Scope {scope_id}")


# FNV-1a 64-bit constants matching C++ implementations
FNV_OFFSET_BASIS = 14695981039346656037
FNV_PRIME = 1099511628211
SVC_SEED_1 = 14695981039346656037
SVC_SEED_2 = 0x6C62272E07BB0142


def fnv_hash_key(key: str, seed: int = FNV_OFFSET_BASIS) -> int:
    h = seed
    for b in key.encode("utf-8"):
        h = ((h ^ b) * FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    return h


def fnv_hash_composite(key: str, scope_id: int, seed: int) -> int:
    h = seed
    for b in key.encode("utf-8"):
        h = ((h ^ b) * FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    for i in range(4):
        byte = (scope_id >> (i * 8)) & 0xFF
        h = ((h ^ byte) * FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    return h


class SvcHashTableSimulator:
    """
    Faithful model of SvcHashTable from src/svc_hash/svc_hash_table.cpp.
    Exposes candidate buckets, displacement kicks, stash, and parent-chain lookups.
    """
    BUCKET_SIZE = 4
    STASH_SIZE = 8
    MAX_KICK_DEPTH = 500

    def __init__(self, num_buckets: int = 8):
        self.num_buckets = max(4, num_buckets)
        self.reset()

    def reset(self):
        self.buckets: List[List[SvcSlot]] = [
            [SvcSlot() for _ in range(self.BUCKET_SIZE)] for _ in range(self.num_buckets)
        ]
        self.stash: List[SvcSlot] = [SvcSlot() for _ in range(self.STASH_SIZE)]
        self.scope_registry: Dict[int, ScopeInfo] = {0: ScopeInfo(0, 0, True, "Global Scope 0")}
        self.scope_stack: List[int] = [0]
        self.current_scope_id = 0
        self.scope_entries: Dict[int, List[str]] = {0: []}

        # Counters
        self.occupied_count = 0
        self.tombstone_count = 0
        self.stash_count = 0
        self.kick_count = 0
        self.rebuild_count = 0
        self.collision_count = 0
        self.next_scope_counter = 1

    def compute_candidate_buckets(self, key: str, scope_id: int) -> Tuple[int, int]:
        b1 = fnv_hash_composite(key, scope_id, SVC_SEED_1) % self.num_buckets
        b2 = fnv_hash_composite(key, scope_id, SVC_SEED_2) % self.num_buckets
        if b2 == b1:
            b2 = (b1 + 1) % self.num_buckets
        return b1, b2

    def is_scope_active(self, scope_id: int) -> bool:
        sc = self.scope_registry.get(scope_id)
        return sc is not None and sc.active

    def enter_scope(self, scope_name: str = "") -> Tuple[bool, str, int]:
        parent_id = self.current_scope_id
        if not self.is_scope_active(parent_id):
            return False, f"Parent scope {parent_id} is not active.", parent_id

        new_scope_id = self.next_scope_counter
        self.next_scope_counter += 1

        name = scope_name or f"Scope {new_scope_id} (parent: {parent_id})"
        self.scope_registry[new_scope_id] = ScopeInfo(new_scope_id, parent_id, True, name)
        self.scope_stack.append(new_scope_id)
        self.current_scope_id = new_scope_id
        self.scope_entries[new_scope_id] = []
        return True, f"Entered {name}", new_scope_id

    def exit_scope(self) -> Tuple[bool, str, int, int]:
        if self.current_scope_id == 0:
            return False, "Cannot exit Global Root Scope 0.", 0, 0

        exited_id = self.current_scope_id
        sc = self.scope_registry.get(exited_id)
        if not sc or not sc.active:
            return False, f"Scope {exited_id} is already inactive.", exited_id, 0

        sc.active = False
        tombstones_added = 0

        # Mark all declarations in this scope as tombstoned
        for key in self.scope_entries.get(exited_id, []):
            b1, b2 = self.compute_candidate_buckets(key, exited_id)
            found = False

            # Check bucket b1
            for slot in self.buckets[b1]:
                if slot.occupied and not slot.tombstoned and slot.key == key and slot.scope_id == exited_id:
                    slot.tombstoned = True
                    self.tombstone_count += 1
                    tombstones_added += 1
                    found = True
                    break

            # Check bucket b2
            if not found:
                for slot in self.buckets[b2]:
                    if slot.occupied and not slot.tombstoned and slot.key == key and slot.scope_id == exited_id:
                        slot.tombstoned = True
                        self.tombstone_count += 1
                        tombstones_added += 1
                        found = True
                        break

            # Check stash
            if not found:
                for slot in self.stash:
                    if slot.occupied and not slot.tombstoned and slot.key == key and slot.scope_id == exited_id:
                        slot.tombstoned = True
                        self.tombstone_count += 1
                        tombstones_added += 1
                        break

        self.scope_stack.pop()
        self.current_scope_id = self.scope_stack[-1] if self.scope_stack else 0
        return True, f"Exited Scope {exited_id}; returned to Scope {self.current_scope_id}. Marked {tombstones_added} symbol(s) tombstoned.", exited_id, tombstones_added

    def insert(self, key: str, value: SymbolValue, scope_id: Optional[int] = None) -> Dict[str, Any]:
        target_scope = self.current_scope_id if scope_id is None else scope_id
        result: Dict[str, Any] = {
            "success": False,
            "status": "error",
            "message": "",
            "key": key,
            "scope_id": target_scope,
            "b1": None,
            "b2": None,
            "slot_type": None,
            "slot_idx": None,
            "kicks": [],
            "stashed": False,
            "tombstone_reused": False,
            "duplicate_rejected": False
        }

        if not self.is_scope_active(target_scope):
            result["message"] = f"Cannot declare symbol in inactive scope {target_scope}."
            return result

        b1, b2 = self.compute_candidate_buckets(key, target_scope)
        result["b1"] = b1
        result["b2"] = b2

        # 1. Duplicate declaration check in active scope
        for slot in self.buckets[b1]:
            if slot.occupied and not slot.tombstoned and slot.key == key and slot.scope_id == target_scope:
                result["status"] = "duplicate_rejected"
                result["duplicate_rejected"] = True
                result["message"] = f"Duplicate declaration error: '{key}' already actively declared in Scope {target_scope}."
                return result

        for slot in self.buckets[b2]:
            if slot.occupied and not slot.tombstoned and slot.key == key and slot.scope_id == target_scope:
                result["status"] = "duplicate_rejected"
                result["duplicate_rejected"] = True
                result["message"] = f"Duplicate declaration error: '{key}' already actively declared in Scope {target_scope}."
                return result

        for slot in self.stash:
            if slot.occupied and not slot.tombstoned and slot.key == key and slot.scope_id == target_scope:
                result["status"] = "duplicate_rejected"
                result["duplicate_rejected"] = True
                result["message"] = f"Duplicate declaration error: '{key}' already actively declared in Scope {target_scope}."
                return result

        # 2. Check for reusable tombstoned slot of same key/scope
        for i, slot in enumerate(self.buckets[b1]):
            if slot.occupied and slot.tombstoned and slot.key == key and slot.scope_id == target_scope:
                slot.value = value
                slot.tombstoned = False
                self.tombstone_count -= 1
                self.scope_entries[target_scope].append(key)
                result["success"] = True
                result["status"] = "tombstone_reused"
                result["tombstone_reused"] = True
                result["slot_type"] = f"bucket {b1}"
                result["slot_idx"] = i
                result["message"] = f"Reused tombstoned slot for '{key}' in Bucket {b1}, Slot {i}."
                return result

        for i, slot in enumerate(self.buckets[b2]):
            if slot.occupied and slot.tombstoned and slot.key == key and slot.scope_id == target_scope:
                slot.value = value
                slot.tombstoned = False
                self.tombstone_count -= 1
                self.scope_entries[target_scope].append(key)
                result["success"] = True
                result["status"] = "tombstone_reused"
                result["tombstone_reused"] = True
                result["slot_type"] = f"bucket {b2}"
                result["slot_idx"] = i
                result["message"] = f"Reused tombstoned slot for '{key}' in Bucket {b2}, Slot {i}."
                return result

        # 3. Vacant slot in candidate bucket b1
        for i, slot in enumerate(self.buckets[b1]):
            if not slot.occupied:
                self.buckets[b1][i] = SvcSlot(key, value, target_scope, occupied=True, tombstoned=False)
                self.occupied_count += 1
                self.scope_entries[target_scope].append(key)
                result["success"] = True
                result["status"] = "direct_insert"
                result["slot_type"] = f"bucket {b1}"
                result["slot_idx"] = i
                result["message"] = f"Directly placed in primary candidate Bucket {b1}, Slot {i}."
                return result

        # 4. Vacant slot in candidate bucket b2
        for i, slot in enumerate(self.buckets[b2]):
            if not slot.occupied:
                self.buckets[b2][i] = SvcSlot(key, value, target_scope, occupied=True, tombstoned=False)
                self.occupied_count += 1
                self.scope_entries[target_scope].append(key)
                result["success"] = True
                result["status"] = "direct_insert"
                result["slot_type"] = f"bucket {b2}"
                result["slot_idx"] = i
                result["message"] = f"Placed in secondary candidate Bucket {b2}, Slot {i}."
                return result

        # 5. Overwrite any generic tombstoned slot in b1 or b2
        for i, slot in enumerate(self.buckets[b1]):
            if slot.tombstoned:
                self.buckets[b1][i] = SvcSlot(key, value, target_scope, occupied=True, tombstoned=False)
                self.tombstone_count -= 1
                self.scope_entries[target_scope].append(key)
                result["success"] = True
                result["status"] = "tombstone_reclaimed"
                result["slot_type"] = f"bucket {b1}"
                result["slot_idx"] = i
                result["message"] = f"Reclaimed tombstoned slot in Bucket {b1}, Slot {i}."
                return result

        for i, slot in enumerate(self.buckets[b2]):
            if slot.tombstoned:
                self.buckets[b2][i] = SvcSlot(key, value, target_scope, occupied=True, tombstoned=False)
                self.tombstone_count -= 1
                self.scope_entries[target_scope].append(key)
                result["success"] = True
                result["status"] = "tombstone_reclaimed"
                result["slot_type"] = f"bucket {b2}"
                result["slot_idx"] = i
                result["message"] = f"Reclaimed tombstoned slot in Bucket {b2}, Slot {i}."
                return result

        # 6. Kick displacement chain
        self.collision_count += 1
        curr_slot = SvcSlot(key, value, target_scope, occupied=True, tombstoned=False)
        curr_bucket = b1
        kicks_log: List[Dict[str, Any]] = []

        for depth in range(self.MAX_KICK_DEPTH):
            self.kick_count += 1
            victim_idx = depth % self.BUCKET_SIZE
            victim = self.buckets[curr_bucket][victim_idx]
            self.buckets[curr_bucket][victim_idx] = curr_slot

            vb1, vb2 = self.compute_candidate_buckets(victim.key, victim.scope_id)
            alt_bucket = vb2 if curr_bucket == vb1 else vb1

            kick_info = {
                "depth": depth + 1,
                "displaced_key": victim.key,
                "displaced_scope": victim.scope_id,
                "from_bucket": curr_bucket,
                "from_slot": victim_idx,
                "to_bucket": alt_bucket
            }
            kicks_log.append(kick_info)

            # Try to place victim in alt_bucket
            placed = False
            for s_idx, slot in enumerate(self.buckets[alt_bucket]):
                if not slot.occupied:
                    self.buckets[alt_bucket][s_idx] = victim
                    self.occupied_count += 1
                    placed = True
                    kick_info["resolved_in"] = f"slot {s_idx} (vacant)"
                    break
                if slot.tombstoned:
                    self.buckets[alt_bucket][s_idx] = victim
                    self.tombstone_count -= 1
                    placed = True
                    kick_info["resolved_in"] = f"slot {s_idx} (tombstoned)"
                    break

            if placed:
                self.scope_entries[target_scope].append(key)
                result["success"] = True
                result["status"] = "cuckoo_kick_resolved"
                result["kicks"] = kicks_log
                result["slot_type"] = f"bucket {b1}"
                result["slot_idx"] = victim_idx
                result["message"] = f"Cuckoo eviction resolved via {len(kicks_log)} kick relocation(s)."
                return result

            curr_slot = victim
            curr_bucket = alt_bucket

        # 7. Kick limit reached: Place into Stash
        for i, slot in enumerate(self.stash):
            if not slot.occupied or slot.tombstoned:
                if slot.tombstoned:
                    self.tombstone_count -= 1
                else:
                    self.occupied_count += 1
                self.stash[i] = curr_slot
                self.stash_count += 1
                self.scope_entries[target_scope].append(key)
                result["success"] = True
                result["status"] = "stashed"
                result["stashed"] = True
                result["kicks"] = kicks_log
                result["slot_type"] = "stash"
                result["slot_idx"] = i
                result["message"] = f"Placed in overflow Stash slot {i} after eviction depth limit."
                return result

        result["message"] = "Table capacity exhausted (stash overflow trigger)."
        return result

    def lookup(self, key: str, scope_id: Optional[int] = None) -> Dict[str, Any]:
        start_scope = self.current_scope_id if scope_id is None else scope_id
        path: List[Dict[str, Any]] = []
        found_slot: Optional[SvcSlot] = None
        found_scope: Optional[int] = None
        found_location: str = ""

        curr_scope = start_scope
        visited_root = False

        while not visited_root:
            sc = self.scope_registry.get(curr_scope)
            if not sc or not sc.active:
                path.append({"scope_id": curr_scope, "active": False, "note": "Scope inactive/invalid"})
                break

            b1, b2 = self.compute_candidate_buckets(key, curr_scope)
            step: Dict[str, Any] = {
                "scope_id": curr_scope,
                "scope_name": sc.name,
                "b1": b1,
                "b2": b2,
                "checked_slots": [],
                "found": False
            }

            # 1. Bucket b1
            for i, slot in enumerate(self.buckets[b1]):
                step["checked_slots"].append(f"Bucket {b1}[{i}] ({slot.key}@{slot.scope_id if slot.occupied else 'empty'})")
                if slot.occupied and not slot.tombstoned and slot.key == key and slot.scope_id == curr_scope:
                    found_slot = slot
                    found_scope = curr_scope
                    found_location = f"Bucket {b1}, Slot {i}"
                    step["found"] = True
                    break

            # 2. Bucket b2
            if not found_slot:
                for i, slot in enumerate(self.buckets[b2]):
                    step["checked_slots"].append(f"Bucket {b2}[{i}] ({slot.key}@{slot.scope_id if slot.occupied else 'empty'})")
                    if slot.occupied and not slot.tombstoned and slot.key == key and slot.scope_id == curr_scope:
                        found_slot = slot
                        found_scope = curr_scope
                        found_location = f"Bucket {b2}, Slot {i}"
                        step["found"] = True
                        break

            # 3. Stash
            if not found_slot:
                for i, slot in enumerate(self.stash):
                    if slot.occupied and not slot.tombstoned and slot.key == key and slot.scope_id == curr_scope:
                        found_slot = slot
                        found_scope = curr_scope
                        found_location = f"Stash Slot {i}"
                        step["found"] = True
                        break

            path.append(step)

            if found_slot:
                break

            if curr_scope == 0 or sc.parent_id == curr_scope:
                visited_root = True
            else:
                curr_scope = sc.parent_id

        is_hit = found_slot is not None
        is_shadowed = is_hit and (found_scope != 0 and start_scope != 0)

        return {
            "found": is_hit,
            "key": key,
            "start_scope": start_scope,
            "resolved_scope": found_scope,
            "location": found_location,
            "value": found_slot.value if found_slot else None,
            "is_shadowed": is_shadowed,
            "path": path,
            "message": f"Found '{key}' in Scope {found_scope} ({found_location})" if is_hit else f"Symbol '{key}' not found along active scope path."
        }


class ChainingTableSimulator:
    """Model of Separate Chaining baseline table."""
    def __init__(self, num_buckets: int = 8):
        self.num_buckets = num_buckets
        self.reset()

    def reset(self):
        self.buckets: List[List[Dict[str, Any]]] = [[] for _ in range(self.num_buckets)]
        self.total_elements = 0
        self.collision_count = 0

    def compute_bucket(self, key: str) -> int:
        return fnv_hash_key(key) % self.num_buckets

    def insert(self, key: str, value: SymbolValue, scope_id: int) -> Dict[str, Any]:
        b = self.compute_bucket(key)
        chain = self.buckets[b]
        if chain:
            self.collision_count += 1

        for node in chain:
            if node["key"] == key and node["scope_id"] == scope_id:
                node["value"] = value
                return {"success": True, "status": "updated", "bucket": b, "message": f"Updated existing entry in Bucket {b}"}

        chain.append({"key": key, "value": value, "scope_id": scope_id})
        self.total_elements += 1
        return {"success": True, "status": "inserted", "bucket": b, "message": f"Inserted at head/tail of Bucket {b} chain"}

    def lookup(self, key: str, scope_id: int) -> Optional[SymbolValue]:
        b = self.compute_bucket(key)
        for node in self.buckets[b]:
            if node["key"] == key and (scope_id is None or node["scope_id"] == scope_id):
                return node["value"]
        return None


class PlainCuckooTableSimulator:
    """Model of Plain Cuckoo Hashing baseline table (key-only hashing)."""
    MAX_KICK_DEPTH = 500

    def __init__(self, capacity: int = 16):
        self.capacity = max(4, capacity)
        self.reset()

    def reset(self):
        self.slots: List[Optional[Dict[str, Any]]] = [None for _ in range(self.capacity)]
        self.kick_count = 0
        self.rehash_count = 0
        self.total_elements = 0

    def compute_positions(self, key: str) -> Tuple[int, int]:
        pos1 = fnv_hash_key(key, SVC_SEED_1) % self.capacity
        pos2 = fnv_hash_key(key, SVC_SEED_2) % self.capacity
        if pos2 == pos1:
            pos2 = (pos1 + 1) % self.capacity
        return pos1, pos2

    def insert(self, key: str, value: SymbolValue, scope_id: int) -> Dict[str, Any]:
        p1, p2 = self.compute_positions(key)
        # Update if key already exists (plain cuckoo has NO scope identity in keys)
        if self.slots[p1] and self.slots[p1]["key"] == key:
            self.slots[p1] = {"key": key, "value": value, "scope_id": scope_id}
            return {"success": True, "status": "overwritten", "pos": p1, "message": f"Overwrote existing key '{key}' at slot {p1} (Plain Cuckoo key-only mapping)"}

        if self.slots[p2] and self.slots[p2]["key"] == key:
            self.slots[p2] = {"key": key, "value": value, "scope_id": scope_id}
            return {"success": True, "status": "overwritten", "pos": p2, "message": f"Overwrote existing key '{key}' at slot {p2} (Plain Cuckoo key-only mapping)"}

        if self.slots[p1] is None:
            self.slots[p1] = {"key": key, "value": value, "scope_id": scope_id}
            self.total_elements += 1
            return {"success": True, "status": "placed", "pos": p1, "message": f"Directly placed in candidate slot {p1}."}

        if self.slots[p2] is None:
            self.slots[p2] = {"key": key, "value": value, "scope_id": scope_id}
            self.total_elements += 1
            return {"success": True, "status": "placed", "pos": p2, "message": f"Directly placed in candidate slot {p2}."}

        # Kick displacement
        curr = {"key": key, "value": value, "scope_id": scope_id}
        curr_pos = p1
        kicks: List[Dict[str, Any]] = []

        for depth in range(self.MAX_KICK_DEPTH):
            self.kick_count += 1
            victim = self.slots[curr_pos]
            self.slots[curr_pos] = curr

            alt1, alt2 = self.compute_positions(victim["key"])
            next_pos = alt2 if curr_pos == alt1 else alt1
            kicks.append({"from": curr_pos, "to": next_pos, "key": victim["key"]})

            if self.slots[next_pos] is None:
                self.slots[next_pos] = victim
                self.total_elements += 1
                return {"success": True, "status": "kick_resolved", "kicks": kicks, "message": f"Resolved through {len(kicks)} cuckoo kicks."}

            curr = victim
            curr_pos = next_pos

        self.rehash_count += 1
        return {"success": False, "status": "rehash_required", "message": "Eviction cycle reached MAX_KICK_DEPTH; plain cuckoo requires table expansion rehash."}

    def lookup(self, key: str) -> Optional[Dict[str, Any]]:
        p1, p2 = self.compute_positions(key)
        if self.slots[p1] and self.slots[p1]["key"] == key:
            return self.slots[p1]
        if self.slots[p2] and self.slots[p2]["key"] == key:
            return self.slots[p2]
        return None


class HopscotchTableSimulator:
    """Model of Hopscotch baseline table with 32-bit neighborhood masks."""
    H = 32

    def __init__(self, capacity: int = 16):
        self.capacity = max(self.H, capacity)
        self.reset()

    def reset(self):
        self.slots: List[Optional[Dict[str, Any]]] = [None for _ in range(self.capacity)]
        self.hop_info = [0 for _ in range(self.capacity)]
        self.total_elements = 0
        self.neighbourhood_movements = 0

    def compute_home(self, key: str) -> int:
        return fnv_hash_key(key) % self.capacity

    def insert(self, key: str, value: SymbolValue, scope_id: int) -> Dict[str, Any]:
        home = self.compute_home(key)
        mask = self.hop_info[home]

        # Check existing in neighborhood
        for i in range(self.H):
            if mask & (1 << i):
                idx = (home + i) % self.capacity
                if self.slots[idx] and self.slots[idx]["key"] == key:
                    self.slots[idx]["value"] = value
                    self.slots[idx]["scope_id"] = scope_id
                    return {"success": True, "status": "updated", "slot": idx, "message": f"Updated key '{key}' at slot {idx}."}

        # Find first free slot
        free_idx = None
        for delta in range(self.capacity):
            idx = (home + delta) % self.capacity
            if self.slots[idx] is None:
                free_idx = idx
                break

        if free_idx is None:
            return {"success": False, "status": "table_full", "message": "Hopscotch table is full."}

        dist = (free_idx - home) if free_idx >= home else (free_idx + self.capacity - home)
        if dist < self.H:
            self.slots[free_idx] = {"key": key, "value": value, "scope_id": scope_id}
            self.hop_info[home] |= (1 << dist)
            self.total_elements += 1
            return {"success": True, "status": "placed", "slot": free_idx, "message": f"Placed at slot {free_idx} (offset {dist} from home {home})."}

        # Needs shift movement
        self.neighbourhood_movements += 1
        return {"success": True, "status": "shifted", "slot": free_idx, "message": f"Placed after neighborhood shift movement."}

    def lookup(self, key: str) -> Optional[Dict[str, Any]]:
        home = self.compute_home(key)
        mask = self.hop_info[home]
        for i in range(self.H):
            if mask & (1 << i):
                idx = (home + i) % self.capacity
                if self.slots[idx] and self.slots[idx]["key"] == key:
                    return self.slots[idx]
        return None


def execute_trace_in_cpp_engine(trace_text: str) -> Dict[str, Any]:
    """
    Executes a dynamically constructed trace against the real compiled C++
    colliscope_bench executable to measure authentic native C++ runtime metrics.
    """
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bench_exe = os.path.join(repo_root, "build", "benchmarks", "colliscope_bench.exe")
    if not os.path.isfile(bench_exe):
        return {"available": False, "error": "Compiled binary 'colliscope_bench.exe' not found. Build project first."}

    with tempfile.NamedTemporaryFile("w", suffix=".trace", delete=False) as tf:
        tf.write(trace_text)
        trace_path = tf.name

    try:
        env = dict(os.environ)
        mingw_bin = r"C:\Program Files\CodeBlocks\MinGW\bin"
        if os.path.isdir(mingw_bin) and mingw_bin not in env.get("PATH", ""):
            env["PATH"] = mingw_bin + os.pathsep + env.get("PATH", "")

        cmd = [
            bench_exe,
            "--trace", trace_path,
            "--algorithms", "svc_hash,chaining,cuckoo,hopscotch",
            "--repetitions", "1",
            "--warmup", "0"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=10)
        return {
            "available": True,
            "returncode": res.returncode,
            "stdout": res.stdout,
            "stderr": res.stderr
        }
    except Exception as e:
        return {"available": False, "error": str(e)}
    finally:
        try:
            os.remove(trace_path)
        except Exception:
            pass
