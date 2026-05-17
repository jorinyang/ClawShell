"""Swarm Topology Manager — Manages network topology for distributed swarm coordination.

TopologyType enum: MESH, HIERARCHICAL, CENTRALIZED, HYBRID
NodeRole enum: QUEEN, WORKER, COORDINATOR, PEER

Topology behavior:
  MESH         — auto-connect all nodes (peer-to-peer)
  HIERARCHICAL — first node is QUEEN, all others are WORKERs
  CENTRALIZED  — single QUEEN, all others are WORKERs (star topology)
  HYBRID       — regional partitions with COORDINATORS per partition

Thread-safe, BFS-based routing, leader election by weighted score.
"""

from __future__ import annotations

import time
import threading
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


# ── Enums ───────────────────────────────────────────────────────────────

class TopologyType(Enum):
    """Supported swarm topology types."""
    MESH = "mesh"
    HIERARCHICAL = "hierarchical"
    CENTRALIZED = "centralized"
    HYBRID = "hybrid"


class NodeRole(Enum):
    """Roles a node can assume in the topology."""
    QUEEN = "queen"
    WORKER = "worker"
    COORDINATOR = "coordinator"
    PEER = "peer"


# ── Data Classes ────────────────────────────────────────────────────────

@dataclass
class TopologyNode:
    """A node in the swarm topology."""
    node_id: str
    role: NodeRole
    status: str = "online"               # online | offline | degraded
    capabilities: List[str] = field(default_factory=list)
    trust_score: float = 0.5             # 0.0–1.0
    connections: List[str] = field(default_factory=list)
    workload: float = 0.0                # 0.0–1.0
    last_heartbeat: float = 0.0          # epoch seconds
    partition_id: Optional[str] = None   # for HYBRID topology

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "role": self.role.value,
            "status": self.status,
            "capabilities": list(self.capabilities),
            "trust_score": self.trust_score,
            "connections": list(self.connections),
            "workload": self.workload,
            "last_heartbeat": self.last_heartbeat,
            "partition_id": self.partition_id,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TopologyNode":
        return cls(
            node_id=d["node_id"],
            role=NodeRole(d["role"]),
            status=d.get("status", "online"),
            capabilities=list(d.get("capabilities", [])),
            trust_score=d.get("trust_score", 0.5),
            connections=list(d.get("connections", [])),
            workload=d.get("workload", 0.0),
            last_heartbeat=d.get("last_heartbeat", 0.0),
            partition_id=d.get("partition_id"),
        )


@dataclass
class TopologyEdge:
    """A weighted edge between two nodes."""
    from_node: str
    to_node: str
    weight: float = 1.0
    bidirectional: bool = True
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "from_node": self.from_node,
            "to_node": self.to_node,
            "weight": self.weight,
            "bidirectional": self.bidirectional,
            "latency_ms": self.latency_ms,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TopologyEdge":
        return cls(
            from_node=d["from_node"],
            to_node=d["to_node"],
            weight=d.get("weight", 1.0),
            bidirectional=d.get("bidirectional", True),
            latency_ms=d.get("latency_ms", 0.0),
        )


@dataclass
class TopologyPartition:
    """A partition of nodes (used in HYBRID topology)."""
    partition_id: str
    nodes: List[str] = field(default_factory=list)
    leader: Optional[str] = None
    replica_count: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "partition_id": self.partition_id,
            "nodes": list(self.nodes),
            "leader": self.leader,
            "replica_count": self.replica_count,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TopologyPartition":
        return cls(
            partition_id=d["partition_id"],
            nodes=list(d.get("nodes", [])),
            leader=d.get("leader"),
            replica_count=d.get("replica_count", 1),
        )


@dataclass
class RebalanceResult:
    """Result of a topology rebalance operation."""
    moved_nodes: List[str] = field(default_factory=list)
    added_edges: List[Tuple[str, str]] = field(default_factory=list)
    removed_edges: List[Tuple[str, str]] = field(default_factory=list)
    partitions_changed: bool = False
    leader_elected: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "moved_nodes": self.moved_nodes,
            "added_edges": list(self.added_edges),
            "removed_edges": list(self.removed_edges),
            "partitions_changed": self.partitions_changed,
            "leader_elected": self.leader_elected,
        }


@dataclass
class TopologyState:
    """Full snapshot of the topology."""
    topology_type: str
    nodes: Dict[str, Dict[str, Any]]
    edges: List[Dict[str, Any]]
    partitions: List[Dict[str, Any]]
    queen_id: Optional[str]
    timestamp: float


# ── Topology Manager ────────────────────────────────────────────────────

