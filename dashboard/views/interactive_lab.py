"""
ColliScope Dashboard: Page 11 - Interactive Symbol Table Lab
Live demonstration interface for Compiler Design students, researchers, and faculty.
Supports interactive operations (ENTER_SCOPE, EXIT_SCOPE, DECLARE, LOOKUP),
live lexical scope trees, bucket/slot state inspection, cuckoo kick chains,
and real C++ engine verification.
"""

import streamlit as st
import pandas as pd
from typing import List, Dict, Any, Optional

from dashboard.symbol_table_engine import (
    SvcHashTableSimulator,
    ChainingTableSimulator,
    PlainCuckooTableSimulator,
    HopscotchTableSimulator,
    SymbolValue,
    execute_trace_in_cpp_engine
)


# Prebuilt Demonstration Scenarios for Compiler Design
PREBUILT_SCENARIOS = {
    "1. Basic Symbol Table Lifecycle": [
        ("DECLARE", "count", 1, "Declare global integer 'count' in Scope 0"),
        ("DECLARE", "total", 2, "Declare global float 'total' in Scope 0"),
        ("LOOKUP", "count", 1, "Look up 'count' in Scope 0 -> Hit"),
        ("LOOKUP", "undefined_var", 1, "Look up undeclared symbol -> Miss"),
    ],
    "2. Lexical Scope Lifecycle": [
        ("DECLARE", "global_config", 1, "Declare global configuration in Scope 0"),
        ("ENTER_SCOPE", "Function 'main'", None, "Enter function 'main' body (Scope 1)"),
        ("DECLARE", "argc", 1, "Declare parameter 'argc' in Scope 1"),
        ("DECLARE", "argv", 5, "Declare parameter 'argv' in Scope 1"),
        ("LOOKUP", "global_config", 1, "Look up global symbol from inside Scope 1 -> Resolved via parent chain"),
        ("EXIT_SCOPE", None, None, "Exit function 'main' (Scope 1 deactivated; symbols tombstoned)"),
        ("LOOKUP", "argc", 1, "Look up 'argc' after Scope 1 exit -> Correctly Misses!"),
    ],
    "3. Variable Shadowing & Unmasking": [
        ("DECLARE", "x", 1, "Declare global variable 'x' (INT) in Scope 0"),
        ("ENTER_SCOPE", "Block 1", None, "Enter nested block (Scope 1)"),
        ("DECLARE", "x", 2, "Declare inner variable 'x' (FLOAT) in Scope 1 -> SHADOWING!"),
        ("LOOKUP", "x", None, "Look up 'x' from Scope 1 -> Resolves to inner FLOAT declaration (Scope 1)"),
        ("EXIT_SCOPE", None, None, "Exit Block 1 (Scope 1 exited; inner 'x' tombstoned)"),
        ("LOOKUP", "x", None, "Look up 'x' from Scope 0 -> Outer INT declaration is unmasked and visible!"),
    ],
    "4. Duplicate Declaration Rejection": [
        ("DECLARE", "buffer_size", 1, "Declare 'buffer_size' in Scope 0"),
        ("DECLARE", "buffer_size", 1, "Attempt to declare 'buffer_size' AGAIN in Scope 0 -> REJECTED!"),
        ("ENTER_SCOPE", "Helper Function", None, "Enter Scope 1"),
        ("DECLARE", "buffer_size", 1, "Declare 'buffer_size' in Scope 1 -> Allowed (different scope)"),
    ],
    "5. Deep Scope Chain Traversal": [
        ("DECLARE", "root_symbol", 1, "Declare 'root_symbol' in Scope 0"),
        ("ENTER_SCOPE", "Level 1", None, "Enter Level 1 (Scope 1)"),
        ("ENTER_SCOPE", "Level 2", None, "Enter Level 2 (Scope 2)"),
        ("ENTER_SCOPE", "Level 3", None, "Enter Level 3 (Scope 3)"),
        ("LOOKUP", "root_symbol", None, "Look up 'root_symbol' from Scope 3 -> Traverses 3 -> 2 -> 1 -> 0 to find symbol"),
        ("EXIT_SCOPE", None, None, "Exit Level 3"),
        ("EXIT_SCOPE", None, None, "Exit Level 2"),
        ("EXIT_SCOPE", None, None, "Exit Level 1"),
    ],
    "6. Collision & Cuckoo Eviction Chain": [
        ("DECLARE", "sym_alpha", 1, "Declare 'sym_alpha' in Scope 0"),
        ("DECLARE", "sym_beta", 1, "Declare 'sym_beta' in Scope 0"),
        ("DECLARE", "sym_gamma", 1, "Declare 'sym_gamma' in Scope 0"),
        ("DECLARE", "sym_delta", 1, "Declare 'sym_delta' in Scope 0"),
        ("DECLARE", "sym_epsilon", 1, "Declare 'sym_epsilon' in Scope 0"),
        ("DECLARE", "sym_zeta", 1, "Declare 'sym_zeta' in Scope 0 -> Triggers cuckoo kick displacement chain!"),
    ],
    "7. SVC-Hash vs Plain Cuckoo (Scope Identity)": [
        ("DECLARE", "identifier_x", 1, "Declare 'identifier_x' in Scope 0"),
        ("ENTER_SCOPE", "Inner Function", None, "Enter Scope 1"),
        ("DECLARE", "identifier_x", 2, "Declare 'identifier_x' in Scope 1 (Shadowing)"),
        ("LOOKUP", "identifier_x", None, "Observe candidate buckets: SVC-Hash hashes (x,0) and (x,1) to distinct buckets!"),
    ]
}


