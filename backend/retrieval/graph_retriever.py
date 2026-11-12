"""
Knowledge Graph-Aware Retrieval.
Expands code candidate evidence using deterministic graph relationships:
CALLS, IMPORTS, DEPENDS_ON, CONTAINS, and DEFINES.
Discovers architectural context and call chains for retrieved symbols.
"""
import structlog
from typing import List, Dict, Any, Set, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = structlog.get_logger(__name__)


class GraphAwareRetriever:
    """
    Expands seed code symbols into graph-connected contextual evidence.
    """

    def __init__(self, graph_data: Optional[Dict[str, Any]] = None):
        self.graph_data = graph_data or {"nodes": [], "edges": []}
        self._index_graph()

    def _index_graph(self):
        # Quick lookups by label, qualified_name, and node_id
        self.nodes_by_id: Dict[str, Dict] = {}
        self.nodes_by_label: Dict[str, List[Dict]] = {}
        self.outgoing_edges: Dict[str, List[Dict]] = {}
        self.incoming_edges: Dict[str, List[Dict]] = {}

        for n in self.graph_data.get("nodes", []):
            nid = str(n.get("id"))
            self.nodes_by_id[nid] = n

            lbl = (n.get("label") or "").lower()
            if lbl:
                self.nodes_by_label.setdefault(lbl, []).append(n)

            qname = (n.get("qualified_name") or "").lower()
            if qname and qname != lbl:
                self.nodes_by_label.setdefault(qname, []).append(n)

        for e in self.graph_data.get("edges", []):
            src = str(e.get("source_id") or e.get("source"))
            tgt = str(e.get("target_id") or e.get("target"))

            self.outgoing_edges.setdefault(src, []).append(e)
            self.incoming_edges.setdefault(tgt, []).append(e)

    def find_nodes_by_symbol(self, symbol_name: str) -> List[Dict]:
        """Find graph nodes matching a symbol name or qualified name."""
        if not symbol_name:
            return []
        sym_lower = symbol_name.lower()
        matches = self.nodes_by_label.get(sym_lower, [])
        if not matches:
            # Substring match
            for lbl, nodes in self.nodes_by_label.items():
                if sym_lower in lbl or lbl in sym_lower:
                    matches.extend(nodes)
        return matches

    def expand_graph_context(
        self,
        seed_symbols: List[str],
        max_depth: int = 2,
    ) -> Dict[str, Any]:
        """
        Traverse callers, callees, dependencies, and hierarchy for seed symbols.
        Returns:
          - related_nodes: list of connected node dicts
          - call_paths: list of call sequences (e.g. ['login', 'authenticate', 'find_user'])
          - dependency_nodes: list of imported/dependent nodes
          - graph_scores: dict of node_id -> graph_score (0.0 to 1.0)
        """
        seed_nodes = []
        for sym in seed_symbols:
            seed_nodes.extend(self.find_nodes_by_symbol(sym))

        if not seed_nodes:
            return {
                "related_nodes": [],
                "call_paths": [],
                "dependency_nodes": [],
                "graph_scores": {},
            }

        visited_nodes: Set[str] = set()
        graph_scores: Dict[str, float] = {}
        call_chains: List[List[str]] = []
        dependency_nodes: List[Dict] = []

        for seed in seed_nodes:
            sid = str(seed.get("id"))
            visited_nodes.add(sid)
            graph_scores[sid] = 1.0

            # 1. Inspect Callers & Callees (CALLS)
            curr_chain = [seed.get("label", "unknown")]
            curr_id = sid

            for d in range(max_depth):
                out_edges = [
                    e for e in self.outgoing_edges.get(curr_id, [])
                    if e.get("relationship_type") == "CALLS"
                ]
                if not out_edges:
                    break

                next_edge = out_edges[0]
                target_id = str(next_edge.get("target_id") or next_edge.get("target"))
                target_node = self.nodes_by_id.get(target_id)
                if target_node:
                    curr_chain.append(target_node.get("label", "unknown"))
                    graph_scores[target_id] = max(graph_scores.get(target_id, 0.0), 0.8 / (d + 1))
                    visited_nodes.add(target_id)
                    curr_id = target_id

            if len(curr_chain) > 1:
                call_chains.append(curr_chain)

            # 2. Inspect Dependencies (IMPORTS / DEPENDS_ON)
            dep_edges = [
                e for e in self.outgoing_edges.get(sid, [])
                if e.get("relationship_type") in ("IMPORTS", "DEPENDS_ON")
            ]
            for de in dep_edges:
                tid = str(de.get("target_id") or de.get("target"))
                tnode = self.nodes_by_id.get(tid)
                if tnode:
                    dependency_nodes.append(tnode)
                    graph_scores[tid] = max(graph_scores.get(tid, 0.0), 0.7)
                    visited_nodes.add(tid)

            # 3. Inspect Hierarchy (CONTAINS / DEFINES)
            in_edges = [
                e for e in self.incoming_edges.get(sid, [])
                if e.get("relationship_type") in ("CONTAINS", "DEFINES")
            ]
            for ie in in_edges:
                parent_id = str(ie.get("source_id") or ie.get("source"))
                pnode = self.nodes_by_id.get(parent_id)
                if pnode:
                    graph_scores[parent_id] = max(graph_scores.get(parent_id, 0.0), 0.6)
                    visited_nodes.add(parent_id)

        related_nodes = [self.nodes_by_id[nid] for nid in visited_nodes if nid in self.nodes_by_id]

        return {
            "related_nodes": related_nodes,
            "call_paths": call_chains,
            "dependency_nodes": dependency_nodes,
            "graph_scores": graph_scores,
        }
