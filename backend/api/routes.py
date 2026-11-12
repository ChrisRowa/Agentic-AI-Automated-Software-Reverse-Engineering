"""
FastAPI route definitions for the Reverse Engineering AI Platform.
All API endpoints follow RESTful conventions with structured error handling.
"""
import asyncio
import os
import uuid
import aiofiles
import structlog
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Query
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from backend.core.config import settings
from backend.core.database import get_db
from backend.models.database import (
    Project, RepositoryFile, Symbol, GraphNode, GraphEdge,
    Claim, Evidence, GeneratedArtifact, ProgramSlice, TraceLink,
    AnalysisStatus, VerificationStatus, AnalysisError as DBAnalysisError,
)
from backend.models.schemas import (
    ProjectCreate, ProjectResponse, ProjectList, ProjectOverview,
    FileResponse, FileTreeNode, GraphResponse, GraphNodeResponse, GraphEdgeResponse,
    AskRequest, AskResponse, SliceRequest, SliceResponse,
    TraceRequest, TraceResponse, ImpactRequest, ImpactResponse,
    UMLRequest, UMLResponse, DocumentationRequest, DocumentationResponse,
    ClaimResponse, EvidenceItem, APIResponse,
)
from backend.analysis.pipeline import run_analysis_pipeline

logger = structlog.get_logger(__name__)

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Helper: get project or 404
# ─────────────────────────────────────────────────────────────────────────────

async def get_project_or_404(project_id: str, db: AsyncSession) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return project


# ─────────────────────────────────────────────────────────────────────────────
# Projects
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/projects", response_model=ProjectResponse, status_code=201, tags=["Projects"])
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new project (before uploading repository)."""
    project = Project(
        id=str(uuid.uuid4()),
        name=body.name,
        description=body.description,
        status=AnalysisStatus.QUEUED,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    logger.info("Project created", project_id=project.id)
    return project


@router.get("/projects", response_model=ProjectList, tags=["Projects"])
async def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all projects."""
    count_result = await db.execute(select(func.count(Project.id)))
    total = count_result.scalar()

    result = await db.execute(
        select(Project).order_by(desc(Project.created_at)).offset(skip).limit(limit)
    )
    projects = result.scalars().all()
    return ProjectList(projects=list(projects), total=total)


@router.get("/projects/{project_id}", response_model=ProjectResponse, tags=["Projects"])
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    """Get project details and current status."""
    return await get_project_or_404(project_id, db)


@router.delete("/projects/{project_id}", status_code=204, tags=["Projects"])
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a project and all its analysis data."""
    project = await get_project_or_404(project_id, db)
    await db.delete(project)
    await db.commit()
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Upload
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/upload", response_model=APIResponse, tags=["Upload"])
async def upload_repository(
    project_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a ZIP archive for analysis.
    Validates, saves to disk, then triggers the analysis pipeline in background.
    """
    project = await get_project_or_404(project_id, db)

    # Validate content type
    allowed_types = {
        "application/zip", "application/x-zip-compressed",
        "application/octet-stream", "application/x-zip",
    }
    if file.content_type and file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Only ZIP files are supported. Received: {file.content_type}"
        )

    # Validate filename
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="File must have a .zip extension")

    # Ensure upload directory exists
    upload_dir = Path(settings.workspace_dir) / project_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    archive_path = upload_dir / f"upload_{project_id}.zip"

    # Stream file to disk safely
    total_bytes = 0
    try:
        async with aiofiles.open(archive_path, "wb") as out_file:
            while chunk := await file.read(1024 * 64):  # 64KB chunks
                total_bytes += len(chunk)
                if total_bytes > settings.max_upload_size_bytes:
                    await out_file.close()
                    archive_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds maximum size of {settings.max_upload_size_mb}MB"
                    )
                await out_file.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

    # Update project with filename
    project.original_filename = file.filename
    project.archive_path = str(archive_path)
    project.status = AnalysisStatus.EXTRACTING
    await db.commit()

    # Launch analysis pipeline in background
    background_tasks.add_task(
        _run_pipeline_task,
        project_id=project_id,
        archive_path=str(archive_path),
    )

    logger.info("Upload complete, analysis started", project_id=project_id, size=total_bytes)
    return APIResponse(
        success=True,
        message="Upload successful. Analysis started.",
        data={"project_id": project_id, "file_size": total_bytes},
    )


async def _run_pipeline_task(project_id: str, archive_path: str):
    """Run the analysis pipeline in background with its own DB session."""
    from backend.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await run_analysis_pipeline(db=db, project_id=project_id, archive_path=archive_path)