def init_lab_session():
    """Initializes session state for the interactive lab."""
    if "lab_sim" not in st.session_state:
        st.session_state["lab_sim"] = SvcHashTableSimulator(num_buckets=8)
        st.session_state["lab_chaining"] = ChainingTableSimulator(num_buckets=8)
        st.session_state["lab_cuckoo"] = PlainCuckooTableSimulator(capacity=16)
        st.session_state["lab_hopscotch"] = HopscotchTableSimulator(capacity=32)
        st.session_state["lab_log"] = []
        st.session_state["lab_last_result"] = None
        st.session_state["scenario_name"] = "3. Variable Shadowing & Unmasking"
        st.session_state["scenario_step_idx"] = 0


def reset_lab():
    """Resets all simulators and state."""
    st.session_state["lab_sim"] = SvcHashTableSimulator(num_buckets=8)
    st.session_state["lab_chaining"] = ChainingTableSimulator(num_buckets=8)
    st.session_state["lab_cuckoo"] = PlainCuckooTableSimulator(capacity=16)
    st.session_state["lab_hopscotch"] = HopscotchTableSimulator(capacity=32)
    st.session_state["lab_log"] = []
    st.session_state["lab_last_result"] = None
    st.session_state["scenario_step_idx"] = 0


def render_interactive_lab():
    init_lab_session()

    st.markdown("""
    <div class="research-card" style="border-left: 5px solid #3b82f6; margin-bottom: 14px;">
        <h2 style="margin: 0 0 6px 0;">🧪 Interactive Symbol Table Lab</h2>
        <p style="margin: 0; font-size: 14.5px; opacity: 0.9;">
            <strong>Live Compiler Demonstration:</strong> Execute compiler symbol-table operations 
            (<code>ENTER_SCOPE</code>, <code>EXIT_SCOPE</code>, <code>DECLARE</code>, <code>LOOKUP</code>) 
            and interactively inspect lexical scope trees, bucket slot occupancy, cuckoo kick chains, 
            shadowing resolution, and native C++ engine execution.
        </p>
    </div>
    <div class="research-callout" style="padding: 8px 14px; margin: 0 0 18px 0; font-size: 12.5px;">
        <strong>Architecture Distinction:</strong> The Python interactive simulator is an educational model designed for visualization of scope trees, slot migrations, and kick displacement chains. The compiled native C++ binary (<code>colliscope_bench.exe</code>) is the authoritative benchmark engine.
    </div>
    """, unsafe_allow_html=True)

    # Top Bar: Algorithm & Scenario Controls
    top_col1, top_col2 = st.columns([1, 1])

    with top_col1:
        algo_choice = st.selectbox(
            "Symbol Table Algorithm Architecture:",
            options=[
                "SVC-Hash (Scope-Versioned Cuckoo Hash) [PROPOSED]",
                "Separate Chaining [BASELINE]",
                "Plain Cuckoo Hashing [BASELINE]",
                "Hopscotch Hashing [BASELINE]"
            ],
            index=0,
            help="Choose between the proposed scope-virtualized cuckoo scheme and classic collision-resolution baselines."
        )

    with top_col2:
        selected_scenario = st.selectbox(
            "Prebuilt Educational Demonstration Scenario:",
            options=list(PREBUILT_SCENARIOS.keys()),
            index=2,
            help="Select a curated sequence of compiler operations demonstrating symbol-table phenomena."
        )
        if selected_scenario != st.session_state.get("scenario_name"):
            st.session_state["scenario_name"] = selected_scenario
            st.session_state["scenario_step_idx"] = 0

    st.markdown("---")

    # Scenario Step Player Controls
    scenario_steps = PREBUILT_SCENARIOS[st.session_state["scenario_name"]]
    curr_step_idx = st.session_state["scenario_step_idx"]
    total_steps = len(scenario_steps)

    play_col1, play_col2, play_col3, play_col4 = st.columns([2, 1, 1, 1])

    with play_col1:
        st.markdown(f"**Scenario Progress:** Step {curr_step_idx} of {total_steps}")
        if curr_step_idx < total_steps:
            next_op, next_arg, next_type, next_desc = scenario_steps[curr_step_idx]
            st.caption(f"**Next Step:** `{next_op} {next_arg or ''}` — *{next_desc}*")
        else:
            st.caption("✅ **Scenario Completed!** Click *Reset* or choose another scenario.")

    with play_col2:
        if st.button("▶ Step Forward", disabled=(curr_step_idx >= total_steps), use_container_width=True):
            op, arg, t_id, desc = scenario_steps[curr_step_idx]
            execute_lab_op(op, arg, t_id or 1, desc)
            st.session_state["scenario_step_idx"] += 1
            st.rerun()

    with play_col3:
        if st.button("⏩ Run All", disabled=(curr_step_idx >= total_steps), use_container_width=True):
            while st.session_state["scenario_step_idx"] < total_steps:
                op, arg, t_id, desc = scenario_steps[st.session_state["scenario_step_idx"]]
                execute_lab_op(op, arg, t_id or 1, desc)
                st.session_state["scenario_step_idx"] += 1
            st.rerun()

    with play_col4:
        if st.button("⏮ Reset Table", use_container_width=True):
            reset_lab()
            st.rerun()

    st.markdown("---")

    # Manual Operation Controls
    with st.expander("🛠️ Manual Operation Console (Execute Custom Operations)", expanded=False):
        m_col1, m_col2, m_col3, m_col4 = st.columns([2, 1.5, 1.5, 1])
        with m_col1:
            m_op = st.selectbox("Operation:", ["DECLARE", "LOOKUP", "ENTER_SCOPE", "EXIT_SCOPE"])
        with m_col2:
            m_id = st.text_input("Identifier / Scope Name:", value="var_x", help="Identifier string to declare or lookup.")
        with m_col3:
            m_type_name = st.selectbox("Type (for DECLARE):", ["INT", "FLOAT", "STRING", "BOOL", "PTR"])
            type_map = {"INT": 1, "FLOAT": 2, "STRING": 3, "BOOL": 4, "PTR": 5}
        with m_col4:
            st.write("")
            st.write("")
            if st.button("⚡ Execute", use_container_width=True):
                if m_op == "ENTER_SCOPE":
                    execute_lab_op("ENTER_SCOPE", m_id or None, None, f"Entered {m_id or 'new scope'}")
                elif m_op == "EXIT_SCOPE":
                    execute_lab_op("EXIT_SCOPE", None, None, "Exited current scope")
                elif m_op == "DECLARE":
                    execute_lab_op("DECLARE", m_id, type_map[m_type_name], f"Declared '{m_id}'")
                elif m_op == "LOOKUP":
                    execute_lab_op("LOOKUP", m_id, None, f"Looked up '{m_id}'")
                st.rerun()

    # Main Visual Layout: Left = Scope Tree & Details, Right = Table State
    sim: SvcHashTableSimulator = st.session_state["lab_sim"]
    v_col1, v_col2 = st.columns([1, 2])

    with v_col1:
        st.subheader("🌲 Lexical Scope Hierarchy")
        st.caption(f"**Current Scope:** `Scope {sim.current_scope_id}` | **Active Scopes:** `{sum(1 for s in sim.scope_registry.values() if s.active)}`")

        # Visual Scope Tree
        scope_tree_html = render_scope_tree_html(sim)
        st.markdown(scope_tree_html, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Last Operation Inspector
        last_res = st.session_state.get("lab_last_result")
        if last_res:
            st.subheader("🔍 Last Operation Inspector")
            render_last_operation_inspector(last_res)

    with v_col2:
        st.subheader("📊 Live Symbol Table State")

        if "SVC-Hash" in algo_choice:
            st.caption(
                f"**Architecture:** Virtualized Multi-Scope Cuckoo Table | **Buckets:** `{sim.num_buckets}` (4 slots/bucket) | "
                f"**Active Elements:** `{sim.occupied_count - sim.tombstone_count}` | **Tombstones:** `{sim.tombstone_count}` | "
                f"**Stash Entries:** `{sim.stash_count}` | **Relocation Kicks:** `{sim.kick_count}`"
            )
            render_svc_table_view(sim)
        elif "Separate Chaining" in algo_choice:
            chain_sim: ChainingTableSimulator = st.session_state["lab_chaining"]
            st.caption(
                f"**Architecture:** Separate Chaining Baseline | **Buckets:** `{chain_sim.num_buckets}` | "
                f"**Elements:** `{chain_sim.total_elements}` | **Collisions:** `{chain_sim.collision_count}`"
            )
            render_chaining_table_view(chain_sim)
        elif "Plain Cuckoo" in algo_choice:
            cuckoo_sim: PlainCuckooTableSimulator = st.session_state["lab_cuckoo"]
            st.caption(
                f"**Architecture:** Plain Cuckoo Hashing (Key-Only Hashing) | **Slots:** `{cuckoo_sim.capacity}` | "
                f"**Elements:** `{cuckoo_sim.total_elements}` | **Kicks:** `{cuckoo_sim.kick_count}` | **Rehashes:** `{cuckoo_sim.rehash_count}`"
            )
            render_cuckoo_table_view(cuckoo_sim)
        elif "Hopscotch" in algo_choice:
            hop_sim: HopscotchTableSimulator = st.session_state["lab_hopscotch"]
            st.caption(
                f"**Architecture:** Hopscotch Hashing (Neighborhood H=32) | **Slots:** `{hop_sim.capacity}` | "
                f"**Elements:** `{hop_sim.total_elements}` | **Neighborhood Shifts:** `{hop_sim.neighbourhood_movements}`"
            )
            render_hopscotch_table_view(hop_sim)

    st.markdown("---")

    # Bottom Area: Operation Chronological Log & C++ Execution
    log_col1, log_col2 = st.columns([1.6, 1])

    with log_col1:
        st.subheader("📜 Chronological Operation Log")
        log_entries = st.session_state.get("lab_log", [])
        if log_entries:
            df_log = pd.DataFrame(log_entries)
            st.dataframe(
                df_log[["Step", "Operation", "Target", "Scope", "Status", "Details"]],
                use_container_width=True,
                height=260
            )
        else:
            st.info("No operations executed yet. Click **▶ Step Forward** or execute a manual operation.")

    with log_col2:
        st.subheader("⚙️ Real C++ Engine Verification")
        st.caption("Verify this session against the compiled native C++ `colliscope_bench` binary.")

        trace_text = generate_session_trace(st.session_state.get("lab_log", []))

        with st.expander("Generated Trace File (`.trace`)", expanded=False):
            st.code(trace_text or "# Empty trace\n", language="text")

        if st.button("🚀 Verify in Native C++ Engine", use_container_width=True, disabled=not log_entries):
            with st.spinner("Invoking compiled native C++ benchmark binary..."):
                res = execute_trace_in_cpp_engine(trace_text)
                if res.get("available"):
                    if res.get("returncode") == 0:
                        st.success("✅ **Native C++ Execution Succeeded!**")
                        st.code(res.get("stdout", ""), language="text")
                    else:
                        st.error(f"Execution returned error code {res.get('returncode')}")
                        st.code(res.get("stderr", "") or res.get("stdout", ""))
                else:
                    st.warning(f"⚠️ Native C++ binary unavailable: {res.get('error')}. The educational simulator continues functioning independently.")


def execute_lab_op(op: str, identifier: Optional[str], type_id: Optional[int], desc: str):
    """Dispatches operation to all simulators and records event log."""
    sim: SvcHashTableSimulator = st.session_state["lab_sim"]
    chain_sim: ChainingTableSimulator = st.session_state["lab_chaining"]
    cuckoo_sim: PlainCuckooTableSimulator = st.session_state["lab_cuckoo"]
    hop_sim: HopscotchTableSimulator = st.session_state["lab_hopscotch"]

    step_num = len(st.session_state["lab_log"]) + 1
    log_record = {
        "Step": step_num,
        "Operation": op,
        "Target": identifier or "-",
        "Scope": sim.current_scope_id,
        "Status": "Executed",
        "Details": desc
    }

    if op == "ENTER_SCOPE":
        ok, msg, new_id = sim.enter_scope(identifier or "")
        log_record["Status"] = "Scope Entered"
        log_record["Details"] = msg
        st.session_state["lab_last_result"] = {"type": "enter_scope", "ok": ok, "msg": msg, "scope_id": new_id}

    elif op == "EXIT_SCOPE":
        ok, msg, ex_id, tombs = sim.exit_scope()
        log_record["Status"] = "Scope Exited"
        log_record["Details"] = msg
        st.session_state["lab_last_result"] = {"type": "exit_scope", "ok": ok, "msg": msg, "exited_id": ex_id, "tombstones": tombs}

    elif op == "DECLARE":
        val = SymbolValue(type_id=type_id or 1, line_declared=step_num * 10)
        res_svc = sim.insert(identifier, val)
        chain_sim.insert(identifier, val, sim.current_scope_id)
        cuckoo_sim.insert(identifier, val, sim.current_scope_id)
        hop_sim.insert(identifier, val, sim.current_scope_id)

        log_record["Status"] = res_svc["status"].replace("_", " ").title()
        log_record["Details"] = res_svc["message"]
        st.session_state["lab_last_result"] = {"type": "declare", "res": res_svc}

    elif op == "LOOKUP":
        res_lookup = sim.lookup(identifier)
        log_record["Status"] = "Hit" if res_lookup["found"] else "Miss"
        log_record["Details"] = res_lookup["message"]
        st.session_state["lab_last_result"] = {"type": "lookup", "res": res_lookup}

    st.session_state["lab_log"].append(log_record)


def render_scope_tree_html(sim: SvcHashTableSimulator) -> str:
    """Generates accessible HTML visualizing active and inactive lexical scopes."""
    items = []
    for s_id, sc in sim.scope_registry.items():
        is_current = (s_id == sim.current_scope_id)
        status_badge = "🟢 CURRENT" if is_current else ("Active" if sc.active else "🔴 Exited")
        depth = 0
        curr = s_id
        while curr != 0 and curr in sim.scope_registry:
            p = sim.scope_registry[curr].parent_id
            if p == curr:
                break
            depth += 1
            curr = p

        indent = "&nbsp;&nbsp;&nbsp;&nbsp;" * depth
        border_style = "border-left: 4px solid #3b82f6; padding-left: 8px;" if is_current else ""
        opacity = "1.0" if sc.active else "0.5"

        items.append(
            f"<div style='margin-bottom: 6px; font-size: 13.5px; opacity: {opacity}; {border_style}'>"
            f"{indent}<strong>Scope {s_id}</strong>: {sc.name} "
            f"<span style='font-size: 11px; padding: 2px 6px; border-radius: 4px; background: rgba(128,128,128,0.2);'>{status_badge}</span>"
            f"</div>"
        )

    return f"<div class='research-card' style='padding: 12px;'>{''.join(items)}</div>"


def render_svc_table_view(sim: SvcHashTableSimulator):
    """Renders the virtualized bucket array and stash of SVC-Hash."""
    tab1, tab2 = st.tabs(["Candidate Buckets (Slots 0..3)", "Overflow Stash (8 Slots)"])

    with tab1:
        cols = st.columns(min(4, sim.num_buckets))
        for b_idx in range(sim.num_buckets):
            c_idx = b_idx % len(cols)
            with cols[c_idx]:
                st.markdown(f"**Bucket {b_idx}**")
                bucket = sim.buckets[b_idx]
                for s_idx, slot in enumerate(bucket):
                    if not slot.occupied:
                        st.markdown(
                            f"<div style='border: 1px dashed rgba(128,128,128,0.3); border-radius: 4px; padding: 4px 8px; margin-bottom: 4px; font-size: 11.5px; opacity: 0.6;'>"
                            f"Slot {s_idx}: <em>Empty</em></div>",
                            unsafe_allow_html=True
                        )
                    elif slot.tombstoned:
                        st.markdown(
                            f"<div style='border: 1px solid rgba(239,68,68,0.4); background: rgba(239,68,68,0.1); border-radius: 4px; padding: 4px 8px; margin-bottom: 4px; font-size: 11.5px;'>"
                            f"Slot {s_idx}: <del><strong>{slot.key}</strong> @ Scope {slot.scope_id}</del> <span style='font-size: 10px; color: #ef4444;'>(Tombstone)</span></div>",
                            unsafe_allow_html=True
                        )
                    else:
                        b1, b2 = sim.compute_candidate_buckets(slot.key, slot.scope_id)
                        st.markdown(
                            f"<div style='border: 1px solid rgba(34,197,94,0.4); background: rgba(34,197,94,0.1); border-radius: 4px; padding: 4px 8px; margin-bottom: 4px; font-size: 11.5px;'>"
                            f"Slot {s_idx}: <strong>{slot.key}</strong> @ S{slot.scope_id} ({slot.value.type_name()})<br>"
                            f"<span style='font-size: 10px; opacity: 0.8;'>Candidates: [{b1}, {b2}]</span></div>",
                            unsafe_allow_html=True
                        )

    with tab2:
        st.markdown("**Stash Array** *(Absorbs displacements when recursive kick depth limit is reached)*")
        s_cols = st.columns(4)
        for i, slot in enumerate(sim.stash):
            sc = s_cols[i % 4]
            with sc:
                if not slot.occupied:
                    st.markdown(f"<div style='border: 1px dashed rgba(128,128,128,0.3); padding: 6px; font-size: 11.5px;'>Stash [{i}]: <em>Empty</em></div>", unsafe_allow_html=True)
                elif slot.tombstoned:
                    st.markdown(f"<div style='border: 1px solid rgba(239,68,68,0.3); background: rgba(239,68,68,0.1); padding: 6px; font-size: 11.5px;'><del>{slot.key} @ S{slot.scope_id}</del></div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div style='border: 1px solid rgba(34,197,94,0.3); background: rgba(34,197,94,0.1); padding: 6px; font-size: 11.5px;'><strong>{slot.key}</strong> @ S{slot.scope_id}</div>", unsafe_allow_html=True)


def render_chaining_table_view(sim: ChainingTableSimulator):
    """Renders buckets with linked lists for Separate Chaining."""
    cols = st.columns(min(4, sim.num_buckets))
    for b_idx in range(sim.num_buckets):
        with cols[b_idx % len(cols)]:
            st.markdown(f"**Bucket {b_idx}**")
            chain = sim.buckets[b_idx]
            if not chain:
                st.markdown("<div style='font-size: 11.5px; opacity: 0.5;'>[ Empty List ]</div>", unsafe_allow_html=True)
            else:
                for node in chain:
                    st.markdown(
                        f"<div style='border: 1px solid rgba(59,130,246,0.3); background: rgba(59,130,246,0.1); border-radius: 4px; padding: 4px; margin-bottom: 3px; font-size: 11.5px;'>"
                        f"• <strong>{node['key']}</strong> @ Scope {node['scope_id']} ({node['value'].type_name()})</div>",
                        unsafe_allow_html=True
                    )


def render_cuckoo_table_view(sim: PlainCuckooTableSimulator):
    """Renders slots for Plain Cuckoo hashing."""
    cols = st.columns(4)
    for i, slot in enumerate(sim.slots):
        with cols[i % 4]:
            if slot is None:
                st.markdown(f"<div style='border: 1px dashed rgba(128,128,128,0.3); padding: 4px; font-size: 11px;'>Slot {i}: <em>Empty</em></div>", unsafe_allow_html=True)
            else:
                p1, p2 = sim.compute_positions(slot["key"])
                st.markdown(
                    f"<div style='border: 1px solid rgba(249,115,22,0.4); background: rgba(249,115,22,0.1); padding: 4px; font-size: 11px;'>"
                    f"Slot {i}: <strong>{slot['key']}</strong><br><span style='font-size: 9.5px;'>Pos: [{p1}, {p2}]</span></div>",
                    unsafe_allow_html=True
                )


def render_hopscotch_table_view(sim: HopscotchTableSimulator):
    """Renders slots and neighborhood bitmasks for Hopscotch hashing."""
    cols = st.columns(4)
    for i, slot in enumerate(sim.slots):
        with cols[i % 4]:
            mask = sim.hop_info[i]
            mask_str = f"{mask:04b}"[-4:]
            if slot is None:
                st.markdown(f"<div style='border: 1px dashed rgba(128,128,128,0.3); padding: 4px; font-size: 11px;'>Slot {i}: <em>Empty</em><br><span style='font-size: 9px;'>Hop: {mask_str}</span></div>", unsafe_allow_html=True)
            else:
                st.markdown(
                    f"<div style='border: 1px solid rgba(168,85,247,0.4); background: rgba(168,85,247,0.1); padding: 4px; font-size: 11px;'>"
                    f"Slot {i}: <strong>{slot['key']}</strong><br><span style='font-size: 9px;'>Hop: {mask_str}</span></div>",
                    unsafe_allow_html=True
                )


def render_last_operation_inspector(res: Dict[str, Any]):
    """Renders step-by-step resolution path or kick path for the last operation."""
    op_type = res.get("type")

    if op_type == "lookup":
        r = res["res"]
        if r["found"]:
            st.success(f"🎯 **HIT:** `{r['key']}` resolved in **Scope {r['resolved_scope']}** ({r['location']})")
            if r.get("is_shadowed"):
                st.info(f"🛡️ **Shadowing Active:** Inner declaration in Scope {r['resolved_scope']} shadows any outer declarations.")
        else:
            st.error(f"❌ **MISS:** `{r['key']}` not found along active scope path.")

        # Step by step path
        st.markdown("**Resolution Path:**")
        for step in r.get("path", []):
            st.markdown(f"• **Scope {step['scope_id']}** (`b1={step.get('b1')}`, `b2={step.get('b2')}`) $\\rightarrow$ {'**FOUND**' if step.get('found') else 'Not present'}")

    elif op_type == "declare":
        r = res["res"]
        if r["success"]:
            st.success(f"✅ **DECLARED:** `{r['key']}` in **Scope {r['scope_id']}** ({r['message']})")
            if r.get("kicks"):
                st.markdown("**Cuckoo Relocation Kicks:**")
                for k in r["kicks"]:
                    st.markdown(f"• Victim `{k['displaced_key']}` from Bucket {k['from_bucket']}[{k['from_slot']}] relocated $\\rightarrow$ Bucket {k['to_bucket']}")
        else:
            st.error(f"⛔ **DECLARATION FAILED:** {r['message']}")

    elif op_type == "exit_scope":
        st.warning(f"🚪 **SCOPE EXITED:** Scope {res.get('exited_id')} closed. {res.get('tombstones')} entry/entries marked tombstoned.")

    elif op_type == "enter_scope":
        st.info(f"📥 **SCOPE ENTERED:** Scope {res.get('scope_id')} active under parent.")


def generate_session_trace(log: List[Dict[str, Any]]) -> str:
    """Translates the interactive lab session into standard ColliScope trace syntax."""
    lines = []
    scope_parents = {0: 0}
    current_scope = 0

    lines.append("ENTER_SCOPE 0 0")

    for entry in log:
        op = entry["Operation"]
        target = entry["Target"]
        s_id = entry["Scope"]

        if op == "ENTER_SCOPE":
            lines.append(f"ENTER_SCOPE {entry.get('new_scope', s_id + 1)} {s_id}")
        elif op == "EXIT_SCOPE":
            lines.append(f"EXIT_SCOPE {s_id}")
        elif op == "DECLARE":
            lines.append(f"DECLARE {target} 1 {s_id}")
        elif op == "LOOKUP":
            lines.append(f"REFERENCE {target} {s_id}")

    return "\n".join(lines) + "\n"
