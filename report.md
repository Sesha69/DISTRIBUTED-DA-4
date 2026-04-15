# Distributed Deadlock Detection Using Wait-For Graphs

## Aim

To build and run a discrete-event simulation of a distributed deadlock detection algorithm using the Wait-For Graph model with SimPy and Streamlit.

## Objective

- Simulate `N` processes distributed across multiple sites
- Model contention for shared resources
- Maintain a local wait-for graph at each site
- Detect distributed deadlocks using a probe-based edge-chasing algorithm

## Technologies Used

- Python
- SimPy
- Streamlit

## System Design

### Distributed Environment

- Processes are distributed across multiple sites
- Resources are also distributed across sites
- Each site stores its own local WFG

### Wait-For Graph

If process `Pi` waits for a resource held by process `Pj`, then an edge `Pi -> Pj` is added to the local WFG.

### Probe-Based Detection

When a process becomes blocked, it initiates a probe. The probe is forwarded along WFG edges. If the probe returns to the initiator, a cycle exists and the system reports a distributed deadlock.

## Implementation Overview

The implementation contains two major parts:

1. `deadlock_sim/simulator.py`
   This file contains the SimPy-based simulation engine, resource model, event handling, local WFG maintenance, and edge-chasing detection logic.

2. `app.py`
   This file provides a Streamlit interface to run the simulation and display process plans, resource states, WFG edges, probe traces, and detected deadlocks.

## Sample Deadlock Cycle

A distributed deadlock may look like:

```text
P1 -> P2 -> P3 -> P1
```

This means:

- `P1` is waiting on a resource held by `P2`
- `P2` is waiting on a resource held by `P3`
- `P3` is waiting on a resource held by `P1`

Since every process in the cycle is waiting indefinitely, the system is deadlocked.

## Output

The simulator displays:

- process request plans
- current resource ownership and wait queues
- local wait-for graphs for each site
- global WFG edges
- event logs
- probe traces
- detected deadlock cycles

## Conclusion

The project successfully demonstrates distributed deadlock detection using local wait-for graphs and an edge-chasing algorithm. The use of SimPy enables event-driven simulation, while Streamlit provides a simple interface for experimentation and demonstration.

