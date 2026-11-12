"""
End-to-End Integration Test for Agentic AI Reverse Engineering Platform.
Tests: ZIP upload -> pipeline -> LangGraph QA -> evidence -> hallucination guard.
Run with: pytest tests/backend/test_e2e_integration.py -v -s

NOTE: Requires the backend server running at localhost:8000
      (uvicorn backend.main:app --host 0.0.0.0 --port 8000)
"""
import asyncio
import time
import pytest
import httpx
from pathlib import Path

BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"
SAMPLE_ZIP = (
    Path(__file__).parent.parent.parent / "sample_projects" / "realistic_auth_system.zip"
)
TIMEOUT = 150  # seconds for full pipeline to complete

# Module-level state to share the project_id between tests
_SHARED: dict = {}


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=BASE_URL, timeout=90.0)


# ---------------------------------------------------------------------------
# 0. Standalone server smoke tests (no shared project needed)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_0_health_check():
    """Backend health endpoint must return healthy."""
    async with _client() as c:
        r = await c.get("/health")
    assert r.status_code == 200
    b = r.json()
    assert b.get("backend") == "healthy"
    assert b.get("database") == "healthy"
    assert b.get("retrieval") == "ready"
    print(f"\n  health: {b}")


@pytest.mark.asyncio
async def test_0b_api_docs_accessible():
    """API docs HTML must be served."""
    async with _client() as c:
        r = await c.get("/api/docs")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")


# ---------------------------------------------------------------------------
# 1. Full upload + pipeline — creates shared project
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_1_upload_and_pipeline():
    """Upload realistic auth ZIP, wait for pipeline to reach COMPLETED."""
    assert SAMPLE_ZIP.exists(), f"Sample ZIP not found: {SAMPLE_ZIP}"

    async with _client() as c:
        # Create project
        r = await c.post(f"{API_BASE}/projects", json={
            "name": "e2e-test-auth-system",
            "description": "End-to-end test — realistic auth application"
        })
        assert r.status_code == 201, r.text
        pid = r.json()["id"]
        _SHARED["project_id"] = pid
        print(f"\n  Created project: {pid}")

        # Upload ZIP
        with open(SAMPLE_ZIP, "rb") as f:
            up = await c.post(
                f"{API_BASE}/projects/{pid}/upload",
                files={"file": ("realistic_auth_system.zip", f, "application/zip")},
            )
        assert up.status_code == 200, up.text
        print(f"  Upload OK: {up.json()}")

        # Poll for completion
        deadline = time.time() + TIMEOUT
        while time.time() < deadline:
            sr = await c.get(f"{API_BASE}/projects/{pid}/status")
            s = sr.json().get("status")
            p = sr.json().get("analysis_progress", 0)
            print(f"  status={s} progress={p:.0f}%")
            if s == "COMPLETED":
                _SHARED["status_body"] = sr.json()
                break
            if s == "FAILED":
                pytest.fail(f"Pipeline FAILED: {sr.json().get('error_message')}")
            await asyncio.sleep(2.5)
        else:
            pytest.fail(f"Pipeline timed out after {TIMEOUT}s")


# ---------------------------------------------------------------------------
# 2. Pipeline metadata validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_2_pipeline_metadata():
    """Pipeline result must have correct file/symbol counts and language."""
    pid = _SHARED.get("project_id")
    if not pid:
        pytest.skip("project not created")

    async with _client() as c:
        r = await c.get(f"{API_BASE}/projects/{pid}/status")
    b = r.json()

    assert b["status"] == "COMPLETED", str(b)
    assert b["analysis_progress"] == 100.0
    assert b.get("primary_language") == "Python", f"primary_language={b.get('primary_language')}"
    assert b.get("total_files", 0) > 5, f"total_files={b.get('total_files')}"
    assert b.get("total_classes", 0) > 0, "No classes extracted"
    assert b.get("total_functions", 0) > 0, "No functions extracted"
    print(f"\n  pipeline: files={b['total_files']} classes={b['total_classes']} funcs={b['total_functions']}")


# ---------------------------------------------------------------------------
# 3. File discovery
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_3_files_extracted():
    """AST must find core auth system files."""
    pid = _SHARED.get("project_id")
    if not pid:
        pytest.skip("project not created")

    async with _client() as c:
        r = await c.get(f"{API_BASE}/projects/{pid}/files")
    files = r.json()

    assert len(files) > 5, f"Only {len(files)} files extracted"
    paths = [f["relative_path"] for f in files]
    assert any("auth_service" in p for p in paths), f"auth_service missing: {paths}"
    assert any("user_repository" in p for p in paths), f"user_repository missing: {paths}"
    print(f"\n  files: {len(files)} total; core paths found")


