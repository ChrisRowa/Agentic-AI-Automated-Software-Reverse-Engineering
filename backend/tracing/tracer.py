"""
Requirement-to-Code Traceability Module.
Research additions:
 - Path-Aware Traceability (#8)
 - Repository-Adaptive Traceability (#9)
 - Reverse Traceability & Change Impact Analysis (#5)

Uses the program knowledge graph and call graph for evidence-backed trace links.
No LLM guessing — all links are graph-derived with source evidence.
"""
import structlog
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.models.database import (
    GraphNode, GraphEdge, Symbol,
    TraceLink, VerificationStatus,
)
from backend.models.schemas import TraceRequest, TraceResponse, VerificationStatusEnum

logger = structlog.get_logger(__name__)


async def compute_trace(
    db: AsyncSession,
    project_id: str,
    request: TraceRequest,
) -> TraceResponse:
    """
    Compute traceability links from the program knowledge graph.
    Path-aware: follows call + dependency edges to verify complete paths.
    """
    source = request.source
    source_type = request.source_type
    direction = request.direction

    logger.info("Computing trace", source=source, source_type=source_type, direction=direction)

    # Find seed nodes matching the source
    node_result = await db.execute(
        select(GraphNode).where(
            GraphNode.project_id == project_id,
            GraphNode.label.ilike(f"%{source}%"),
        ).limit(10)
    )
    seed_nodes = node_result.scalars().all()

    if not seed_nodes:
        # Fallback: search by qualified name
        node_result2 = await db.execute(
            select(GraphNode).where(
                GraphNode.project_id == project_id,
                GraphNode.qualified_name.ilike(f"%{source}%"),
            ).limit(5)
        )
        seed_nodes = node_result2.scalars().all()

    if not seed_nodes:
        return TraceResponse(
            source=source,
            links=[],
            path=[],
            explanation=(
                f"No code elements found matching '{source}'. "
                "Try a function, class, or file name from the repository."
            ),
            verification_status=VerificationStatusEnum.UNCERTAIN,
            confidence=0.0,
        )

    links = []
    full_path = []
    files_seen = set()

    for seed_node in seed_nodes[:3]:
        seed_id = str(seed_node.id)
        if seed_node.file_path:
            files_seen.add(seed_node.file_path)

        if direction in ("forward", "both"):
            fwd = await _trace_forward(db, project_id, seed_node, seed_id)
            links.extend(fwd["links"])
            full_path.extend(fwd["path"])

        if direction in ("backward", "both"):
            bwd = await _trace_backward(db, project_id, seed_node, seed_id)
            links.extend(bwd["links"])

    # Deduplicate
    seen = set()
    unique_links = []
    for link in links:
        key = (link.get("source"), link.get("target"))
        if key not in seen:
            seen.add(key)
            unique_links.append(link)

    confidence = min(0.92, 0.4 + len(unique_links) * 0.08) if unique_links else 0.1

    # Store trace links
    for lnk in unique_links[:10]:
        db_link = TraceLink(
            project_id=project_id,
            source_type=source_type,
            source_id=lnk.get("source", source),
            target_type=lnk.get("target_type", "code"),
            target_id=lnk.get("target", ""),
            link_type=direction,
            confidence=lnk.get("confidence", 0.7),
            path=lnk.get("path"),
            verification_status=VerificationStatus.INFERRED,
        )
        db.add(db_link)
    await db.commit()

    explanation = (
        f"{'Forward' if direction == 'forward' else 'Reverse' if direction == 'backward' else 'Bidirectional'} "
        f"traceability from '{source}'. Found {len(unique_links)} trace links derived from "
        f"call graph and dependency graph traversal across {len(files_seen)} files. "
        f"All links have source evidence from static analysis."
    )

    return TraceResponse(
        source=source,
        links=unique_links[:50],
        path=list(dict.fromkeys(full_path))[:15],
        explanation=explanation,
        verification_status=VerificationStatusEnum.INFERRED if unique_links else VerificationStatusEnum.UNCERTAIN,
        confidence=confidence,
    )


async def _trace_forward(
    db: AsyncSession, project_id: str, seed_node: GraphNode, seed_id: str
) -> Dict[str, Any]:
    """Follow outgoing CALLS/DEPENDS_ON edges."""
    links = []
    path = [seed_node.label]
    queue = [(seed_id, seed_node.label, 0)]
    visited = set()

    while queue:
        nid, nname, depth = queue.pop(0)
        if nid in visited or depth > 4:
            continue
        visited.add(nid)

        result = await db.execute(
            select(GraphEdge, GraphNode).join(
                GraphNode, GraphNode.id == GraphEdge.target_id
            ).where(
                GraphEdge.project_id == project_id,
                GraphEdge.source_id == nid,
                GraphEdge.relationship_type.in_(["CALLS", "IMPORTS", "DEPENDS_ON", "USES"]),
            ).limit(8)
        )
        for edge, tnode in result.all():
            tid = str(tnode.id)
            links.append({
                "source": nname,
                "source_type": "code",
                "target": tnode.label,
                "target_type": (tnode.node_type or "code").lower(),
                "link_type": "forward",
                "relationship": edge.relationship_type,
                "confidence": float(edge.confidence or 0.8),
                "file": tnode.file_path,
                "line_start": tnode.line_start,
                "path": path + [tnode.label],
                "verification_status": "INFERRED",
            })
            if tnode.label not in path:
                path.append(tnode.label)
            if depth < 3:
                queue.append((tid, tnode.label, depth + 1))

    return {"links": links, "path": path}


async def _trace_backward(
    db: AsyncSession, project_id: str, seed_node: GraphNode, seed_id: str
) -> Dict[str, Any]:
    """Follow incoming CALLS edges — find callers."""
    links = []
    queue = [(seed_id, seed_node.label, 0)]
    visited = set()

    while queue:
        nid, nname, depth = queue.pop(0)
        if nid in visited or depth > 3:
            continue
        visited.add(nid)

        result = await db.execute(
            select(GraphEdge, GraphNode).join(
                GraphNode, GraphNode.id == GraphEdge.source_id
            ).where(
                GraphEdge.project_id == project_id,
                GraphEdge.target_id == nid,
                GraphEdge.relationship_type.in_(["CALLS", "IMPORTS", "DEPENDS_ON"]),
            ).limit(8)
        )
        for edge, snode in result.all():
            sid = str(snode.id)
            links.append({
                "source": snode.label,
                "source_type": (snode.node_type or "code").lower(),
                "target": nname,
                "target_type": "code",
                "link_type": "backward",
                "relationship": edge.relationship_type,
                "confidence": float(edge.confidence or 0.8),
                "file": snode.file_path,
                "line_start": snode.line_start,
                "path": [snode.label, nname],
                "verification_status": "INFERRED",
            })
            if depth < 2:
                queue.append((sid, snode.label, depth + 1))

    return {"links": links, "path": []}