class TopologyManager:
    """Manages swarm network topology, routing, leader election, and rebalancing.

    Thread-safe. Supports four topology types with automatic connection management.
    """

    def __init__(self, topology_type: TopologyType = TopologyType.MESH,
                 max_partition_size: int = 10) -> None:
        self._lock = threading.RLock()
        self._topology_type = topology_type
        self._max_partition_size = max_partition_size

        self._nodes: Dict[str, TopologyNode] = {}
        self._edges: Dict[Tuple[str, str], TopologyEdge] = {}  # (from,to) -> edge
        self._partitions: Dict[str, TopologyPartition] = {}
        self._queen_id: Optional[str] = None

    # ── Public API ──────────────────────────────────────────────────────

    @property
    def topology_type(self) -> TopologyType:
        return self._topology_type

    def add_node(self, node_id: str, capabilities: Optional[List[str]] = None,
                 trust_score: float = 0.5, partition_id: Optional[str] = None,
                 role: Optional[NodeRole] = None) -> TopologyNode:
        """Add a node to the topology. Role assignment depends on topology type."""
        with self._lock:
            if node_id in self._nodes:
                raise ValueError(f"Node {node_id} already exists")

            resolved_role = role or self._assign_role(node_id)
            node = TopologyNode(
                node_id=node_id,
                role=resolved_role,
                status="online",
                capabilities=capabilities or [],
                trust_score=trust_score,
                last_heartbeat=time.time(),
                partition_id=partition_id,
            )
            self._nodes[node_id] = node

            # Auto-wire based on topology type
            self._auto_connect(node_id)

            # Handle HYBRID partitioning
            if self._topology_type == TopologyType.HYBRID:
                self._assign_to_partition(node_id, partition_id)

            # If this is the first node, potentially elect queen
            if self._queen_id is None and resolved_role == NodeRole.QUEEN:
                self._queen_id = node_id

            return node

    def remove_node(self, node_id: str) -> RebalanceResult:
        """Remove a node and return the rebalance result."""
        with self._lock:
            if node_id not in self._nodes:
                raise ValueError(f"Node {node_id} not found")

            result = RebalanceResult()

            # Remove edges involving this node
            edges_to_remove = [
                key for key in self._edges
                if node_id in key
            ]
            for key in edges_to_remove:
                del self._edges[key]
                result.removed_edges.append(key)

            # Update connections on remaining nodes
            for nid, n in self._nodes.items():
                if node_id in n.connections:
                    n.connections.remove(node_id)

            # Remove from partition
            if node_id in self._nodes and self._nodes[node_id].partition_id:
                pid = self._nodes[node_id].partition_id
                if pid in self._partitions:
                    part = self._partitions[pid]
                    if node_id in part.nodes:
                        part.nodes.remove(node_id)
                    if part.leader == node_id:
                        part.leader = None
                        # Elect new leader from partition if possible
                        candidates = [n for n in part.nodes if n in self._nodes]
                        if candidates:
                            new_leader = self._elect_leader(candidates)
                            part.leader = new_leader
                            result.leader_elected = new_leader

            # If queen was removed, elect new queen
            if self._queen_id == node_id:
                self._queen_id = None
                remaining = [n for n in self._nodes if n != node_id]
                if remaining:
                    new_queen = self._elect_leader(remaining)
                    self._queen_id = new_queen
                    self._nodes[new_queen].role = NodeRole.QUEEN
                    result.leader_elected = new_queen

            # Remove the node
            del self._nodes[node_id]
            result.moved_nodes.append(node_id)

            # Rebalance after removal
            rb = self._rebalance_internal()
            result.added_edges.extend(rb.added_edges)
            result.removed_edges.extend(rb.removed_edges)
            result.partitions_changed = rb.partitions_changed

            return result

    def update_node_status(self, node_id: str, status: str) -> None:
        """Update a node's status (online, offline, degraded)."""
        with self._lock:
            if node_id not in self._nodes:
                raise ValueError(f"Node {node_id} not found")
            self._nodes[node_id].status = status

    def update_node_metrics(self, node_id: str, trust_score: Optional[float] = None,
                            workload: Optional[float] = None,
                            capabilities: Optional[List[str]] = None) -> None:
        """Update node metrics (trust, workload, capabilities)."""
        with self._lock:
            if node_id not in self._nodes:
                raise ValueError(f"Node {node_id} not found")
            node = self._nodes[node_id]
            if trust_score is not None:
                node.trust_score = max(0.0, min(1.0, trust_score))
            if workload is not None:
                node.workload = max(0.0, min(1.0, workload))
            if capabilities is not None:
                node.capabilities = capabilities
            node.last_heartbeat = time.time()

    def elect_leader(self, candidates: Optional[List[str]] = None) -> Optional[str]:
        """Elect a leader from candidates using weighted scoring.

        Score = trust_score * 0.6 + (1 - workload) * 0.4
        """
        with self._lock:
            if candidates is None:
                candidates = [
                    nid for nid, n in self._nodes.items()
                    if n.status == "online"
                ]
            if not candidates:
                return None
            elected = self._elect_leader(candidates)
            self._queen_id = elected
            return elected

    def rebalance(self) -> RebalanceResult:
        """Trigger a full topology rebalance."""
        with self._lock:
            return self._rebalance_internal()

    def get_route(self, from_node: str, to_node: str) -> Optional[List[str]]:
        """Find shortest path between two nodes using BFS."""
        with self._lock:
            return self._bfs_route(from_node, to_node)

    def get_topology_state(self) -> TopologyState:
        """Get a full snapshot of the topology state."""
        with self._lock:
            edges = [e.to_dict() for e in self._edges.values()]
            # Deduplicate bidirectional edges for snapshot
            seen: Set[Tuple[str, str]] = set()
            deduped_edges = []
            for e in edges:
                key = tuple(sorted([e["from_node"], e["to_node"]]))
                if key not in seen:
                    seen.add(key)
                    deduped_edges.append(e)

            return TopologyState(
                topology_type=self._topology_type.value,
                nodes={nid: n.to_dict() for nid, n in self._nodes.items()},
                edges=deduped_edges,
                partitions=[p.to_dict() for p in self._partitions.values()],
                queen_id=self._queen_id,
                timestamp=time.time(),
            )

    # ── Internals ───────────────────────────────────────────────────────

    def _assign_role(self, node_id: str) -> NodeRole:
        """Assign a role based on topology type. Caller must hold lock."""
        if self._topology_type == TopologyType.MESH:
            return NodeRole.PEER
        elif self._topology_type in (TopologyType.HIERARCHICAL, TopologyType.CENTRALIZED):
            if len(self._nodes) == 0:
                return NodeRole.QUEEN
            return NodeRole.WORKER
        elif self._topology_type == TopologyType.HYBRID:
            # First node per partition is COORDINATOR
            return NodeRole.WORKER  # Will be promoted by partition logic
        return NodeRole.WORKER

    def _auto_connect(self, node_id: str) -> None:
        """Auto-wire edges based on topology type. Caller must hold lock."""
        if self._topology_type == TopologyType.MESH:
            # Connect to all existing nodes
            for nid in self._nodes:
                if nid != node_id:
                    self._add_edge(node_id, nid, bidirectional=True)

        elif self._topology_type == TopologyType.HIERARCHICAL:
            # Connect to queen only
            if self._queen_id and self._queen_id != node_id:
                self._add_edge(self._queen_id, node_id, bidirectional=True)

        elif self._topology_type == TopologyType.CENTRALIZED:
            # All connections go through queen (star)
            if self._queen_id and self._queen_id != node_id:
                self._add_edge(self._queen_id, node_id, bidirectional=True)

        elif self._topology_type == TopologyType.HYBRID:
            # Connect to nodes in same partition + coordinator
            pass  # Handled by _assign_to_partition

    def _add_edge(self, from_node: str, to_node: str, weight: float = 1.0,
                  bidirectional: bool = True, latency_ms: float = 0.0) -> TopologyEdge:
        """Add an edge between two nodes. Caller must hold lock."""
        # Ensure canonical key order for bidirectional
        key = (from_node, to_node)
        edge = TopologyEdge(
            from_node=from_node, to_node=to_node,
            weight=weight, bidirectional=bidirectional, latency_ms=latency_ms,
        )
        self._edges[key] = edge

        # Update connections lists
        if from_node in self._nodes and to_node not in self._nodes[from_node].connections:
            self._nodes[from_node].connections.append(to_node)
        if bidirectional and to_node in self._nodes and from_node not in self._nodes[to_node].connections:
            self._nodes[to_node].connections.append(from_node)

        return edge

    def _has_edge(self, a: str, b: str) -> bool:
        """Check if an edge exists between a and b (either direction). Caller must hold lock."""
        return (a, b) in self._edges or (b, a) in self._edges

    def _assign_to_partition(self, node_id: str, partition_id: Optional[str]) -> None:
        """Assign a node to a partition in HYBRID topology. Caller must hold lock."""
        if partition_id is None:
            # Auto-assign to partition with fewest nodes
            if not self._partitions:
                partition_id = "partition-0"
            else:
                smallest = min(self._partitions.values(), key=lambda p: len(p.nodes))
                # If smallest is full, create new
                if len(smallest.nodes) >= self._max_partition_size:
                    partition_id = f"partition-{len(self._partitions)}"
                else:
                    partition_id = smallest.partition_id

        if partition_id not in self._partitions:
            self._partitions[partition_id] = TopologyPartition(
                partition_id=partition_id,
                leader=node_id,
                replica_count=1,
            )

        part = self._partitions[partition_id]
        if node_id not in part.nodes:
            part.nodes.append(node_id)
        self._nodes[node_id].partition_id = partition_id

        # First node in partition becomes COORDINATOR
        if len(part.nodes) == 1:
            self._nodes[node_id].role = NodeRole.COORDINATOR
            part.leader = node_id
        else:
            # Connect to coordinator and other nodes in partition
            if part.leader and part.leader != node_id:
                self._add_edge(part.leader, node_id, bidirectional=True)
            # Also connect to other partition members
            for existing_nid in part.nodes:
                if existing_nid != node_id and not self._has_edge(node_id, existing_nid):
                    self._add_edge(node_id, existing_nid, bidirectional=True)

    def _elect_leader(self, candidates: List[str]) -> str:
        """Elect leader by weighted score: trust*0.6 + (1-workload)*0.4. Caller must hold lock."""
        best_id = candidates[0]
        best_score = -1.0
        for cid in candidates:
            node = self._nodes.get(cid)
            if node is None:
                continue
            score = node.trust_score * 0.6 + (1.0 - node.workload) * 0.4
            if score > best_score:
                best_score = score
                best_id = cid
        return best_id

    def _rebalance_internal(self) -> RebalanceResult:
        """Internal rebalance. Caller must hold lock."""
        result = RebalanceResult()

        if self._topology_type == TopologyType.MESH:
            # Ensure all nodes are connected to each other
            node_ids = list(self._nodes.keys())
            for i, a in enumerate(node_ids):
                for b in node_ids[i + 1:]:
                    if not self._has_edge(a, b):
                        self._add_edge(a, b, bidirectional=True)
                        result.added_edges.append((a, b))

        elif self._topology_type in (TopologyType.HIERARCHICAL, TopologyType.CENTRALIZED):
            # Ensure queen exists and all workers connect to queen
            if self._queen_id is None or self._queen_id not in self._nodes:
                online = [
                    nid for nid, n in self._nodes.items()
                    if n.status == "online"
                ]
                if online:
                    self._queen_id = self._elect_leader(online)
                    self._nodes[self._queen_id].role = NodeRole.QUEEN
                    result.leader_elected = self._queen_id

            if self._queen_id:
                for nid, node in self._nodes.items():
                    if nid != self._queen_id:
                        if not self._has_edge(self._queen_id, nid):
                            self._add_edge(self._queen_id, nid, bidirectional=True)
                            result.added_edges.append((self._queen_id, nid))
                        node.role = NodeRole.WORKER

        elif self._topology_type == TopologyType.HYBRID:
            # Ensure each partition has a coordinator
            for pid, part in self._partitions.items():
                online_in_partition = [
                    nid for nid in part.nodes
                    if nid in self._nodes and self._nodes[nid].status == "online"
                ]
                if online_in_partition:
                    if part.leader not in online_in_partition:
                        new_leader = self._elect_leader(online_in_partition)
                        part.leader = new_leader
                        self._nodes[new_leader].role = NodeRole.COORDINATOR
                        result.leader_elected = new_leader
                        result.partitions_changed = True

                    # Ensure full connectivity within partition
                    for i, a in enumerate(online_in_partition):
                        for b in online_in_partition[i + 1:]:
                            if not self._has_edge(a, b):
                                self._add_edge(a, b, bidirectional=True)
                                result.added_edges.append((a, b))

        return result

    def _bfs_route(self, from_node: str, to_node: str) -> Optional[List[str]]:
        """BFS shortest path. Caller must hold lock."""
        if from_node not in self._nodes or to_node not in self._nodes:
            return None
        if from_node == to_node:
            return [from_node]

        visited: Set[str] = {from_node}
        queue: deque[List[str]] = deque([[from_node]])

        while queue:
            path = queue.popleft()
            current = path[-1]

            # Get neighbors
            node = self._nodes.get(current)
            if node is None:
                continue
            for neighbor in node.connections:
                if neighbor == to_node:
                    return path + [neighbor]
                if neighbor not in visited and neighbor in self._nodes:
                    visited.add(neighbor)
                    queue.append(path + [neighbor])

        return None  # No path found