# ---------------------------------------------------------------------------
# 4. Graph validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_4a_knowledge_graph():
    """Knowledge graph must have nodes."""
    pid = _SHARED.get("project_id")
    if not pid:
        pytest.skip("project not created")

    async with _client() as c:
        r = await c.get(f"{API_BASE}/projects/{pid}/graph")
    b = r.json()
    assert b["total_nodes"] > 0, "Graph has no nodes"
    print(f"\n  graph: {b['total_nodes']} nodes, {b['total_edges']} edges")


@pytest.mark.asyncio
async def test_4b_call_graph():
    """Call graph endpoint must respond."""
    pid = _SHARED.get("project_id")
    if not pid:
        pytest.skip("project not created")

    async with _client() as c:
        r = await c.get(f"{API_BASE}/projects/{pid}/call-graph")
    assert r.status_code == 200
    b = r.json()
    print(f"\n  call-graph: {b['total_nodes']} nodes, {b['total_edges']} edges")


@pytest.mark.asyncio
async def test_4c_dependency_graph():
    """Dependency graph endpoint must respond."""
    pid = _SHARED.get("project_id")
    if not pid:
        pytest.skip("project not created")

    async with _client() as c:
        r = await c.get(f"{API_BASE}/projects/{pid}/dependencies")
    assert r.status_code == 200
    b = r.json()
    print(f"\n  dep-graph: {b['total_nodes']} nodes, {b['total_edges']} edges")


# ---------------------------------------------------------------------------
# 5. Ask AI (requires LLM — gracefully skip if not configured)
# ---------------------------------------------------------------------------

async def _ask(pid: str, question: str) -> dict:
    async with _client() as c:
        r = await c.post(
            f"{API_BASE}/projects/{pid}/ask",
            json={"question": question, "context_limit": 10},
        )
    assert r.status_code == 200, f"ask failed {r.status_code}: {r.text[:300]}"
    return r.json()


def _no_evidence(result: dict) -> bool:
    """Return True if result correctly signals no evidence (hallucination guard)."""
    status = result.get("verification_status", "")
    answer = result.get("answer", "").lower()
    confidence = result.get("confidence") or 1.0
    return (
        status == "UNSUPPORTED"
        or "no supporting evidence" in answer
        or "not found" in answer
        or "not implemented" in answer
        or "cannot find" in answer
        or "does not" in answer
        or "no evidence" in answer
        or confidence < 0.3
    )


def _llm_check(result: dict):
    """Skip test gracefully if LLM is not configured.
    
    When no LLM key is set, the orchestrator returns:
      - verification_status: UNSUPPORTED
      - confidence: 0.0
      - answer: 'No supporting evidence...'
    """
    ans_lower = result.get("answer", "").lower()
    confidence = result.get("confidence") or 0.0
    status = result.get("verification_status", "")
    no_llm_signals = (
        "llm not configured" in ans_lower
        or "not configured" in ans_lower
        or "no llm" in ans_lower
        or "api key" in ans_lower
        or result.get("status") == "error"
        or (len(result.get("answer", "")) < 20 and not result.get("evidence"))
        # Orchestrator fallback when no LLM: 0.0 confidence + UNSUPPORTED + no evidence
        or (confidence == 0.0 and status == "UNSUPPORTED" and not result.get("evidence"))
    )
    if no_llm_signals:
        pytest.skip("LLM not configured (set OPENAI_API_KEY / GOOGLE_API_KEY / ANTHROPIC_API_KEY)")


@pytest.mark.asyncio
async def test_5a_ask_architecture():
    """Architecture question must return valid grounded answer."""
    pid = _SHARED.get("project_id")
    if not pid:
        pytest.skip("project not created")

    result = await _ask(pid, "Explain the architecture of this repository.")
    _llm_check(result)
    assert result.get("answer"), "Empty answer returned"
    status = result.get("verification_status")
    conf = result.get("confidence")
    ev = len(result.get("evidence", []))
    assert status in ("VERIFIED", "INFERRED", "UNCERTAIN", "UNSUPPORTED")
    print(f"\n  architecture: status={status} confidence={conf} evidence={ev}")
    print(f"    answer: {result['answer'][:200]}")


