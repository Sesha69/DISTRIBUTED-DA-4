from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import random
from typing import Dict, List, Optional, Set, Tuple

import simpy


@dataclass
class Resource:
    resource_id: str
    site_id: str
    holder: Optional[str] = None
    wait_queue: List[str] = field(default_factory=list)


@dataclass
class ProbeMessage:
    initiator: str
    sender: str
    receiver: str
    path: List[str]


class DistributedDeadlockSimulator:
    """Simulates processes competing for distributed resources with local WFGs."""

    def __init__(
        self,
        num_processes: int = 6,
        num_sites: int = 3,
        resources_per_site: int = 2,
        seed: int = 7,
        force_deadlock: bool = True,
        max_time: int = 40,
    ) -> None:
        self.env = simpy.Environment()
        self.num_processes = num_processes
        self.num_sites = num_sites
        self.resources_per_site = resources_per_site
        self.seed = seed
        self.force_deadlock = force_deadlock
        self.max_time = max_time
        self.random = random.Random(seed)

        self.process_sites: Dict[str, str] = {}
        self.resources: Dict[str, Resource] = {}
        self.held_resources: Dict[str, Set[str]] = defaultdict(set)
        self.waiting_for: Dict[str, Optional[str]] = {}
        self.resource_waiters: Dict[str, Set[str]] = defaultdict(set)
        self.local_wfgs: Dict[str, Dict[str, Set[str]]] = {
            f"S{i}": defaultdict(set) for i in range(1, num_sites + 1)
        }

        self.event_log: List[Dict[str, object]] = []
        self.probe_log: List[Dict[str, object]] = []
        self.detected_cycles: List[Dict[str, object]] = []
        self.completed_processes: Set[str] = set()
        self.detected_cycle_keys: Set[Tuple[str, ...]] = set()

        self._create_sites_and_resources()
        self._assign_processes_to_sites()

    def _create_sites_and_resources(self) -> None:
        for site_index in range(1, self.num_sites + 1):
            site_id = f"S{site_index}"
            for resource_index in range(1, self.resources_per_site + 1):
                resource_id = f"R{site_index}.{resource_index}"
                self.resources[resource_id] = Resource(resource_id=resource_id, site_id=site_id)

    def _assign_processes_to_sites(self) -> None:
        for process_index in range(1, self.num_processes + 1):
            process_id = f"P{process_index}"
            site_id = f"S{((process_index - 1) % self.num_sites) + 1}"
            self.process_sites[process_id] = site_id
            self.waiting_for[process_id] = None

    def log_event(self, event_type: str, message: str, **details: object) -> None:
        self.event_log.append(
            {
                "time": round(self.env.now, 2),
                "event": event_type,
                "message": message,
                **details,
            }
        )

    def _add_wfg_edge(self, waiting_process: str, holder_process: str) -> None:
        site_id = self.process_sites[waiting_process]
        self.local_wfgs[site_id][waiting_process].add(holder_process)
        self.log_event(
            "WFG_EDGE_ADDED",
            f"{waiting_process} waits for {holder_process}",
            site=site_id,
            waiting_process=waiting_process,
            holder_process=holder_process,
        )

    def _remove_wfg_edges_for(self, waiting_process: str) -> None:
        site_id = self.process_sites[waiting_process]
        if waiting_process in self.local_wfgs[site_id]:
            del self.local_wfgs[site_id][waiting_process]
        for neighbors in self.local_wfgs[site_id].values():
            neighbors.discard(waiting_process)

    def _resource_holders_blocking(self, resource_id: str) -> List[str]:
        resource = self.resources[resource_id]
        return [resource.holder] if resource.holder else []

    def request_resource(self, process_id: str, resource_id: str) -> bool:
        resource = self.resources[resource_id]
        self.log_event(
            "REQUEST",
            f"{process_id} requests {resource_id}",
            process=process_id,
            resource=resource_id,
            site=resource.site_id,
        )

        if resource.holder is None:
            resource.holder = process_id
            self.held_resources[process_id].add(resource_id)
            self.log_event(
                "ALLOCATED",
                f"{resource_id} allocated to {process_id}",
                process=process_id,
                resource=resource_id,
                site=resource.site_id,
            )
            return True

        if resource.holder == process_id:
            return True

        if process_id not in resource.wait_queue:
            resource.wait_queue.append(process_id)
        self.resource_waiters[resource_id].add(process_id)
        self.waiting_for[process_id] = resource_id
        for holder in self._resource_holders_blocking(resource_id):
            self._add_wfg_edge(process_id, holder)
        self.log_event(
            "BLOCKED",
            f"{process_id} blocked on {resource_id} held by {resource.holder}",
            process=process_id,
            resource=resource_id,
            holder=resource.holder,
            site=resource.site_id,
        )
        self.initiate_probe(process_id)
        return False

    def release_resource(self, process_id: str, resource_id: str) -> None:
        resource = self.resources[resource_id]
        if resource.holder != process_id:
            return

        resource.holder = None
        self.held_resources[process_id].discard(resource_id)
        self.log_event(
            "RELEASE",
            f"{process_id} released {resource_id}",
            process=process_id,
            resource=resource_id,
            site=resource.site_id,
        )

        if resource.wait_queue:
            next_process = resource.wait_queue.pop(0)
            self.resource_waiters[resource_id].discard(next_process)
            self.waiting_for[next_process] = None
            self._remove_wfg_edges_for(next_process)
            resource.holder = next_process
            self.held_resources[next_process].add(resource_id)
            self.log_event(
                "REALLOCATED",
                f"{resource_id} reallocated to {next_process}",
                process=next_process,
                resource=resource_id,
                site=resource.site_id,
            )

    def release_all_resources(self, process_id: str) -> None:
        for resource_id in list(self.held_resources[process_id]):
            self.release_resource(process_id, resource_id)

    def _canonical_cycle(self, cycle_nodes: List[str]) -> Tuple[str, ...]:
        if not cycle_nodes:
            return tuple()
        variants = []
        for index in range(len(cycle_nodes)):
            rotated = cycle_nodes[index:] + cycle_nodes[:index]
            variants.append(tuple(rotated))
        return min(variants)

    def initiate_probe(self, initiator: str) -> None:
        neighbors = list(self.local_wfgs[self.process_sites[initiator]].get(initiator, set()))
        for neighbor in neighbors:
            self.forward_probe(ProbeMessage(initiator=initiator, sender=initiator, receiver=neighbor, path=[initiator]))

    def forward_probe(self, probe: ProbeMessage) -> None:
        current_path = probe.path + [probe.receiver]
        self.probe_log.append(
            {
                "time": round(self.env.now, 2),
                "initiator": probe.initiator,
                "sender": probe.sender,
                "receiver": probe.receiver,
                "path": " -> ".join(current_path),
            }
        )

        if probe.receiver == probe.initiator and len(current_path) > 2:
            cycle_nodes = current_path[:-1]
            canonical = self._canonical_cycle(cycle_nodes)
            if canonical not in self.detected_cycle_keys:
                self.detected_cycle_keys.add(canonical)
                cycle_sites = sorted({self.process_sites[process] for process in cycle_nodes})
                cycle_record = {
                    "time": round(self.env.now, 2),
                    "initiator": probe.initiator,
                    "cycle": cycle_nodes,
                    "sites": cycle_sites,
                }
                self.detected_cycles.append(cycle_record)
                self.log_event(
                    "DEADLOCK_DETECTED",
                    f"Distributed deadlock detected: {' -> '.join(cycle_nodes)} -> {cycle_nodes[0]}",
                    initiator=probe.initiator,
                    cycle=cycle_nodes,
                    sites=cycle_sites,
                )
            return

        receiver_site = self.process_sites[probe.receiver]
        for neighbor in sorted(self.local_wfgs[receiver_site].get(probe.receiver, set())):
            if neighbor in current_path and neighbor != probe.initiator:
                continue
            next_probe = ProbeMessage(
                initiator=probe.initiator,
                sender=probe.receiver,
                receiver=neighbor,
                path=current_path,
            )
            self.forward_probe(next_probe)

    def process_lifecycle(self, process_id: str, plan: List[str]):
        if not plan:
            return

        yield self.env.timeout(self.random.uniform(0.2, 1.2))
        first_resource = plan[0]
        self.request_resource(process_id, first_resource)
        yield self.env.timeout(self.random.uniform(0.5, 1.0))

        for resource_id in plan[1:]:
            acquired = self.request_resource(process_id, resource_id)
            while not acquired:
                yield self.env.timeout(1)
                # Stay blocked until the requested resource is assigned.
                acquired = self.waiting_for[process_id] is None and resource_id in self.held_resources[process_id]
            yield self.env.timeout(self.random.uniform(0.5, 1.0))

        should_release = (not self.force_deadlock) or len(plan) == 1
        if should_release:
            yield self.env.timeout(self.random.uniform(1.0, 2.0))
            self.release_all_resources(process_id)
            self.completed_processes.add(process_id)
            self.log_event("COMPLETE", f"{process_id} completed execution", process=process_id)

    def _deadlock_demo_plans(self) -> Dict[str, List[str]]:
        if self.num_processes < 3 or self.num_sites < 3:
            return self._random_plans()

        plans: Dict[str, List[str]] = {
            "P1": ["R1.1", "R2.1"],
            "P2": ["R2.1", "R3.1"],
            "P3": ["R3.1", "R1.1"],
        }

        filler_resources = [
            resource_id
            for resource_id in sorted(self.resources.keys())
            if resource_id not in {"R1.1", "R2.1", "R3.1"}
        ]
        for process_index in range(4, self.num_processes + 1):
            process_id = f"P{process_index}"
            if filler_resources:
                resource_id = filler_resources[(process_index - 4) % len(filler_resources)]
                plans[process_id] = [resource_id]
            else:
                plans[process_id] = []
        return plans

    def _random_plans(self) -> Dict[str, List[str]]:
        resources = list(self.resources.keys())
        plans: Dict[str, List[str]] = {}
        for process_index in range(1, self.num_processes + 1):
            process_id = f"P{process_index}"
            picks = self.random.sample(resources, k=min(2, len(resources)))
            plans[process_id] = picks
        return plans

    def _safe_demo_plans(self) -> Dict[str, List[str]]:
        resources = sorted(self.resources.keys())
        plans: Dict[str, List[str]] = {}
        for process_index in range(1, self.num_processes + 1):
            process_id = f"P{process_index}"
            resource_id = resources[(process_index - 1) % len(resources)]
            plans[process_id] = [resource_id]
        return plans

    def generate_plans(self) -> Dict[str, List[str]]:
        return self._deadlock_demo_plans() if self.force_deadlock else self._safe_demo_plans()

    def build_global_wfg_edges(self) -> List[Tuple[str, str, str]]:
        edges: List[Tuple[str, str, str]] = []
        for site_id, graph in self.local_wfgs.items():
            for source, targets in graph.items():
                for target in sorted(targets):
                    edges.append((site_id, source, target))
        return sorted(edges)

    def resource_snapshot(self) -> List[Dict[str, object]]:
        snapshot = []
        for resource_id, resource in sorted(self.resources.items()):
            snapshot.append(
                {
                    "resource": resource_id,
                    "site": resource.site_id,
                    "holder": resource.holder or "-",
                    "wait_queue": ", ".join(resource.wait_queue) if resource.wait_queue else "-",
                }
            )
        return snapshot

    def run(self) -> Dict[str, object]:
        plans = self.generate_plans()
        self.log_event(
            "START",
            "Simulation started",
            processes=self.num_processes,
            sites=self.num_sites,
            resources_per_site=self.resources_per_site,
            force_deadlock=self.force_deadlock,
        )
        for process_id, plan in plans.items():
            self.log_event("PLAN", f"{process_id} plan: {' -> '.join(plan)}", process=process_id, plan=plan)
            self.env.process(self.process_lifecycle(process_id, plan))

        self.env.run(until=self.max_time)
        self.log_event("END", "Simulation finished", detected_deadlocks=len(self.detected_cycles))

        return {
            "seed": self.seed,
            "plans": plans,
            "events": self.event_log,
            "probes": self.probe_log,
            "deadlocks": self.detected_cycles,
            "local_wfgs": {
                site_id: {node: sorted(targets) for node, targets in graph.items()}
                for site_id, graph in self.local_wfgs.items()
            },
            "global_edges": self.build_global_wfg_edges(),
            "resources": self.resource_snapshot(),
        }
