"""
AI Q&A Agent — Intent-aware retrieval + evidence-backed answers.
Research additions: Intent-Aware Retrieval (#17), Evidence-Linked Results,
Repository-Specific Evidence Selection (#7).

Uses LLM only after deterministic evidence retrieval.
"""
import structlog
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from backend.models.database import (
    GraphNode, GraphEdge, Symbol, RepositoryFile, Claim,
    VerificationStatus, AnalysisStatus,
)
from backend.models.schemas import AskResponse, EvidenceItem, VerificationStatusEnum
from backend.core.config import settings

logger = structlog.get_logger(__name__)

# Intent classification patterns
INTENT_PATTERNS = {
    "architecture": ["architecture", "overview", "structure", "design", "high-level", "system"],
    "dependency": ["depend", "import", "require", "use", "reference"],
    "function_explanation": ["what does", "explain", "how does", "purpose of", "what is"],
    "feature_flow": ["flow", "process", "workflow", "step", "sequence", "how does login", "how does"],
    "data_flow": ["data", "variable", "pass", "value", "return", "store"],
    "traceability": ["where is", "which file", "which function", "locate", "find"],
    "slicing": ["slice", "impact", "affect", "related", "connected"],
    "uml": ["diagram", "class diagram", "uml", "chart"],
    "change_impact": ["change", "modify", "update", "refactor", "impact"],
}


def classify_intent(question: str) -> str:
    """Classify the user's question intent for retrieval strategy selection."""
    q_lower = question.lower()
    for intent, keywords in INTENT_PATTERNS.items():
        if any(kw in q_lower for kw in keywords):
            return intent
    return "general"


async def retrieve_evidence(
    db: AsyncSession,
    project_id: str,
    question: str,
    intent: str,
    limit: int = 10,
) -> tuple:
    """
    Hybrid evidence retrieval via RetrievalService:
    Combines BM25 lexical, semantic vector similarity, and knowledge graph relationships.
    Enforces generic-term filtering and insufficient-evidence safeguards.
    Returns: (evidence_items, call_path, has_sufficient_evidence)
    """
    from backend.retrieval.service import retrieval_service

    res = await retrieval_service.retrieve(
        project_id=project_id,
        query=question,
        top_k=limit,
        intent=intent,
        db=db,
    )

    evidence_items = res.get("evidence", [])
    call_paths = res.get("call_paths", [])
    has_sufficient = res.get("has_sufficient_evidence", False)
    first_call_path = call_paths[0] if call_paths else None

    # If hybrid retriever found sufficient evidence, return it
    if has_sufficient and evidence_items:
        return evidence_items, first_call_path, True

    # If hybrid retriever explicitly determined insufficient evidence, return empty
    if not has_sufficient:
        return [], None, False

    # Fallback to direct graph search if index wasn't populated yet
    stopwords = {"the", "a", "an", "is", "are", "was", "in", "of", "for", "to", "how", "what", "does", "do", "where", "which"}
    terms = [w.strip("?,.'\"") for w in question.lower().split() if w.strip("?,.'\"") not in stopwords and len(w) > 2]

    fallback_evidence = []
    for term in terms[:5]:
        result = await db.execute(
            select(GraphNode).where(
                GraphNode.project_id == project_id,
                GraphNode.label.ilike(f"%{term}%"),
            ).limit(5)
        )
        for node in result.scalars().all():
            if node.file_path and node.line_start:
                fallback_evidence.append({
                    "id": str(node.id),
                    "file": node.file_path,
                    "line_start": node.line_start,
                    "line_end": node.line_end,
                    "evidence_type": f"{node.node_type}_MATCH",
                    "content_snippet": f"{node.node_type}: {node.label}",
                    "source_tool": "graph_fallback_search",
                    "label": node.label,
                    "node_type": node.node_type,
                })

    return fallback_evidence[:limit], None, len(fallback_evidence) > 0


async def answer_question(
    db: AsyncSession,
    project_id: str,
    question: str,
    context_limit: int = 10,
) -> AskResponse:
    """
    Main Q&A function — intent-aware hybrid retrieval + LLM reasoning.
    Evidence is collected first from hybrid RAG and graph; LLM only reasons over it.
    """
    # Step 1: Classify intent
    intent = classify_intent(question)
    logger.info("Question classified", intent=intent, question=question[:100])

    # Step 2: Retrieve evidence from Hybrid RAG
    evidence_items, graph_call_path, has_sufficient = await retrieve_evidence(
        db, project_id, question, intent, limit=context_limit
    )

    # Negative / unsupported query check
    if not has_sufficient or not evidence_items:
        return AskResponse(
            question=question,
            answer=(
                f"No sufficiently relevant repository evidence found for '{question}'. "
                "The requested feature, service, or concept does not appear to be implemented in this codebase."
            ),
            evidence=[],
            call_path=None,
            relevant_files=[],
            confidence=0.0,
            verification_status=VerificationStatusEnum.UNSUPPORTED,
            intent_type=intent,
        )

    # Step 3: Call LLM with compact evidence context
    answer_text, confidence, verification_status, call_path = await _call_llm_with_evidence(
        question=question,
        intent=intent,
        evidence_items=evidence_items,
        project_id=project_id,
    )

    final_call_path = call_path or graph_call_path

    # Step 4: Store claim in database
    from backend.models.database import Claim
    claim = Claim(
        project_id=project_id,
        claim_text=answer_text[:2000],
        claim_type=intent,
        agent_source="qa_agent",
        verification_status=VerificationStatus(verification_status),
        confidence=confidence,
        evidence_ids=[item.get("id") for item in evidence_items if item.get("id")],
    )
    db.add(claim)
    await db.commit()

    # Build response
    relevant_files = list({item["file"] for item in evidence_items if item.get("file")})

    return AskResponse(
        question=question,
        answer=answer_text,
        evidence=[
            EvidenceItem(
                id=item.get("id"),
                file=item.get("file", ""),
                line_start=item.get("line_start"),
                line_end=item.get("line_end"),
                evidence_type=item.get("evidence_type", "MATCH"),
                content_snippet=item.get("content_snippet"),
                source_tool=item.get("source_tool"),
            )
            for item in evidence_items
        ],
        call_path=final_call_path,
        relevant_files=relevant_files,
        confidence=confidence,
        verification_status=VerificationStatusEnum(verification_status),
        intent_type=intent,
    )