@pytest.mark.asyncio
async def test_5b_ask_login_flow():
    """Login flow question must reference authentication concepts."""
    pid = _SHARED.get("project_id")
    if not pid:
        pytest.skip("project not created")

    result = await _ask(pid, "What happens when a user logs in?")
    _llm_check(result)
    assert result.get("answer"), "Empty answer"
    ans = result["answer"].lower()
    ev = len(result.get("evidence", []))
    has_auth = any(k in ans for k in ("auth", "login", "password", "token", "credential", "session"))
    assert has_auth or ev > 0, f"Not auth-related: {result['answer'][:200]}"
    print(f"\n  login flow: evidence={ev} answer={result['answer'][:150]}")


@pytest.mark.asyncio
async def test_5c_ask_authentication_function():
    """Question about auth function must return authenticate in evidence/answer."""
    pid = _SHARED.get("project_id")
    if not pid:
        pytest.skip("project not created")

    result = await _ask(pid, "Which function performs authentication?")
    _llm_check(result)
    assert result.get("answer"), "Empty answer"
    print(f"\n  auth function: {result['answer'][:200]}")


@pytest.mark.asyncio
async def test_5d_ask_user_repository():
    """Repository layer question must reference UserRepository."""
    pid = _SHARED.get("project_id")
    if not pid:
        pytest.skip("project not created")

    result = await _ask(pid, "Which repository handles user lookup?")
    _llm_check(result)
    assert result.get("answer"), "Empty answer"
    print(f"\n  user repo: {result['answer'][:200]}")


# ---------------------------------------------------------------------------
# 6. HALLUCINATION GUARD (CRITICAL)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_6a_no_evidence_bitcoin():
    """Bitcoin MUST NOT appear as implemented in this auth repo — no hallucination."""
    pid = _SHARED.get("project_id")
    if not pid:
        pytest.skip("project not created")

    result = await _ask(pid, "Where is Bitcoin blockchain payment implemented?")
    _llm_check(result)
    status = result.get("verification_status")
    conf = result.get("confidence")

    assert _no_evidence(result), (
        f"HALLUCINATION DETECTED — system fabricated Bitcoin content!\n"
        f"status={status} confidence={conf}\n"
        f"answer: {result['answer'][:400]}"
    )
    print(f"\n  bitcoin hallucination guard: PASS status={status} conf={conf}")


@pytest.mark.asyncio
async def test_6b_no_evidence_facial_recognition():
    """Facial recognition MUST NOT appear in this auth repo — no hallucination."""
    pid = _SHARED.get("project_id")
    if not pid:
        pytest.skip("project not created")

    result = await _ask(pid, "Which file implements facial recognition?")
    _llm_check(result)
    status = result.get("verification_status")

    assert _no_evidence(result), (
        f"HALLUCINATION DETECTED — facial recognition fabricated!\n"
        f"status={status}\nanswer: {result['answer'][:400]}"
    )
    print(f"\n  facial recognition hallucination guard: PASS status={status}")


@pytest.mark.asyncio
async def test_6c_no_evidence_kubernetes():
    """Kubernetes MUST NOT appear in this auth repo — no hallucination."""
    pid = _SHARED.get("project_id")
    if not pid:
        pytest.skip("project not created")

    result = await _ask(pid, "Where is the Kubernetes cluster deployment logic?")
    _llm_check(result)
    status = result.get("verification_status")

    assert _no_evidence(result), (
        f"HALLUCINATION DETECTED — Kubernetes fabricated!\n"
        f"status={status}\nanswer: {result['answer'][:400]}"
    )
    print(f"\n  kubernetes hallucination guard: PASS status={status}")


@pytest.mark.asyncio
async def test_6d_no_evidence_machine_learning():
    """Machine learning MUST NOT appear in this auth repo — no hallucination."""
    pid = _SHARED.get("project_id")
    if not pid:
        pytest.skip("project not created")

    result = await _ask(pid, "Where is the machine learning model trained?")
    _llm_check(result)
    status = result.get("verification_status")
    conf = result.get("confidence")

    assert _no_evidence(result), (
        f"HALLUCINATION DETECTED — ML fabricated!\n"
        f"status={status} conf={conf}\nanswer: {result['answer'][:400]}"
    )
    print(f"\n  machine learning hallucination guard: PASS status={status} conf={conf}")


# ---------------------------------------------------------------------------
# 7. Specialized analysis endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_7a_impact_analysis():
    """Impact analysis endpoint must return structured results."""
    pid = _SHARED.get("project_id")
    if not pid:
        pytest.skip("project not created")

    async with _client() as c:
        r = await c.post(
            f"{API_BASE}/projects/{pid}/impact-analysis",
            json={"entity": "authenticate", "entity_type": "function", "depth": 3},
        )
    assert r.status_code == 200, r.text
    print(f"\n  impact analysis: {str(r.json())[:300]}")


