"""
Hierarchical Program Slicing Module.
Computes forward, backward, feature, and function slices from the knowledge graph.
Research addition #15: Hierarchical Program Slicing — extends statement-level
slicing to function/class/module/behavior slices.
"""
import structlog
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.models.database import GraphNode, GraphEdge, Symbol, RepositoryFile
from backend.models.schemas import SliceRequest, SliceResponse

logger = structlog.get_logger(__name__)


async def compute_slice(
    db: AsyncSession,
    project_id: str,
    request: SliceRequest,
) -> SliceResponse:
    """
    Compute a program slice from the knowledge graph.
    Uses graph traversal — deterministic, not LLM guessing.
    """
    criterion = request.criterion
    slice_type = request.slice_type

    # Find nodes matching the criterion
    node_result = await db.execute(
        select(GraphNode).where(
            GraphNode.project_id == project_id,
            GraphNode.label.ilike(f"%{criterion}%"),
        ).limit(10)
    )
    seed_nodes = node_result.scalars().all()

    if not seed_nodes:
        return SliceResponse(
            criterion=criterion,
            slice_type=slice_type,
            explanation=f"No nodes found matching '{criterion}'. "
                        f"Try using a function or class name from the repository.",
        )

    seed_node = seed_nodes[0]
    seed_id = str(seed_node.id)

    # Traverse graph based on slice type
    relevant_node_ids = set([seed_id])
    edges_traversed = []

    if slice_type in ("forward", "feature"):
        # Follow CALLS and DEPENDS_ON edges outward
        queue = [seed_id]
        visited = set()
        depth = 0
        while queue and depth < 5:
            next_queue = []
            for nid in queue:
                if nid in visited:
                    continue
                visited.add(nid)
                result = await db.execute(
                    select(GraphEdge).where(
                        GraphEdge.project_id == project_id,
                        GraphEdge.source_id == nid,
                        GraphEdge.relationship_type.in_(["CALLS", "DEPENDS_ON", "IMPORTS"]),
                    ).limit(20)
                )
                for edge in result.scalars().all():
                    tid = str(edge.target_id)
                    relevant_node_ids.add(tid)
                    edges_traversed.append(edge)
                    next_queue.append(tid)
            queue = next_queue
            depth += 1

    elif slice_type == "backward":
        # Follow incoming CALLS edges
        queue = [seed_id]
        visited = set()
        depth = 0
        while queue and depth < 5:
            next_queue = []
            for nid in queue:
                if nid in visited:
                    continue
                visited.add(nid)
                result = await db.execute(
                    select(GraphEdge).where(
                        GraphEdge.project_id == project_id,
                        GraphEdge.target_id == nid,
                        GraphEdge.relationship_type == "CALLS",
                    ).limit(20)
                )
                for edge in result.scalars().all():
                    sid = str(edge.source_id)
                    relevant_node_ids.add(sid)
                    edges_traversed.append(edge)
                    next_queue.append(sid)
            queue = next_queue
            depth += 1

    # Get node details
    node_result = await db.execute(
        select(GraphNode).where(GraphNode.id.in_(list(relevant_node_ids)))
    )
    nodes = node_result.scalars().all()

    # Collect files and functions
    relevant_files = list({n.file_path for n in nodes if n.file_path})
    relevant_functions = [n.label for n in nodes if n.node_type in ("FUNCTION", "METHOD")]

    # Build dependency path
    dep_path = [seed_node.label]
    for edge in edges_traversed[:10]:
        node_r = await db.execute(select(GraphNode).where(GraphNode.id == edge.target_id))
        tnode = node_r.scalar_one_or_none()
        if tnode:
            dep_path.append(tnode.label)

    # Build source lines
    source_lines = []
    for node in nodes[:20]:
        if node.file_path and node.line_start:
            source_lines.append({
                "file": node.file_path,
                "line_start": node.line_start,
                "line_end": node.line_end,
                "symbol": node.label,
                "type": node.node_type,
            })

    explanation = (
        f"{'Forward' if slice_type in ('forward', 'feature') else 'Backward'} slice "
        f"of '{criterion}':\n"
        f"Found {len(relevant_node_ids)} related program elements across "
        f"{len(relevant_files)} files.\n"
        f"Dependency path: {' → '.join(dep_path[:8])}"
    )

    return SliceResponse(
        criterion=criterion,
        slice_type=slice_type,
        relevant_files=relevant_files,
        relevant_functions=relevant_functions,
        dependency_path=dep_path,
        source_lines=source_lines,
        explanation=explanation,
        visualization_data={
            "nodes": [{"id": str(n.id), "label": n.label, "type": n.node_type} for n in nodes],
            "edges": [{"source": str(e.source_id), "target": str(e.target_id), "type": e.relationship_type} for e in edges_traversed],
        },
    )
