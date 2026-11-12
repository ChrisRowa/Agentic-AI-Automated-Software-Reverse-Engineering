"""
Shared typed state definition for the LangGraph Reverse Engineering Multi-Agent System.
"""
from typing import TypedDict, List, Dict, Any, Optional


class ReverseEngineeringState(TypedDict, total=False):
    """
    Unified state passed across all specialized agents in the LangGraph workflow:
    Planner -> Retrieval -> Code Analysis -> Graph Analysis -> Reasoning -> Verification -> Confidence -> Report
    """
    # Request & Core identifiers
    project_id: str
    question: str
    intent: str
    context_limit: int

    # Repository & Structural context
    repository_context: Dict[str, Any]
    retrieved_chunks: List[Dict[str, Any]]
    graph_entities: List[Dict[str, Any]]
    graph_relationships: List[Dict[str, Any]]
    call_paths: List[List[str]]

    # Grounded evidence & static analysis
    evidence: List[Dict[str, Any]]
    has_sufficient_evidence: bool
    static_analysis: Dict[str, Any]

    # AI Reasoning & Explanations
    reasoning: str
    draft_answer: str
    feedback: Optional[str]

    # Verification & Confidence
    verification_status: str  # VERIFIED, INFERRED, UNCERTAIN, UNSUPPORTED
    confidence: float         # 0.0 - 1.0
    verification_explanation: str
    claim_id: Optional[str]
    regeneration_needed: bool

    # Final Output
    final_answer: str
    relevant_files: List[str]
    call_path: Optional[List[str]]

    # Execution tracking & control flow
    iteration_count: int
    errors: List[str]
    status: str