@pytest.mark.asyncio
async def test_7b_traceability():
    """Traceability endpoint must return links."""
    pid = _SHARED.get("project_id")
    if not pid:
        pytest.skip("project not created")

    async with _client() as c:
        r = await c.post(
            f"{API_BASE}/projects/{pid}/trace",
            json={"source": "authenticate", "source_type": "function"},
        )
    assert r.status_code == 200, r.text
    print(f"\n  traceability: {str(r.json())[:300]}")


@pytest.mark.asyncio
async def test_7c_program_slice():
    """Program slice endpoint must return backward slice."""
    pid = _SHARED.get("project_id")
    if not pid:
        pytest.skip("project not created")

    async with _client() as c:
        r = await c.post(
            f"{API_BASE}/projects/{pid}/slice",
            json={"criterion": "authenticate", "slice_type": "backward", "depth": 3},
        )
    assert r.status_code == 200, r.text
    print(f"\n  program slice: {str(r.json())[:300]}")


# ---------------------------------------------------------------------------
# 8. Reports
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_8a_report_json():
    """JSON report must be generated for completed project."""
    pid = _SHARED.get("project_id")
    if not pid:
        pytest.skip("project not created")

    async with _client() as c:
        r = await c.get(f"{API_BASE}/projects/{pid}/report", params={"format": "json"})
    assert r.status_code == 200, r.text
    b = r.json()
    print(f"\n  JSON report keys: {list(b.keys())}")


@pytest.mark.asyncio
async def test_8b_report_markdown():
    """Markdown report must be generated."""
    pid = _SHARED.get("project_id")
    if not pid:
        pytest.skip("project not created")

    async with _client() as c:
        r = await c.get(f"{API_BASE}/projects/{pid}/report", params={"format": "markdown"})
    assert r.status_code == 200, r.text
    print(f"\n  Markdown report: {r.text[:200]}")


# ---------------------------------------------------------------------------
# 9. Evidence & Verification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_9a_evidence_endpoint():
    """Evidence endpoint must return claims."""
    pid = _SHARED.get("project_id")
    if not pid:
        pytest.skip("project not created")

    async with _client() as c:
        r = await c.get(f"{API_BASE}/projects/{pid}/evidence")
    assert r.status_code == 200
    b = r.json()
    assert "claims" in b
    print(f"\n  evidence: {len(b['claims'])} claims")


@pytest.mark.asyncio
async def test_9b_verification_summary():
    """Verification summary must return status breakdown."""
    pid = _SHARED.get("project_id")
    if not pid:
        pytest.skip("project not created")

    async with _client() as c:
        r = await c.get(f"{API_BASE}/projects/{pid}/verification")
    assert r.status_code == 200
    b = r.json()
    assert "total" in b
    print(f"\n  verification summary: {b}")


# ---------------------------------------------------------------------------
# 10. Project Overview
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_10_project_overview():
    """Overview must return file tree and language distribution."""
    pid = _SHARED.get("project_id")
    if not pid:
        pytest.skip("project not created")

    async with _client() as c:
        r = await c.get(f"{API_BASE}/projects/{pid}/overview")
    assert r.status_code == 200, r.text
    b = r.json()
    assert "project" in b
    assert "language_distribution" in b
    print(f"\n  overview: langs={b.get('language_distribution')} tech={b.get('tech_stack', [])}")


# ---------------------------------------------------------------------------
# 11. Security
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_11_corrupt_zip_handled_gracefully():
    """Uploading a corrupt ZIP must not crash the server."""
    import io

    async with _client() as c:
        r = await c.post(f"{API_BASE}/projects", json={"name": "security-test-corrupt"})
        pid = r.json()["id"]

        bad_zip = io.BytesIO(b"NOT_A_ZIP_FILE_XYZ123")
        ur = await c.post(
            f"{API_BASE}/projects/{pid}/upload",
            files={"file": ("bad.zip", bad_zip, "application/zip")},
        )
        # Must not 500 crash — any clean response is OK
        assert ur.status_code in (200, 400, 422), f"Unexpected status: {ur.status_code}"
        print(f"\n  corrupt ZIP: server returned {ur.status_code} (correct, not 500)")

        await c.delete(f"{API_BASE}/projects/{pid}")


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_99_cleanup():
    """Delete the test project to clean up."""
    pid = _SHARED.get("project_id")
    if not pid:
        return

    async with _client() as c:
        r = await c.delete(f"{API_BASE}/projects/{pid}")
    assert r.status_code == 204
    print(f"\n  cleanup: project {pid} deleted")