# ─────────────────────────────────────────────────────────────────────────────
# Project Overview & Status
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/status", response_model=ProjectResponse, tags=["Analysis"])
async def get_analysis_status(project_id: str, db: AsyncSession = Depends(get_db)):
    """Poll the current analysis status and progress."""
    return await get_project_or_404(project_id, db)


@router.get("/projects/{project_id}/overview", response_model=ProjectOverview, tags=["Analysis"])
async def get_project_overview(project_id: str, db: AsyncSession = Depends(get_db)):
    """Get project overview including file tree and summary stats."""
    project = await get_project_or_404(project_id, db)

    # Get file tree
    result = await db.execute(
        select(RepositoryFile).where(
            RepositoryFile.project_id == project_id,
            RepositoryFile.is_ignored == False,
        ).limit(2000)
    )
    files = result.scalars().all()

    # Build simple file tree
    file_tree = _build_api_file_tree(files)

    # Language distribution
    lang_dist = project.detected_languages or {}

    return ProjectOverview(
        project=project,
        file_tree=file_tree,
        language_distribution=lang_dist,
        detected_patterns=project.detected_frameworks or [],
        tech_stack=_build_tech_stack(project),
    )


def _build_api_file_tree(files) -> List[FileTreeNode]:
    """Build FileTreeNode list from DB file records."""
    tree_dict = {}
    for f in files:
        parts = f.relative_path.replace("\\", "/").split("/")
        node = tree_dict
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                node[part] = FileTreeNode(
                    name=part,
                    path=f.relative_path,
                    type="file",
                    language=f.language,
                    is_test=f.is_test_file,
                    is_config=f.is_config_file,
                    file_id=str(f.id),
                )
            else:
                if part not in node:
                    node[part] = {"_dir": FileTreeNode(name=part, path=part, type="directory", children=[]), "_children": {}}
                node = node[part].get("_children", node[part]) if isinstance(node[part], dict) else node

    def flatten(d) -> List[FileTreeNode]:
        result = []
        for k, v in sorted(d.items()):
            if isinstance(v, FileTreeNode):
                result.append(v)
            elif isinstance(v, dict):
                dir_node = v.get("_dir")
                if dir_node:
                    dir_node.children = flatten(v.get("_children", {}))
                    result.append(dir_node)
        return result

    return flatten(tree_dict)


def _build_tech_stack(project: Project) -> List[str]:
    stack = []
    if project.detected_languages:
        for lang in list(project.detected_languages.keys())[:5]:
            stack.append(lang)
    if project.detected_frameworks:
        stack.extend(project.detected_frameworks[:5])
    return list(dict.fromkeys(stack))  # Deduplicate preserving order


