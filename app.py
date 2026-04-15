from __future__ import annotations

import pandas as pd
import streamlit as st

from deadlock_sim.simulator import DistributedDeadlockSimulator


st.set_page_config(
    page_title="Distributed Deadlock Detection Simulator",
    page_icon="🔗",
    layout="wide",
)


def format_cycle(cycle: list[str]) -> str:
    return " -> ".join(cycle) + f" -> {cycle[0]}"


st.title("Distributed Deadlock Detection with Wait-For Graphs")
st.caption("SimPy + Streamlit simulation of distributed deadlock detection using edge-chasing probes.")

with st.sidebar:
    st.header("Simulation Controls")
    num_processes = st.slider("Processes (N)", min_value=3, max_value=12, value=6)
    num_sites = st.slider("Sites", min_value=2, max_value=6, value=3)
    resources_per_site = st.slider("Resources per site", min_value=1, max_value=4, value=2)
    max_time = st.slider("Simulation time", min_value=10, max_value=80, value=40)
    seed = st.number_input("Random seed", min_value=1, max_value=9999, value=7)
    force_deadlock = st.toggle("Force a distributed deadlock demo", value=True)
    run_clicked = st.button("Run Simulation", type="primary", use_container_width=True)

if "result" not in st.session_state:
    st.session_state.result = None

if run_clicked or st.session_state.result is None:
    simulator = DistributedDeadlockSimulator(
        num_processes=num_processes,
        num_sites=num_sites,
        resources_per_site=resources_per_site,
        seed=int(seed),
        force_deadlock=force_deadlock,
        max_time=max_time,
    )
    st.session_state.result = simulator.run()

result = st.session_state.result

plans_df = pd.DataFrame(
    [{"process": process, "request_plan": " -> ".join(plan)} for process, plan in result["plans"].items()]
)
resources_df = pd.DataFrame(result["resources"])
events_df = pd.DataFrame(result["events"])
probes_df = pd.DataFrame(result["probes"])
edges_df = pd.DataFrame(result["global_edges"], columns=["site", "from", "to"])

deadlock_count = len(result["deadlocks"])
cross_site_cycles = sum(1 for deadlock in result["deadlocks"] if len(deadlock["sites"]) > 1)

metric_columns = st.columns(4)
metric_columns[0].metric("Processes", len(result["plans"]))
metric_columns[1].metric("Sites", num_sites)
metric_columns[2].metric("Deadlocks Found", deadlock_count)
metric_columns[3].metric("Cross-Site Cycles", cross_site_cycles)

summary_col, cycle_col = st.columns([1.2, 1])

with summary_col:
    st.subheader("Process Request Plans")
    st.dataframe(plans_df, use_container_width=True, hide_index=True)

    st.subheader("Resource Allocation Snapshot")
    st.dataframe(resources_df, use_container_width=True, hide_index=True)

with cycle_col:
    st.subheader("Detection Summary")
    if result["deadlocks"]:
        for index, deadlock in enumerate(result["deadlocks"], start=1):
            st.success(
                f"Cycle {index}: {format_cycle(deadlock['cycle'])} | Sites: {', '.join(deadlock['sites'])}"
            )
    else:
        st.info("No deadlock cycle was detected in this run.")

    st.subheader("Local Wait-For Graphs")
    for site_id, graph in result["local_wfgs"].items():
        if not graph:
            st.write(f"{site_id}: No waiting edges")
            continue
        graph_lines = [f"{node} -> {', '.join(targets)}" for node, targets in graph.items()]
        st.code("\n".join([f"{site_id}"] + graph_lines), language="text")

st.subheader("Global Wait-For Graph Edges")
if edges_df.empty:
    st.info("No wait-for edges were generated.")
else:
    st.dataframe(edges_df, use_container_width=True, hide_index=True)

event_tab, probe_tab, explanation_tab = st.tabs(["Event Log", "Probe Trace", "How It Works"])

with event_tab:
    st.dataframe(events_df, use_container_width=True, hide_index=True)

with probe_tab:
    if probes_df.empty:
        st.info("No probe messages were needed in this run.")
    else:
        st.dataframe(probes_df, use_container_width=True, hide_index=True)

with explanation_tab:
    st.markdown(
        """
        ### Algorithm Flow
        1. Each site maintains a **local wait-for graph (WFG)** with edges `Pi -> Pj` when `Pi` is blocked by a resource held by `Pj`.
        2. When a process becomes blocked, the simulator starts an **edge-chasing probe**.
        3. A probe is forwarded along outgoing WFG edges across sites.
        4. If the probe comes back to its initiator, a **distributed cycle** exists, which means a deadlock has been detected.

        ### Why This Is Distributed
        - Processes are mapped to multiple sites.
        - Resources are hosted by different sites.
        - A waiting edge can point from a process at one site to a holder at another site.
        - Detection therefore spans multiple local WFGs instead of one centralized graph.
        """
    )

