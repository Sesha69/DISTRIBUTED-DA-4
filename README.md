# Distributed Deadlock Detection Simulator

This project implements a discrete-event simulation of a **Distributed Deadlock Detection Algorithm** using:

- **SimPy** for event scheduling
- **Streamlit** for the interactive UI
- A **Wait-For Graph (WFG)** model per site
- An **edge-chasing / probe-based algorithm** to detect distributed cycles

## Problem Statement

The simulator models `N` distributed processes competing for shared resources across multiple sites. Each site maintains a local wait-for graph. When a process is blocked by another process, a wait-for edge is added. Probe messages are then forwarded along the WFG. If a probe returns to its initiator, a deadlock cycle has been detected.

## Features

- Configurable number of processes, sites, and resources
- Local WFG maintenance at each site
- Distributed edge-chasing deadlock detection
- Event log showing resource requests, allocations, blocking, releases, and detection
- Probe trace showing how the detection message propagates
- Deadlock demo mode that intentionally creates a cross-site cycle

## Project Structure

```text
DIST DA-4/
├── app.py
├── README.md
├── requirements.txt
├── report.md
└── deadlock_sim/
    ├── __init__.py
    └── simulator.py
```

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run the Streamlit App

```bash
streamlit run app.py
```

The UI lets you:

- choose the number of processes `N`
- choose the number of sites and resources per site
- toggle a deterministic deadlock demonstration
- inspect process plans, local WFGs, global edges, event logs, and probe traces

## Core Logic

### 1. Resource Competition

Each process follows a plan of resource requests. If the requested resource is free, it is allocated immediately. Otherwise, the process is blocked and added to the resource wait queue.

### 2. Local Wait-For Graph

When process `Pi` is blocked by a resource held by `Pj`, the site of `Pi` records the edge:

```text
Pi -> Pj
```

### 3. Edge-Chasing Detection

When a process is blocked, the simulator starts a probe with:

```text
(initiator, sender, receiver)
```

The probe is forwarded through outgoing WFG edges. If the receiver eventually becomes the initiator again, a distributed cycle exists.

### 4. Deadlock Example

The demo mode creates a cycle such as:

```text
P1 -> P2 -> P3 -> P1
```

This can span multiple sites, which makes it a **distributed deadlock** rather than a purely local one.

## Suggested Walkthrough Recording

For the screen-recorded walkthrough, cover:

1. `deadlock_sim/simulator.py`
2. How local WFG edges are added
3. How probe messages are forwarded
4. How the Streamlit app displays results
5. A live run showing the deadlock detection output

## GitHub Submission Steps

```bash
git init
git add .
git commit -m "Add distributed deadlock detection simulator"
git branch -M main
git remote add origin <your-repo-url>
git push -u origin main
```

After pushing, paste the GitHub repository URL in the required submission field.

## PDF Upload

Convert `report.md` to PDF and upload that PDF to VTOP.

If you have Pandoc installed:

```bash
pandoc report.md -o report.pdf
```