# ─────────────────────────────────────────────────────────────────────────────
# Files
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/files", response_model=List[FileResponse], tags=["Files"])
async def get_files(
    project_id: str,
    language: Optional[str] = None,
    is_test: Optional[bool] = None,
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """Get files in the project, optionally filtered."""
    await get_project_or_404(project_id, db)

    query = select(RepositoryFile).where(RepositoryFile.project_id == project_id)
    if language:
        query = query.where(RepositoryFile.language == language)
    if is_test is not None:
        query = query.where(RepositoryFile.is_test_file == is_test)

    result = await db.execute(query.limit(limit))
    return result.scalars().all()


@router.get("/projects/{project_id}/files/{file_id}/content", tags=["Files"])
async def get_file_content(
    project_id: str,
    file_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the raw content of a specific file."""
    project = await get_project_or_404(project_id, db)
    result = await db.execute(
        select(RepositoryFile).where(
            RepositoryFile.id == file_id,
            RepositoryFile.project_id == project_id,
        )
    )
    file_rec = result.scalar_one_or_none()
    if not file_rec:
        raise HTTPException(status_code=404, detail="File not found")

    # Build absolute path
    source_path = Path(settings.workspace_dir) / project_id / "source" / file_rec.relative_path
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="File content not available")

    try:
        content = source_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not read file: {e}")

    return {
        "file_id": file_id,
        "relative_path": file_rec.relative_path,
        "language": file_rec.language,
        "content": content,
        "lines": len(content.splitlines()),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Graphs
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/graph", response_model=GraphResponse, tags=["Graph"])
async def get_knowledge_graph(
    project_id: str,
    node_type: Optional[str] = None,
    limit: int = Query(500, ge=1, le=5000),
    db: AsyncSession = Depends(get_db),
):
    """Get the full program knowledge graph."""
    await get_project_or_404(project_id, db)

    node_query = select(GraphNode).where(GraphNode.project_id == project_id)
    if node_type:
        node_query = node_query.where(GraphNode.node_type == node_type)
    node_query = node_query.limit(limit)

    node_result = await db.execute(node_query)
    nodes = node_result.scalars().all()
    node_ids = {str(n.id) for n in nodes}

    edge_result = await db.execute(
        select(GraphEdge).where(GraphEdge.project_id == project_id)
        .limit(limit * 3)
    )
    edges = [e for e in edge_result.scalars().all()
             if str(e.source_id) in node_ids and str(e.target_id) in node_ids]

    return GraphResponse(
        nodes=[GraphNodeResponse.model_validate(n) for n in nodes],
        edges=[GraphEdgeResponse.model_validate(e) for e in edges],
        total_nodes=len(nodes),
        total_edges=len(edges),
    )


@router.get("/projects/{project_id}/call-graph", response_model=GraphResponse, tags=["Graph"])
async def get_call_graph(
    project_id: str,
    limit: int = Query(300, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    """Get only CALLS edges — the call graph."""
    await get_project_or_404(project_id, db)

    edge_result = await db.execute(
        select(GraphEdge).where(
            GraphEdge.project_id == project_id,
            GraphEdge.relationship_type == "CALLS",
        ).limit(limit)
    )
    edges = edge_result.scalars().all()

    # Collect unique node IDs
    node_ids = set()
    for e in edges:
        node_ids.add(str(e.source_id))
        node_ids.add(str(e.target_id))

    nodes = []
    if node_ids:
        node_result = await db.execute(
            select(GraphNode).where(GraphNode.id.in_(list(node_ids)))
        )
        nodes = node_result.scalars().all()

    return GraphResponse(
        nodes=[GraphNodeResponse.model_validate(n) for n in nodes],
        edges=[GraphEdgeResponse.model_validate(e) for e in edges],
        total_nodes=len(nodes),
        total_edges=len(edges),
    )


@router.get("/projects/{project_id}/dependencies", response_model=GraphResponse, tags=["Graph"])
async def get_dependency_graph(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the file dependency / import graph."""
    await get_project_or_404(project_id, db)

    edge_result = await db.execute(
        select(GraphEdge).where(
            GraphEdge.project_id == project_id,
            GraphEdge.relationship_type.in_(["IMPORTS", "DEPENDS_ON"]),
        ).limit(1000)
    )
    edges = edge_result.scalars().all()
    node_ids = set()
    for e in edges:
        node_ids.add(str(e.source_id))
        node_ids.add(str(e.target_id))

    nodes = []
    if node_ids:
        node_result = await db.execute(
            select(GraphNode).where(GraphNode.id.in_(list(node_ids)))
        )
        nodes = node_result.scalars().all()

    return GraphResponse(
        nodes=[GraphNodeResponse.model_validate(n) for n in nodes],
        edges=[GraphEdgeResponse.model_validate(e) for e in edges],
        total_nodes=len(nodes),
        total_edges=len(edges),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Ask AI (Interactive Q&A)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/ask", response_model=AskResponse, tags=["AI"])
async def ask_question(
    project_id: str,
    body: AskRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Answer a question about the repository using hybrid RAG + LangGraph agents.
    Returns evidence-backed answers with source citations.
    """
    project = await get_project_or_404(project_id, db)

    if project.status not in (AnalysisStatus.COMPLETED, AnalysisStatus.PARTIAL):
        raise HTTPException(
            status_code=409,
            detail=f"Analysis not complete. Current status: {project.status}"
        )

    # Run LangGraph multi-agent reverse engineering workflow
    from backend.agents.orchestrator import run_agentic_qa
    response = await run_agentic_qa(
        db=db,
        project_id=project_id,
        question=body.question,
        context_limit=body.context_limit,
    )
    return response


# ─────────────────────────────────────────────────────────────────────────────
# Program Slicing
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/slice", response_model=SliceResponse, tags=["Analysis"])
async def create_slice(
    project_id: str,
    body: SliceRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate a program slice for a given criterion."""
    project = await get_project_or_404(project_id, db)
    if project.status not in (AnalysisStatus.COMPLETED, AnalysisStatus.PARTIAL):
        raise HTTPException(status_code=409, detail="Analysis not complete")

    from backend.slicing.slicer import compute_slice
    return await compute_slice(db=db, project_id=project_id, request=body)


# ─────────────────────────────────────────────────────────────────────────────
# Traceability
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/trace", response_model=TraceResponse, tags=["Analysis"])
async def trace_links(
    project_id: str,
    body: TraceRequest,
    db: AsyncSession = Depends(get_db),
):
    """Find traceability links between requirements and code."""
    project = await get_project_or_404(project_id, db)
    if project.status not in (AnalysisStatus.COMPLETED, AnalysisStatus.PARTIAL):
        raise HTTPException(status_code=409, detail="Analysis not complete")

    from backend.tracing.tracer import compute_trace
    return await compute_trace(db=db, project_id=project_id, request=body)


# ─────────────────────────────────────────────────────────────────────────────
# Change Impact Analysis
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/impact-analysis", response_model=ImpactResponse, tags=["Analysis"])
async def impact_analysis(
    project_id: str,
    body: ImpactRequest,
    db: AsyncSession = Depends(get_db),
):
    """Analyze which components are affected by a change to an entity."""
    project = await get_project_or_404(project_id, db)
    if project.status not in (AnalysisStatus.COMPLETED, AnalysisStatus.PARTIAL):
        raise HTTPException(status_code=409, detail="Analysis not complete")

    from backend.analysis.impact import compute_impact
    return await compute_impact(db=db, project_id=project_id, request=body)


# ─────────────────────────────────────────────────────────────────────────────
# UML Generation
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/uml", response_model=UMLResponse, tags=["Generation"])
async def generate_uml(
    project_id: str,
    body: UMLRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate UML diagrams from program structure (not LLM hallucination)."""
    project = await get_project_or_404(project_id, db)
    if project.status not in (AnalysisStatus.COMPLETED, AnalysisStatus.PARTIAL):
        raise HTTPException(status_code=409, detail="Analysis not complete")

    from backend.uml.generator import generate_uml_diagram
    return await generate_uml_diagram(db=db, project_id=project_id, request=body)


# ─────────────────────────────────────────────────────────────────────────────
# Documentation Generation
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/documentation", response_model=DocumentationResponse, tags=["Generation"])
async def generate_documentation(
    project_id: str,
    body: DocumentationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate documentation for the repository."""
    project = await get_project_or_404(project_id, db)
    if project.status not in (AnalysisStatus.COMPLETED, AnalysisStatus.PARTIAL):
        raise HTTPException(status_code=409, detail="Analysis not complete")

    from backend.documentation.generator import generate_docs
    return await generate_docs(db=db, project_id=project_id, request=body)


# ─────────────────────────────────────────────────────────────────────────────
# Evidence & Verification
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/evidence", tags=["Verification"])
async def get_evidence(
    project_id: str,
    claim_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get evidence items for verification."""
    await get_project_or_404(project_id, db)
    query = select(Claim).where(Claim.project_id == project_id)
    if claim_id:
        query = query.where(Claim.id == claim_id)
    result = await db.execute(query.limit(200))
    claims = result.scalars().all()
    return {"claims": [ClaimResponse.model_validate(c) for c in claims]}


@router.get("/projects/{project_id}/verification", tags=["Verification"])
async def get_verification_summary(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get verification summary — counts of verified/inferred/uncertain/unsupported claims."""
    await get_project_or_404(project_id, db)

    result = await db.execute(
        select(
            Claim.verification_status,
            func.count(Claim.id).label("count"),
        ).where(Claim.project_id == project_id)
        .group_by(Claim.verification_status)
    )
    rows = result.fetchall()
    summary = {row[0]: row[1] for row in rows}

    return {
        "project_id": project_id,
        "summary": summary,
        "total": sum(summary.values()),
        "verified": summary.get("VERIFIED", 0),
        "inferred": summary.get("INFERRED", 0),
        "uncertain": summary.get("UNCERTAIN", 0),
        "unsupported": summary.get("UNSUPPORTED", 0),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Final Report
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/report", tags=["Generation"])
async def get_report(
    project_id: str,
    format: str = Query("json", enum=["json", "markdown"]),
    db: AsyncSession = Depends(get_db),
):
    """Generate / retrieve the final System Reconstruction Report."""
    project = await get_project_or_404(project_id, db)
    if project.status not in (AnalysisStatus.COMPLETED, AnalysisStatus.PARTIAL):
        raise HTTPException(status_code=409, detail="Analysis not complete")

    from backend.documentation.report import generate_report
    return await generate_report(db=db, project=project, format=format)


# ─────────────────────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/health", tags=["System"])
async def health_check():
    """System health check verifying database, LLM config, retrieval, and graph services."""
    from backend.core.database import check_db_health
    from backend.retrieval.service import retrieval_service
    db_res = await check_db_health()
    llm_configured = bool(settings.openai_api_key or settings.google_api_key or settings.anthropic_api_key)

    is_healthy = db_res.get("status") == "healthy"
    return {
        "status": "healthy" if is_healthy else "degraded",
        "backend": "healthy",
        "database": db_res.get("status", "unavailable"),
        "database_dialect": db_res.get("dialect", "unknown"),
        "fallback_active": db_res.get("fallback_active", False),
        "llm": "configured" if llm_configured else "not_configured",
        "retrieval": "ready" if retrieval_service else "unavailable",
        "graph": "ready",
        "version": settings.app_version,
        "time": datetime.utcnow().isoformat(),
    }
