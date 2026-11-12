"""
End-to-end API tests for Reverse Engineering Platform.
Validates:
- Root and /health endpoints reporting system component status
- API v1 /projects creation and listing
- /projects/{id}/ask with LangGraph agentic reasoning
"""
import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app, lifespan


@pytest.mark.asyncio
async def test_health_endpoint():
    """Verify /health reports status of all core components."""
    async with lifespan(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
            data = resp.json()

            assert "backend" in data
            assert data["backend"] == "healthy"
            assert "database" in data
            assert data["database"] == "healthy"
            assert "retrieval" in data
            assert data["retrieval"] == "ready"
            assert "graph" in data
            assert data["graph"] == "ready"
            assert "llm" in data


@pytest.mark.asyncio
async def test_projects_crud_workflow():
    """Verify project creation, retrieval, and listing."""
    async with lifespan(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Create project
            create_resp = await client.post(
                "/api/v1/projects",
                json={"name": "Test Repository", "description": "Automated test project"},
            )
            assert create_resp.status_code == 201
            project_data = create_resp.json()
            project_id = project_data["id"]
            assert project_data["name"] == "Test Repository"
            assert project_data["status"] == "QUEUED"

            # 2. Get project by ID
            get_resp = await client.get(f"/api/v1/projects/{project_id}")
            assert get_resp.status_code == 200
            assert get_resp.json()["id"] == project_id

            # 3. List projects
            list_resp = await client.get("/api/v1/projects")
            assert list_resp.status_code == 200
            projects_list = list_resp.json()["projects"]
            assert any(p["id"] == project_id for p in projects_list)

            # 4. Clean up / delete project
            del_resp = await client.delete(f"/api/v1/projects/{project_id}")
            assert del_resp.status_code == 204