async def _call_llm_with_evidence(
    question: str,
    intent: str,
    evidence_items: List[Dict],
    project_id: str,
) -> tuple:
    """
    Call the configured LLM with compact evidence context.
    If no LLM is configured, returns a structured answer from evidence alone.
    """
    # Build compact context from evidence
    evidence_context = "\n".join([
        f"- {item.get('evidence_type')}: {item.get('file', '')}:{item.get('line_start', '?')} — {item.get('content_snippet', '')}"
        for item in evidence_items[:10]
    ])

    # Check if LLM is available
    llm_available = bool(
        settings.openai_api_key or
        settings.google_api_key or
        settings.anthropic_api_key
    )

    if not evidence_items:
        return (
            f"No relevant code elements were found for your question about '{question}'. "
            "This may be because the repository analysis is still incomplete, "
            "or the specific element doesn't exist in the codebase.",
            0.2,
            "UNCERTAIN",
            None,
        )

    if not llm_available:
        # Return evidence-only answer without LLM
        answer = f"**Evidence found for: {question}**\n\n"
        answer += f"Intent classified as: `{intent}`\n\n"
        answer += "**Relevant code elements:**\n"
        for item in evidence_items[:10]:
            answer += f"- `{item.get('file', 'unknown')}:{item.get('line_start', '?')}` — {item.get('evidence_type')}: **{item.get('content_snippet', item.get('label', ''))[:100]}**\n"
        answer += "\n> ⚠️ LLM reasoning is not available (no API key configured). "
        answer += "Configure `OPENAI_API_KEY`, `GOOGLE_API_KEY`, or `ANTHROPIC_API_KEY` in `.env` for AI explanations."

        call_path = [item.get("content_snippet", "").replace("calls ", "") for item in evidence_items if item.get("evidence_type") == "CALL"]

        return answer, 0.6, "INFERRED", call_path if call_path else None

    # LLM is available — call it with compact context
    try:
        answer, call_path = await _invoke_llm(question, intent, evidence_context, evidence_items)
        return answer, 0.85, "INFERRED", call_path
    except Exception as e:
        logger.warning("LLM call failed", error=str(e))
        return (
            f"Evidence retrieval succeeded but LLM reasoning failed: {str(e)[:200]}. "
            f"Evidence found: {len(evidence_items)} items.",
            0.5,
            "UNCERTAIN",
            None,
        )


async def _invoke_llm(
    question: str,
    intent: str,
    evidence_context: str,
    evidence_items: List[Dict],
) -> tuple:
    """Invoke the configured LLM with a structured prompt."""
    from langchain_core.messages import HumanMessage, SystemMessage

    system_prompt = """You are an expert software reverse engineering assistant.
You analyze source code evidence and explain software behavior.

CRITICAL RULES:
1. Only make claims supported by the evidence provided.
2. Clearly mark any inference that goes beyond direct evidence.
3. Never invent functions, classes, or relationships not in the evidence.
4. Format your answer with source citations.
5. Keep answers concise and developer-focused.

Response format:
1. Direct answer (1-2 sentences)
2. Evidence-based explanation
3. Source references (from the evidence provided)"""

    user_prompt = f"""Question: {question}
Intent type: {intent}

Code Evidence Found:
{evidence_context}

Please answer the question using only this evidence. Cite specific files and lines."""

    # Route to configured LLM
    if settings.openai_api_key:
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            model=settings.primary_llm_model,
            api_key=settings.openai_api_key,
            temperature=0.1,
            max_tokens=1000,
        )
    elif settings.google_api_key:
        from langchain_google_genai import ChatGoogleGenerativeAI
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            google_api_key=settings.google_api_key,
            temperature=0.1,
        )
    elif settings.anthropic_api_key:
        from langchain_anthropic import ChatAnthropic
        llm = ChatAnthropic(
            model="claude-3-5-haiku-20241022",
            api_key=settings.anthropic_api_key,
            temperature=0.1,
            max_tokens=1000,
        )
    else:
        raise ValueError("No LLM provider configured")

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    response = await llm.ainvoke(messages)
    answer = response.content

    # Extract call path from call evidence
    call_path = [
        item.get("content_snippet", "").replace("calls ", "")
        for item in evidence_items
        if item.get("evidence_type") == "CALL"
    ]

    return answer, call_path if call_path else None
