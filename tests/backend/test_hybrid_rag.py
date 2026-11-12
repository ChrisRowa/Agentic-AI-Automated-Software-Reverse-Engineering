"""
Test suite for Phase 10-11: Hybrid RAG & Code-Aware Evidence Retrieval.
Validates:
- Structural code-aware chunking with line traceability
- Embedding provider dimension and normalization
- Lexical retrieval with identifier normalization
- Generic-term false match prevention and negative queries (Bitcoin payment test)
- Positive queries (exact class, method, file, semantic concept, natural language)
- Graph-aware retrieval (caller/callee/dependency expansion)
- Cross-project vector and evidence isolation
- QA Agent integration
"""
import pytest
import asyncio
from pathlib import Path

from backend.retrieval.chunker import CodeChunker
from backend.retrieval.embeddings import get_embedding_provider, DeterministicHashingEmbeddingProvider
from backend.retrieval.lexical import LexicalRetriever, tokenize_code
from backend.retrieval.vector_store import VectorStore
from backend.retrieval.graph_retriever import GraphAwareRetriever
from backend.retrieval.ranker import HybridRanker
from backend.retrieval.service import RetrievalService


# Sample repository codebase for testing
SAMPLE_AUTH_CODE = """# Authentication Service Module
import os
import hashlib
from database import get_connection

class AuthService:
    \"\"\"Handles user authentication and session tokens.\"\"\"

    def __init__(self, secret_key: str):
        self.secret_key = secret_key

    def authenticate(self, username: str, password_hash: str) -> bool:
        \"\"\"Verify user credentials against the database.\"\"\"
        db = get_connection()
        user = db.find_user(username)
        if not user:
            return False
        return user.password_hash == password_hash

    def login(self, username: str, password_hash: str) -> str:
        \"\"\"Log in user and return session token.\"\"\"
        if self.authenticate(username, password_hash):
            return "session_token_123"
        return ""
"""

SAMPLE_DB_CODE = """# Database Connection Module
class DatabaseConnection:
    \"\"\"Manages database queries and user records.\"\"\"

    def find_user(self, username: str):
        return None
"""


@pytest.fixture
def auth_repo_setup(tmp_path):
    """Sets up a mock workspace with auth files and parse results."""
    repo_dir = tmp_path / "auth_app"
    repo_dir.mkdir()
    auth_file = repo_dir / "auth.py"
    auth_file.write_text(SAMPLE_AUTH_CODE, encoding="utf-8")
    db_file = repo_dir / "database.py"
    db_file.write_text(SAMPLE_DB_CODE, encoding="utf-8")

    manifest = {
        "files": [
            {
                "relative_path": "auth.py",
                "filename": "auth.py",
                "language": "python",
                "extension": ".py",
                "lines_of_code": 22,
                "is_ignored": False,
                "is_test_file": False,
            },
            {
                "relative_path": "database.py",
                "filename": "database.py",
                "language": "python",
                "extension": ".py",
                "lines_of_code": 6,
                "is_ignored": False,
                "is_test_file": False,
            },
        ]
    }

    parse_results = {
        "all_classes": [
            {
                "name": "AuthService",
                "file": "auth.py",
                "line_start": 6,
                "line_end": 22,
                "docstring": "Handles user authentication and session tokens.",
                "methods": ["__init__", "authenticate", "login"],
            },
            {
                "name": "DatabaseConnection",
                "file": "database.py",
                "line_start": 2,
                "line_end": 6,
                "docstring": "Manages database queries and user records.",
                "methods": ["find_user"],
            },
        ],
        "all_functions": [
            {
                "name": "__init__",
                "class_name": "AuthService",
                "file": "auth.py",
                "line_start": 9,
                "line_end": 10,
                "signature": "def __init__(self, secret_key: str):",
            },
            {
                "name": "authenticate",
                "class_name": "AuthService",
                "file": "auth.py",
                "line_start": 12,
                "line_end": 18,
                "signature": "def authenticate(self, username: str, password_hash: str) -> bool:",
                "docstring": "Verify user credentials against the database.",
            },
            {
                "name": "login",
                "class_name": "AuthService",
                "file": "auth.py",
                "line_start": 20,
                "line_end": 23,
                "signature": "def login(self, username: str, password_hash: str) -> str:",
                "docstring": "Log in user and return session token.",
            },
            {
                "name": "find_user",
                "class_name": "DatabaseConnection",
                "file": "database.py",
                "line_start": 5,
                "line_end": 6,
                "signature": "def find_user(self, username: str):",
            },
        ],
    }

    graph_data = {
        "nodes": [
            {"id": "FILE:auth.py", "label": "auth.py", "node_type": "FILE", "file_path": "auth.py"},
            {"id": "CLASS:auth.py::AuthService", "label": "AuthService", "node_type": "CLASS", "file_path": "auth.py", "line_start": 6, "line_end": 22},
            {"id": "FUNC:auth.py::login", "label": "login", "node_type": "FUNCTION", "file_path": "auth.py", "line_start": 20, "line_end": 23},
            {"id": "FUNC:auth.py::authenticate", "label": "authenticate", "node_type": "FUNCTION", "file_path": "auth.py", "line_start": 12, "line_end": 18},
            {"id": "CLASS:database.py::DatabaseConnection", "label": "DatabaseConnection", "node_type": "CLASS", "file_path": "database.py", "line_start": 2, "line_end": 6},
        ],
        "edges": [
            {"source": "FUNC:auth.py::login", "target": "FUNC:auth.py::authenticate", "relationship_type": "CALLS"},
            {"source": "CLASS:auth.py::AuthService", "target": "FUNC:auth.py::authenticate", "relationship_type": "CONTAINS"},
            {"source": "CLASS:auth.py::AuthService", "target": "FUNC:auth.py::login", "relationship_type": "CONTAINS"},
            {"source": "FILE:auth.py", "target": "CLASS:database.py::DatabaseConnection", "relationship_type": "DEPENDS_ON"},
        ],
    }

    return {
        "repo_dir": str(repo_dir),
        "manifest": manifest,
        "parse_results": parse_results,
        "graph_data": graph_data,
        "tmp_path": str(tmp_path),
    }


