"""Change Impact Analysis — identifies affected components when an entity changes."""
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.models.database import GraphNode, GraphEdge
from backend.models.schemas import ImpactRequest, ImpactResponse

logger = structlog.get_logger(__name__)


async def compute_impact(db: AsyncSession, project_id: str, request: ImpactRequest) -> ImpactResponse:
    entity = request.entity
    entity_type = request.entity_type

    # Find the entity node
    result = await db.execute(
        select(GraphNode).where(
            GraphNode.project_id == project_id,
            GraphNode.label.ilike(f"%{entity}%"),
        ).limit(5)
    )
    nodes = result.scalars().all()

    if not nodes:
        return ImpactResponse(
            entity=entity,
            explanation=f"No code element named '{entity}' found.",
        )

    node_id = str(nodes[0].id)

    # Find callers (backward)
    caller_result = await db.execute(
        select(GraphEdge, GraphNode).join(
            GraphNode, GraphEdge.source_id == GraphNode.id
        ).where(
            GraphEdge.project_id == project_id,
            GraphEdge.target_id == node_id,
            GraphEdge.relationship_type == "CALLS",
        ).limit(20)
    )
    callers = [row[1].label for row in caller_result.fetchall()]

    # Find callees (forward)
    callee_result = await db.execute(
        select(GraphEdge, GraphNode).join(
            GraphNode, GraphEdge.target_id == GraphNode.id
        ).where(
            GraphEdge.project_id == project_id,
            GraphEdge.source_id == node_id,
            GraphEdge.relationship_type == "CALLS",
        ).limit(20)
    )
    callees = [row[1].label for row in callee_result.fetchall()]

    # Files depending on this node's file
    dep_result = await db.execute(
        select(GraphEdge, GraphNode).join(
            GraphNode, GraphEdge.source_id == GraphNode.id
        ).where(
            GraphEdge.project_id == project_id,
            GraphEdge.target_id == node_id,
            GraphEdge.relationship_type.in_(["IMPORTS", "DEPENDS_ON"]),
        ).limit(10)
    )
    affected_files = list({row[1].file_path for row in dep_result.fetchall() if row[1].file_path})

    evidence_path = [entity] + callees[:3]

    explanation = (
        f"Change impact for '{entity}':\n"
        f"- {len(callers)} callers may be affected\n"
        f"- {len(callees)} callees called by this entity\n"
        f"- {len(affected_files)} files depend on this entity"
    )

    return ImpactResponse(
        entity=entity,
        affected_callers=callers,
        affected_callees=callees,
        affected_files=affected_files,
        evidence_path=evidence_path,
        explanation=explanation,
    )
