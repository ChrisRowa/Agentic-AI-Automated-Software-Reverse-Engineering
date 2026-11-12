"""
SQLAlchemy database models for the Reverse Engineering AI Platform.
Covers: projects, files, symbols, graphs, agents, evidence, verification, and more.
"""
from datetime import datetime
from typing import Optional
import uuid
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, JSON,
    ForeignKey, Enum as SAEnum, BigInteger, Index
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB, ARRAY
from sqlalchemy.types import TypeDecorator, CHAR

class GUID(TypeDecorator):
    """Platform-independent GUID/UUID type.
    Uses PostgreSQL's UUID type, otherwise uses CHAR(36).
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=False))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        return str(value) if value is not None else None

    def process_result_value(self, value, dialect):
        return str(value) if value is not None else None

JSON_TYPE = JSON().with_variant(JSONB, "postgresql")
from sqlalchemy.orm import DeclarativeBase, relationship
import enum


def new_uuid():
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class AnalysisStatus(str, enum.Enum):
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


class VerificationStatus(str, enum.Enum):
    VERIFIED = "VERIFIED"
    INFERRED = "INFERRED"
    UNCERTAIN = "UNCERTAIN"
    UNSUPPORTED = "UNSUPPORTED"


class SymbolType(str, enum.Enum):
    CLASS = "CLASS"
    FUNCTION = "FUNCTION"
    METHOD = "METHOD"
    VARIABLE = "VARIABLE"
    MODULE = "MODULE"
    API = "API"
    IMPORT = "IMPORT"
    CONSTANT = "CONSTANT"


class RelationshipType(str, enum.Enum):
    CONTAINS = "CONTAINS"
    IMPORTS = "IMPORTS"
    CALLS = "CALLS"
    DEPENDS_ON = "DEPENDS_ON"
    DEFINES = "DEFINES"
    INHERITS = "INHERITS"
    IMPLEMENTS = "IMPLEMENTS"
    READS = "READS"
    WRITES = "WRITES"
    USES = "USES"
    EXPOSES_API = "EXPOSES_API"
    ACCESSES_DATABASE = "ACCESSES_DATABASE"
    DOCUMENTS = "DOCUMENTS"
    IMPLEMENTS_REQUIREMENT = "IMPLEMENTS_REQUIREMENT"
    AFFECTS = "AFFECTS"
    DATA_FLOWS_TO = "DATA_FLOWS_TO"
    OVERRIDES = "OVERRIDES"


class NodeType(str, enum.Enum):
    REPOSITORY = "REPOSITORY"
    PROJECT = "PROJECT"
    FOLDER = "FOLDER"
    FILE = "FILE"
    MODULE = "MODULE"
    CLASS = "CLASS"
    FUNCTION = "FUNCTION"
    METHOD = "METHOD"
    VARIABLE = "VARIABLE"
    API = "API"
    DATABASE = "DATABASE"
    REQUIREMENT = "REQUIREMENT"
    DOCUMENTATION = "DOCUMENTATION"
    TEST = "TEST"
    FEATURE = "FEATURE"


# ─────────────────────────────────────────────────────────────────────────────
# Project / Repository
# ─────────────────────────────────────────────────────────────────────────────

class Project(Base):
    __tablename__ = "projects"

    id = Column(GUID, primary_key=True, default=new_uuid)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(SAEnum(AnalysisStatus), default=AnalysisStatus.QUEUED, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Upload info
    original_filename = Column(String(512), nullable=True)
    archive_path = Column(String(1024), nullable=True)
    workspace_path = Column(String(1024), nullable=True)
    archive_size_bytes = Column(BigInteger, nullable=True)
    file_count = Column(Integer, nullable=True)

    # Detection results
    primary_language = Column(String(100), nullable=True)
    detected_languages = Column(JSON_TYPE, nullable=True)  # {"Python": 60, "JS": 40}
    detected_frameworks = Column(JSON_TYPE, nullable=True)
    project_type = Column(String(100), nullable=True)  # web_app, library, cli, etc.

    # Stats
    total_files = Column(Integer, default=0)
    total_classes = Column(Integer, default=0)
    total_functions = Column(Integer, default=0)
    total_modules = Column(Integer, default=0)
    total_dependencies = Column(Integer, default=0)
    total_api_endpoints = Column(Integer, default=0)
    total_lines_of_code = Column(Integer, default=0)

    # Analysis metadata
    analysis_progress = Column(Float, default=0.0)  # 0-100
    error_message = Column(Text, nullable=True)
    git_available = Column(Boolean, default=False)
    git_branch = Column(String(255), nullable=True)
    git_commit_count = Column(Integer, nullable=True)

    # Relationships
    files = relationship("RepositoryFile", back_populates="project", cascade="all, delete-orphan")
    symbols = relationship("Symbol", back_populates="project", cascade="all, delete-orphan")
    graph_nodes = relationship("GraphNode", back_populates="project", cascade="all, delete-orphan")
    graph_edges = relationship("GraphEdge", back_populates="project", cascade="all, delete-orphan")
    analysis_runs = relationship("AnalysisRun", back_populates="project", cascade="all, delete-orphan")
    claims = relationship("Claim", back_populates="project", cascade="all, delete-orphan")
    generated_artifacts = relationship("GeneratedArtifact", back_populates="project", cascade="all, delete-orphan")
    trace_links = relationship("TraceLink", back_populates="project", cascade="all, delete-orphan")
    chunks = relationship("CodeChunk", back_populates="project", cascade="all, delete-orphan")


class RepositoryFile(Base):
    __tablename__ = "repository_files"

    id = Column(GUID, primary_key=True, default=new_uuid)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    relative_path = Column(String(2048), nullable=False)
    filename = Column(String(512), nullable=False)
    extension = Column(String(32), nullable=True)
    language = Column(String(64), nullable=True)
    size_bytes = Column(BigInteger, nullable=True)
    lines_of_code = Column(Integer, nullable=True)
    content_hash = Column(String(64), nullable=True)

    # Analysis
    is_test_file = Column(Boolean, default=False)
    is_config_file = Column(Boolean, default=False)
    is_documentation = Column(Boolean, default=False)
    is_ignored = Column(Boolean, default=False)
    module_name = Column(String(512), nullable=True)
    ai_summary = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="files")
    symbols = relationship("Symbol", back_populates="file", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_repo_files_project_path", "project_id", "relative_path"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Symbols (classes, functions, methods, variables)
# ─────────────────────────────────────────────────────────────────────────────

class Symbol(Base):
    __tablename__ = "symbols"

    id = Column(GUID, primary_key=True, default=new_uuid)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    file_id = Column(GUID, ForeignKey("repository_files.id", ondelete="CASCADE"), nullable=True)

    name = Column(String(512), nullable=False)
    qualified_name = Column(String(1024), nullable=True)  # module.ClassName.method_name
    symbol_type = Column(SAEnum(SymbolType), nullable=False)
    language = Column(String(64), nullable=True)

    # Source location
    line_start = Column(Integer, nullable=True)
    line_end = Column(Integer, nullable=True)
    column_start = Column(Integer, nullable=True)
    column_end = Column(Integer, nullable=True)

    # Code content
    signature = Column(Text, nullable=True)
    docstring = Column(Text, nullable=True)
    body_hash = Column(String(64), nullable=True)

    # Context
    parent_symbol_id = Column(GUID, ForeignKey("symbols.id"), nullable=True)
    parameters = Column(JSON_TYPE, nullable=True)  # [{"name": "x", "type": "int"}]
    return_type = Column(String(256), nullable=True)
    decorators = Column(JSON_TYPE, nullable=True)
    modifiers = Column(JSON_TYPE, nullable=True)  # static, public, async, etc.

    # AI analysis
    ai_summary = Column(Text, nullable=True)
    ai_complexity = Column(String(32), nullable=True)  # low/medium/high
    confidence = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="symbols")
    file = relationship("RepositoryFile", back_populates="symbols")
    children = relationship("Symbol", foreign_keys=[parent_symbol_id])

    __table_args__ = (
        Index("ix_symbols_project_name", "project_id", "name"),
        Index("ix_symbols_type", "project_id", "symbol_type"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Program Knowledge Graph
# ─────────────────────────────────────────────────────────────────────────────

class GraphNode(Base):
    __tablename__ = "graph_nodes"

    id = Column(GUID, primary_key=True, default=new_uuid)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    node_type = Column(SAEnum(NodeType), nullable=False)
    label = Column(String(512), nullable=False)
    qualified_name = Column(String(1024), nullable=True)

    # Source reference
    file_path = Column(String(2048), nullable=True)
    line_start = Column(Integer, nullable=True)
    line_end = Column(Integer, nullable=True)

    # Properties
    properties = Column(JSON_TYPE, nullable=True)
    ai_summary = Column(Text, nullable=True)
    language = Column(String(64), nullable=True)
    module = Column(String(512), nullable=True)

    # For embedding retrieval
    symbol_id = Column(GUID, ForeignKey("symbols.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    project = relationship("Project", back_populates="graph_nodes")

    __table_args__ = (
        Index("ix_graph_nodes_project_type", "project_id", "node_type"),
    )


class GraphEdge(Base):
    __tablename__ = "graph_edges"

    id = Column(GUID, primary_key=True, default=new_uuid)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    source_id = Column(GUID, ForeignKey("graph_nodes.id"), nullable=False)
    target_id = Column(GUID, ForeignKey("graph_nodes.id"), nullable=False)
    relationship_type = Column(SAEnum(RelationshipType), nullable=False)

    # Evidence
    evidence_file = Column(String(2048), nullable=True)
    evidence_line_start = Column(Integer, nullable=True)
    evidence_line_end = Column(Integer, nullable=True)
    evidence_type = Column(String(128), nullable=True)  # AST, CALL, IMPORT, etc.
    evidence_source = Column(String(128), nullable=True)  # tree-sitter, ast-module, etc.

    # Metadata
    weight = Column(Float, default=1.0)
    confidence = Column(Float, default=1.0)
    properties = Column(JSON_TYPE, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    project = relationship("Project", back_populates="graph_edges")
    source_node = relationship("GraphNode", foreign_keys=[source_id])
    target_node = relationship("GraphNode", foreign_keys=[target_id])

    __table_args__ = (
        Index("ix_graph_edges_project_type", "project_id", "relationship_type"),
        Index("ix_graph_edges_source", "source_id"),
        Index("ix_graph_edges_target", "target_id"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Agent / Analysis Runs
# ─────────────────────────────────────────────────────────────────────────────

class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id = Column(GUID, primary_key=True, default=new_uuid)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    agent_name = Column(String(128), nullable=False)
    status = Column(String(64), nullable=False, default="QUEUED")
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    input_data = Column(JSON_TYPE, nullable=True)
    output_data = Column(JSON_TYPE, nullable=True)
    error_message = Column(Text, nullable=True)
    tokens_used = Column(Integer, default=0)
    model_used = Column(String(128), nullable=True)
    duration_seconds = Column(Float, nullable=True)

    project = relationship("Project", back_populates="analysis_runs")


# ─────────────────────────────────────────────────────────────────────────────
# Claims & Evidence (Hallucination Prevention Core)
# ─────────────────────────────────────────────────────────────────────────────

class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(GUID, primary_key=True, default=new_uuid)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    file_path = Column(String(2048), nullable=False)
    line_start = Column(Integer, nullable=True)
    line_end = Column(Integer, nullable=True)
    evidence_type = Column(String(128), nullable=False)  # CALL, IMPORT, AST, DEPENDENCY
    content_snippet = Column(Text, nullable=True)
    source_tool = Column(String(128), nullable=True)  # tree-sitter, ast, networkx
    created_at = Column(DateTime, default=datetime.utcnow)


class Claim(Base):
    __tablename__ = "claims"

    id = Column(GUID, primary_key=True, default=new_uuid)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    claim_text = Column(Text, nullable=False)
    claim_type = Column(String(128), nullable=True)  # dependency, call, behavior, etc.
    agent_source = Column(String(128), nullable=True)
    verification_status = Column(SAEnum(VerificationStatus), default=VerificationStatus.UNCERTAIN)
    confidence = Column(Float, default=0.0)
    evidence_ids = Column(JSON_TYPE, nullable=True)  # list of evidence IDs
    context = Column(JSON_TYPE, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="claims")


class VerificationResult(Base):
    __tablename__ = "verification_results"

    id = Column(GUID, primary_key=True, default=new_uuid)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    claim_id = Column(GUID, ForeignKey("claims.id"), nullable=True)
    verification_method = Column(String(128), nullable=True)
    result_status = Column(SAEnum(VerificationStatus), nullable=False)
    supporting_evidence = Column(JSON_TYPE, nullable=True)
    contradicting_evidence = Column(JSON_TYPE, nullable=True)
    explanation = Column(Text, nullable=True)
    confidence = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)


# ─────────────────────────────────────────────────────────────────────────────
# Slices & Traceability
# ─────────────────────────────────────────────────────────────────────────────

class ProgramSlice(Base):
    __tablename__ = "program_slices"

    id = Column(GUID, primary_key=True, default=new_uuid)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    slice_type = Column(String(64), nullable=False)  # forward, backward, feature, function
    criterion = Column(String(512), nullable=False)  # what was sliced on
    relevant_nodes = Column(JSON_TYPE, nullable=True)  # node IDs
    relevant_files = Column(JSON_TYPE, nullable=True)
    relevant_functions = Column(JSON_TYPE, nullable=True)
    dependency_path = Column(JSON_TYPE, nullable=True)
    source_lines = Column(JSON_TYPE, nullable=True)
    explanation = Column(Text, nullable=True)
    visualization_data = Column(JSON_TYPE, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class TraceLink(Base):
    __tablename__ = "trace_links"

    id = Column(GUID, primary_key=True, default=new_uuid)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    source_type = Column(String(64), nullable=False)  # requirement, code, behavior, feature
    source_id = Column(String(512), nullable=False)
    target_type = Column(String(64), nullable=False)
    target_id = Column(String(512), nullable=False)
    link_type = Column(String(64), nullable=False)  # forward, backward, inferred
    confidence = Column(Float, default=0.0)
    evidence_ids = Column(JSON_TYPE, nullable=True)
    path = Column(JSON_TYPE, nullable=True)  # the dependency path through the graph
    verification_status = Column(SAEnum(VerificationStatus), default=VerificationStatus.UNCERTAIN)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="trace_links")


# ─────────────────────────────────────────────────────────────────────────────
# Generated Artifacts
# ─────────────────────────────────────────────────────────────────────────────

class GeneratedArtifact(Base):
    __tablename__ = "generated_artifacts"

    id = Column(GUID, primary_key=True, default=new_uuid)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    artifact_type = Column(String(128), nullable=False)  # uml_class, uml_sequence, report, doc, etc.
    title = Column(String(512), nullable=True)
    content = Column(Text, nullable=True)
    format = Column(String(64), nullable=True)  # mermaid, plantuml, markdown, json, html
    artifact_metadata = Column("metadata", JSON_TYPE, nullable=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="generated_artifacts")


# ─────────────────────────────────────────────────────────────────────────────
# Repository Semantic Ontology (research addition #18)
# ─────────────────────────────────────────────────────────────────────────────

class SemanticOntology(Base):
    __tablename__ = "semantic_ontologies"

    id = Column(GUID, primary_key=True, default=new_uuid)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True)
    domain_terms = Column(JSON_TYPE, nullable=True)       # {term: frequency}
    class_concepts = Column(JSON_TYPE, nullable=True)
    api_concepts = Column(JSON_TYPE, nullable=True)
    business_concepts = Column(JSON_TYPE, nullable=True)
    naming_patterns = Column(JSON_TYPE, nullable=True)
    module_terminology = Column(JSON_TYPE, nullable=True)
    vocabulary = Column(JSON_TYPE, nullable=True)          # full vocabulary with embeddings
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ─────────────────────────────────────────────────────────────────────────────
# Error Tracking
# ─────────────────────────────────────────────────────────────────────────────

class AnalysisError(Base):
    __tablename__ = "analysis_errors"

    id = Column(GUID, primary_key=True, default=new_uuid)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    component = Column(String(128), nullable=False)
    message = Column(Text, nullable=False)
    severity = Column(String(32), default="WARNING")  # ERROR, WARNING, INFO
    affected_files = Column(JSON_TYPE, nullable=True)
    fallback_used = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ─────────────────────────────────────────────────────────────────────────────
# Code Chunks & Embeddings (Hybrid RAG Foundation)
# ─────────────────────────────────────────────────────────────────────────────

try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False
    Vector = None


class CodeChunk(Base):
    __tablename__ = "code_chunks"

    id = Column(GUID, primary_key=True, default=new_uuid)
    project_id = Column(GUID, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    file_id = Column(GUID, ForeignKey("repository_files.id", ondelete="SET NULL"), nullable=True)

    file_path = Column(String(2048), nullable=False)
    language = Column(String(64), nullable=True)
    symbol_name = Column(String(512), nullable=True)
    symbol_type = Column(String(64), nullable=True)
    class_name = Column(String(512), nullable=True)
    start_line = Column(Integer, nullable=False)
    end_line = Column(Integer, nullable=False)

    chunk_type = Column(String(64), nullable=False, default="code")  # function, class, file, module, doc
    content = Column(Text, nullable=False)
    contextualized_text = Column(Text, nullable=False)

    embedding = Column(Vector(384), nullable=True) if PGVECTOR_AVAILABLE and Vector is not None else Column(JSON_TYPE, nullable=True)
    chunk_metadata = Column("metadata", JSON_TYPE, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="chunks")

    __table_args__ = (
        Index("ix_code_chunks_project_id", "project_id"),
        Index("ix_code_chunks_file_path", "project_id", "file_path"),
        Index("ix_code_chunks_symbol", "project_id", "symbol_name"),
    )