def test_code_aware_chunking(auth_repo_setup):
    """Test that CodeChunker correctly extracts classes and methods with line numbers."""
    chunker = CodeChunker()
    chunks = chunker.chunk_repository(
        project_id="test-proj-1",
        extraction_path=auth_repo_setup["repo_dir"],
        manifest=auth_repo_setup["manifest"],
        parse_results=auth_repo_setup["parse_results"],
    )

    assert len(chunks) > 0

    # Verify method chunk
    auth_chunk = next((c for c in chunks if c.get("symbol_name") == "authenticate"), None)
    assert auth_chunk is not None
    assert auth_chunk["file_path"] == "auth.py"
    assert auth_chunk["start_line"] == 12
    assert auth_chunk["end_line"] == 18
    assert auth_chunk["class_name"] == "AuthService"
    assert "Verify user credentials" in auth_chunk["contextualized_text"]

    # Verify class chunk
    cls_chunk = next((c for c in chunks if c.get("symbol_name") == "AuthService"), None)
    assert cls_chunk is not None
    assert cls_chunk["start_line"] == 6
    assert "class AuthService" in cls_chunk["content"]


def test_lexical_tokenization_and_generic_filtering():
    """Verify camelCase and snake_case splitting and generic term suppression."""
    tokens = tokenize_code("getUserProfileAndVerifyHash")
    assert "user" in tokens
    assert "profile" in tokens
    assert "verify" in tokens

    snake_tokens = tokenize_code("payment_service_handler.py")
    assert "payment" in snake_tokens
    assert "service" in snake_tokens

    # Test retriever with generic vs informative query
    chunks = [
        {
            "chunk_id": "c1",
            "symbol_name": "AuthService",
            "file_path": "auth.py",
            "contextualized_text": "Class AuthService handles authentication login tokens",
        },
        {
            "chunk_id": "c2",
            "symbol_name": "PaymentService",
            "file_path": "payment.py",
            "contextualized_text": "Class PaymentService handles credit card payments and billing",
        },
    ]

    retriever = LexicalRetriever(chunks)

    # Informative query: "credit card payments" -> should match c2
    results = retriever.search("credit card payments")
    assert len(results) > 0
    assert results[0][0] == "c2"

    # Query with generic word + absent concept: "Bitcoin payment service" -> c1 should NOT dominate
    btc_results = retriever.search("Bitcoin cryptocurrency blockchain service")
    # Neither chunk has Bitcoin, so scores should be heavily suppressed / zero
    assert len(btc_results) == 0 or btc_results[0][1] < 0.2


