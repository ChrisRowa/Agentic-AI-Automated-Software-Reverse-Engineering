"""
Unit and integration tests for LangGraph Multi-Agent Orchestrator.
Validates:
- Full LangGraph execution from START to END
- Intent classification
- Negative / impossible question detection (No-Evidence state)
- Verification agent claim checking
- Feedback loop routing when regeneration is needed
- Source citation and line range preservation
"""
import pytest
import asyncio
from backend.agents.orchestrator import (
    reverse_engineering_graph,
    planner_agent,
    verification_agent,
    confidence_agent,
    check_regeneration,
)
from backend.agents.state import ReverseEngineeringState


@pytest.mark.asyncio
async def test_planner_agent_intent_classification():
    """Verify planner classifies diverse questions correctly."""
    # Architecture
    s1 = await planner_agent({"question": "What is the high-level system architecture?"})
    assert s1["intent"] == "architecture"

    # Dependency
    s2 = await planner_agent({"question": "Which modules depend on the database package?"})
    assert s2["intent"] == "dependency"

    # Call graph
    s3 = await planner_agent({"question": "Who calls AuthService.authenticate()?"})
    assert s3["intent"] == "call_graph"

    # Feature flow
    s4 = await planner_agent({"question": "What happens when a user logs in?"})
    assert s4["intent"] == "feature_flow"

    # Security
    s5 = await planner_agent({"question": "Where are user credentials and tokens handled?"})
    assert s5["intent"] == "security"


@pytest.mark.asyncio
async def test_negative_impossible_question_returns_unsupported():
    """Verify impossible questions return the mandatory NO_EVIDENCE state without hallucinations."""
    state: ReverseEngineeringState = {
        "project_id": "nonexistent-project",
        "question": "Where is Bitcoin blockchain cryptocurrency mining implemented?",
        "context_limit": 5,
        "iteration_count": 0,
        "errors": [],
    }

    final_state = await reverse_engineering_graph.ainvoke(state)

    assert final_state["verification_status"] == "UNSUPPORTED"
    assert final_state["confidence"] == 0.0
    assert "No supporting evidence" in final_state["final_answer"]
    assert len(final_state.get("evidence", [])) == 0


@pytest.mark.asyncio
async def test_verification_agent_unsupported_detection():
    """Verify verification agent flags claims referencing non-existent files."""
    state: ReverseEngineeringState = {
        "has_sufficient_evidence": True,
        "draft_answer": "Implemented in nonexistent_crypto_service.py:100",
        "evidence": [
            {"file": "auth_service.py", "line_start": 20, "line_end": 40, "evidence_type": "METHOD", "content_snippet": "def login()"}
        ],
        "iteration_count": 0,
    }

    res = await verification_agent(state)
    assert res["regeneration_needed"] is True
    assert "nonexistent_crypto_service.py" in res["verification_explanation"]


@pytest.mark.asyncio
async def test_confidence_agent_scoring():
    """Verify confidence agent maps evidence and verification status to calibrated confidence."""
    # Verified state
    c1 = await confidence_agent({
        "verification_status": "VERIFIED",
        "evidence": [{"id": "1"}, {"id": "2"}, {"id": "3"}],
    })
    assert c1["confidence"] >= 0.90

    # Inferred state
    c2 = await confidence_agent({
        "verification_status": "INFERRED",
        "evidence": [{"id": "1"}],
    })
    assert c2["confidence"] == 0.75

    # Unsupported state
    c3 = await confidence_agent({
        "verification_status": "UNSUPPORTED",
        "evidence": [],
    })
    assert c3["confidence"] == 0.0


def test_conditional_routing_regeneration():
    """Verify feedback loop triggers only on first iteration when regeneration is required."""
    # First attempt: regeneration needed -> route back to reasoning
    route1 = check_regeneration({
        "regeneration_needed": True,
        "iteration_count": 0,
    })
    assert route1 == "reasoning"

    # Second attempt: do not loop indefinitely -> route to report
    route2 = check_regeneration({
        "regeneration_needed": True,
        "iteration_count": 1,
    })
    assert route2 == "report"

    # Normal success -> route to report
    route3 = check_regeneration({
        "regeneration_needed": False,
        "iteration_count": 0,
    })
    assert route3 == "report"
