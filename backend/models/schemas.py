"""
Pydantic schemas for API request/response validation.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ─────────────────────────────────────────────────────────────────────────────
# Shared enums (mirrors DB enums but for API)
# ─────────────────────────────────────────────────────────────────────────────

class AnalysisStatusEnum(str, Enum):
    QUEUED = "QUEUED"
    EXTRACTING = "EXTRACTING"
    DISCOVERING = "DISCOVERING"
    PARSING = "PARSING"
    BUILDING_GRAPHS = "BUILDING_GRAPHS"
    INDEXING = "INDEXING"
    AGENT_ANALYSIS = "AGENT_ANALYSIS"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


class VerificationStatusEnum(str, Enum):
    VERIFIED = "VERIFIED"
    INFERRED = "INFERRED"
    UNCERTAIN = "UNCERTAIN"
    UNSUPPORTED = "UNSUPPORTED"


# ─────────────────────────────────────────────────────────────────────────────
# Project
# ─────────────────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    status: AnalysisStatusEnum
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    original_filename: Optional[str] = None
    archive_size_bytes: Optional[int] = None
    file_count: Optional[int] = None

    primary_language: Optional[str] = None
    detected_languages: Optional[Dict[str, Any]] = None
    detected_frameworks: Optional[List[str]] = None
    project_type: Optional[str] = None

    total_files: int = 0
    total_classes: int = 0
    total_functions: int = 0
    total_modules: int = 0
    total_dependencies: int = 0
    total_api_endpoints: int = 0
    total_lines_of_code: int = 0

    analysis_progress: float = 0.0
    error_message: Optional[str] = None
    git_available: bool = False

    class Config:
        from_attributes = True


class ProjectList(BaseModel):
    projects: List[ProjectResponse]
    total: int


# ─────────────────────────────────────────────────────────────────────────────
# Files
# ─────────────────────────────────────────────────────────────────────────────

class FileResponse(BaseModel):
    id: str
    project_id: str
    relative_path: str
    filename: str
    extension: Optional[str] = None
    language: Optional[str] = None
    size_bytes: Optional[int] = None
    lines_of_code: Optional[int] = None
    is_test_file: bool = False
    is_config_file: bool = False
    is_documentation: bool = False
    module_name: Optional[str] = None
    ai_summary: Optional[str] = None

    class Config:
        from_attributes = True


class FileTreeNode(BaseModel):
    name: str
    path: str
    type: str  # file or directory
    language: Optional[str] = None
    children: Optional[List["FileTreeNode"]] = None
    file_id: Optional[str] = None
    is_test: bool = False
    is_config: bool = False


FileTreeNode.model_rebuild()


# ─────────────────────────────────────────────────────────────────────────────
# Graph structures
# ─────────────────────────────────────────────────────────────────────────────

class GraphNodeResponse(BaseModel):
    id: str
    node_type: str
    label: str
    qualified_name: Optional[str] = None
    file_path: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    properties: Optional[Dict[str, Any]] = None
    ai_summary: Optional[str] = None
    language: Optional[str] = None
    module: Optional[str] = None

    class Config:
        from_attributes = True


class GraphEdgeResponse(BaseModel):
    id: str
    source_id: str
    target_id: str
    relationship_type: str
    evidence_file: Optional[str] = None
    evidence_line_start: Optional[int] = None
    evidence_line_end: Optional[int] = None
    weight: float = 1.0
    confidence: float = 1.0

    class Config:
        from_attributes = True


class GraphResponse(BaseModel):
    nodes: List[GraphNodeResponse]
    edges: List[GraphEdgeResponse]
    total_nodes: int
    total_edges: int


# ─────────────────────────────────────────────────────────────────────────────
# Evidence
# ─────────────────────────────────────────────────────────────────────────────

class EvidenceItem(BaseModel):
    id: Optional[str] = None
    file: str
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    evidence_type: str
    content_snippet: Optional[str] = None
    source_tool: Optional[str] = None


class ClaimResponse(BaseModel):
    id: str
    claim_text: str
    claim_type: Optional[str] = None
    agent_source: Optional[str] = None
    verification_status: VerificationStatusEnum
    confidence: float
    evidence: Optional[List[EvidenceItem]] = None

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────────────────
# Analysis requests
# ─────────────────────────────────────────────────────────────────────────────

class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    context_limit: int = Field(default=10, ge=1, le=50)


class AskResponse(BaseModel):
    question: str
    answer: str
    evidence: List[EvidenceItem] = []
    call_path: Optional[List[str]] = None
    relevant_files: List[str] = []
    confidence: float
    verification_status: VerificationStatusEnum
    intent_type: Optional[str] = None
    graph_data: Optional[Dict[str, Any]] = None


class SliceRequest(BaseModel):
    criterion: str = Field(..., description="Function name, variable, or feature to slice on")
    slice_type: str = Field(default="forward", description="forward, backward, feature, function")


class SliceResponse(BaseModel):
    criterion: str
    slice_type: str
    relevant_files: List[str] = []
    relevant_functions: List[str] = []
    dependency_path: List[str] = []
    source_lines: List[Dict[str, Any]] = []
    explanation: Optional[str] = None
    visualization_data: Optional[Dict[str, Any]] = None


class TraceRequest(BaseModel):
    source: str = Field(..., description="Requirement text or code entity")
    source_type: str = Field(default="code", description="requirement or code")
    direction: str = Field(default="forward", description="forward (req->code) or backward (code->req)")


class TraceResponse(BaseModel):
    source: str
    links: List[Dict[str, Any]] = []
    path: List[str] = []
    explanation: Optional[str] = None
    verification_status: VerificationStatusEnum
    confidence: float


class ImpactRequest(BaseModel):
    entity: str = Field(..., description="Function, class, or file to analyze")
    entity_type: str = Field(default="function")


class ImpactResponse(BaseModel):
    entity: str
    affected_callers: List[str] = []
    affected_callees: List[str] = []
    affected_classes: List[str] = []
    affected_apis: List[str] = []
    affected_tests: List[str] = []
    affected_files: List[str] = []
    evidence_path: List[str] = []
    explanation: Optional[str] = None


class UMLRequest(BaseModel):
    diagram_type: str = Field(default="class", description="class, sequence, dependency, architecture")
    scope: Optional[str] = None  # file path or module name to scope


class UMLResponse(BaseModel):
    diagram_type: str
    content: str  # Mermaid diagram content
    format: str = "mermaid"
    is_verified: bool = False
    scope: Optional[str] = None


class DocumentationRequest(BaseModel):
    doc_type: str = Field(default="project", description="project, module, api, architecture")
    scope: Optional[str] = None


class DocumentationResponse(BaseModel):
    doc_type: str
    content: str
    format: str = "markdown"
    sections: Optional[List[str]] = None


# ─────────────────────────────────────────────────────────────────────────────
# Overview / Dashboard
# ─────────────────────────────────────────────────────────────────────────────

class ProjectOverview(BaseModel):
    project: ProjectResponse
    file_tree: Optional[List[FileTreeNode]] = None
    language_distribution: Optional[Dict[str, float]] = None
    top_modules: Optional[List[str]] = None
    detected_patterns: Optional[List[str]] = None
    architecture_summary: Optional[str] = None
    executive_summary: Optional[str] = None
    tech_stack: Optional[List[str]] = None


class AnalysisError(BaseModel):
    component: str
    message: str
    severity: str = "WARNING"
    affected_files: Optional[List[str]] = None
    fallback: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Generic response wrapper
# ─────────────────────────────────────────────────────────────────────────────

class APIResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None
    data: Optional[Any] = None
    errors: Optional[List[AnalysisError]] = None