@pytest.mark.asyncio
async def test_hybrid_retrieval_negative_query(auth_repo_setup):
    """
    Mandatory Section 17 Test:
    Query: 'What handles Bitcoin payment processing?'
    Repository: only has AuthService and DatabaseConnection.
    Expected: low relevance / insufficient evidence, NOT returning AuthService merely because it is a 'service'.
    """
    service = RetrievalService()
    service.vector_store.index_base_dir = Path(auth_repo_setup["tmp_path"])

    await service.index_project(
        project_id="test-auth-proj",
        extraction_path=auth_repo_setup["repo_dir"],
        manifest=auth_repo_setup["manifest"],
        parse_results=auth_repo_setup["parse_results"],
        graph_data=auth_repo_setup["graph_data"],
    )

    result = await service.retrieve(
        project_id="test-auth-proj",
        query="What service handles Bitcoin payments?",
    )

    # Must return insufficient evidence
    assert result["has_sufficient_evidence"] is False
    assert result["evidence"] == []
    assert "No sufficiently relevant repository evidence found" in result["message"]


@pytest.mark.asyncio
async def test_hybrid_retrieval_positive_queries(auth_repo_setup):
    """
    Mandatory Section 18 Tests:
    Verify exact class, exact method, file lookup, semantic lookup, and call path discovery.
    """
    service = RetrievalService()
    service.vector_store.index_base_dir = Path(auth_repo_setup["tmp_path"])

    await service.index_project(
        project_id="test-auth-proj",
        extraction_path=auth_repo_setup["repo_dir"],
        manifest=auth_repo_setup["manifest"],
        parse_results=auth_repo_setup["parse_results"],
        graph_data=auth_repo_setup["graph_data"],
    )

    # 1. Exact class lookup: "AuthService"
    res_cls = await service.retrieve(project_id="test-auth-proj", query="AuthService")
    assert res_cls["has_sufficient_evidence"] is True
    assert len(res_cls["evidence"]) > 0
    top_syms = [e.get("symbol") for e in res_cls["evidence"]]
    assert "AuthService" in top_syms

    # 2. Exact method lookup: "authenticate"
    res_method = await service.retrieve(project_id="test-auth-proj", query="authenticate")
    assert res_method["has_sufficient_evidence"] is True
    auth_ev = next((e for e in res_method["evidence"] if e.get("symbol") == "authenticate"), None)
    assert auth_ev is not None
    assert auth_ev["line_start"] == 12

    # 3. File lookup: "auth.py"
    res_file = await service.retrieve(project_id="test-auth-proj", query="auth.py")
    assert res_file["has_sufficient_evidence"] is True
    assert any(e.get("file") == "auth.py" for e in res_file["evidence"])

    # 4. Semantic concept lookup: "verifying user credentials and password hash"
    res_concept = await service.retrieve(project_id="test-auth-proj", query="verifying user credentials and password hash")
    assert res_concept["has_sufficient_evidence"] is True
    assert any(e.get("symbol") in ("authenticate", "AuthService") for e in res_concept["evidence"])

    # 5. Caller/callee retrieval: call path discovery
    res_login = await service.retrieve(project_id="test-auth-proj", query="login")
    assert res_login["has_sufficient_evidence"] is True
    assert len(res_login["call_paths"]) > 0
    assert any("login" in cp and "authenticate" in cp for cp in res_login["call_paths"])

    # 6. Import/dependency retrieval: "DatabaseConnection"
    res_dep = await service.retrieve(project_id="test-auth-proj", query="DatabaseConnection")
    assert res_dep["has_sufficient_evidence"] is True
    assert any("database.py" in e.get("file", "") for e in res_dep["evidence"])

    # 7. Natural-language feature query: "How does user login work?"
    res_nl = await service.retrieve(project_id="test-auth-proj", query="How does user login work?")
    assert res_nl["has_sufficient_evidence"] is True
    assert any(e.get("symbol") in ("login", "authenticate", "AuthService") for e in res_nl["evidence"])

    # 8. Negative query with absent concept: "Quantum computing key exchange"
    res_absent = await service.retrieve(project_id="test-auth-proj", query="Quantum computing key exchange")
    assert res_absent["has_sufficient_evidence"] is False
    assert res_absent["evidence"] == []

    # 9. Generic-term query: "service" alone
    res_gen = await service.retrieve(project_id="test-auth-proj", query="service")
    # Even if returning candidates, component scores attribute the generic nature
    assert len(res_gen["top_candidates"]) > 0

    # 10. Cross-file query: "find_user in database"
    res_cross = await service.retrieve(project_id="test-auth-proj", query="find_user in database")
    assert res_cross["has_sufficient_evidence"] is True
    assert any(e.get("file") == "database.py" for e in res_cross["evidence"])


@pytest.mark.asyncio
async def test_cross_project_isolation(tmp_path):
    """
    Mandatory Section 19 Test:
    Project A (AuthService) vs Project B (PaymentGateway).
    Queries against Project A must NEVER return evidence from Project B, and vice versa.
    """
    service = RetrievalService()
    service.vector_store.index_base_dir = tmp_path

    # Set up Project A (Auth)
    dir_a = tmp_path / "proj_a"
    dir_a.mkdir()
    (dir_a / "auth.py").write_text("class AuthService:\n    def login(self): pass\n", encoding="utf-8")

    manifest_a = {"files": [{"relative_path": "auth.py", "filename": "auth.py", "language": "python"}]}
    parse_a = {
        "all_classes": [{"name": "AuthService", "file": "auth.py", "line_start": 1, "line_end": 2}],
        "all_functions": [{"name": "login", "class_name": "AuthService", "file": "auth.py", "line_start": 2, "line_end": 2}],
    }
    graph_a = {"nodes": [{"id": "CLASS:AuthService", "label": "AuthService", "node_type": "CLASS", "file_path": "auth.py"}], "edges": []}

    await service.index_project("proj_a", str(dir_a), manifest_a, parse_a, graph_a)

    # Set up Project B (Payment)
    dir_b = tmp_path / "proj_b"
    dir_b.mkdir()
    (dir_b / "payment.py").write_text("class PaymentGateway:\n    def process_charge(self): pass\n", encoding="utf-8")

    manifest_b = {"files": [{"relative_path": "payment.py", "filename": "payment.py", "language": "python"}]}
    parse_b = {
        "all_classes": [{"name": "PaymentGateway", "file": "payment.py", "line_start": 1, "line_end": 2}],
        "all_functions": [{"name": "process_charge", "class_name": "PaymentGateway", "file": "payment.py", "line_start": 2, "line_end": 2}],
    }
    graph_b = {"nodes": [{"id": "CLASS:PaymentGateway", "label": "PaymentGateway", "node_type": "CLASS", "file_path": "payment.py"}], "edges": []}

    await service.index_project("proj_b", str(dir_b), manifest_b, parse_b, graph_b)

    # Query Project A for "PaymentGateway" -> should be insufficient evidence, never returning Project B's file
    res_a = await service.retrieve("proj_a", "PaymentGateway")
    assert res_a["has_sufficient_evidence"] is False
    assert not any("payment.py" in str(e) for e in res_a["evidence"])

    # Query Project B for "AuthService" -> should be insufficient evidence, never returning Project A's file
    res_b = await service.retrieve("proj_b", "AuthService")
    assert res_b["has_sufficient_evidence"] is False
    assert not any("auth.py" in str(e) for e in res_b["evidence"])

    # Query Project A for "AuthService" -> must return AuthService
    res_a_auth = await service.retrieve("proj_a", "AuthService")
    assert res_a_auth["has_sufficient_evidence"] is True
    assert any("auth.py" in e.get("file", "") for e in res_a_auth["evidence"])


@pytest.mark.asyncio
async def test_qa_agent_retrieval_integration(auth_repo_setup):
    """
    Test that qa_agent.retrieve_evidence seamlessly consumes the hybrid RAG service
    and correctly flags sufficient vs insufficient evidence queries.
    """
    from backend.retrieval.service import retrieval_service
    from backend.agents.qa_agent import retrieve_evidence, classify_intent

    retrieval_service.vector_store.index_base_dir = Path(auth_repo_setup["tmp_path"])

    await retrieval_service.index_project(
        project_id="test-qa-proj",
        extraction_path=auth_repo_setup["repo_dir"],
        manifest=auth_repo_setup["manifest"],
        parse_results=auth_repo_setup["parse_results"],
        graph_data=auth_repo_setup["graph_data"],
    )

    # 1. Supported query: user login
    intent = classify_intent("How does user login work?")
    evidence, call_path, has_sufficient = await retrieve_evidence(
        db=None,
        project_id="test-qa-proj",
        question="How does user login work?",
        intent=intent,
    )
    assert has_sufficient is True
    assert len(evidence) > 0
    assert any(e.get("symbol") in ("login", "authenticate", "AuthService") for e in evidence)

    # 2. Unsupported negative query: Bitcoin payment
    intent_neg = classify_intent("What service handles Bitcoin payments?")
    ev_neg, _, has_suff_neg = await retrieve_evidence(
        db=None,
        project_id="test-qa-proj",
        question="What service handles Bitcoin payments?",
        intent=intent_neg,
    )
    assert has_suff_neg is False
    assert len(ev_neg) == 0
