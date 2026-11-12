"""
Evidence Representation and Formatter.
Grounds all AI claims in verifiable source code locations (file, line_start, line_end, symbol).
Enforces: NO EVIDENCE -> NO FACTUAL CLAIM.
"""
from typing import Dict, Any, List, Optional
from backend.models.schemas import EvidenceItem
from backend.retrieval.ranker import ScoredChunk


class EvidenceBuilder:
    """
    Constructs standardized evidence dictionaries from scored chunks and graph nodes.
    """

    @staticmethod
    def from_scored_chunk(scored: ScoredChunk) -> Dict[str, Any]:
        chunk = scored.chunk
        symbol = chunk.get("symbol_name") or chunk.get("class_name") or ""
        return {
            "id": scored.chunk_id,
            "project_id": chunk.get("project_id"),
            "file_id": chunk.get("file_id"),
            "file": chunk.get("file_path", ""),
            "line_start": chunk.get("start_line"),
            "line_end": chunk.get("end_line"),
            "symbol": symbol,
            "symbol_type": chunk.get("symbol_type"),
            "evidence_type": f"{chunk.get('symbol_type', 'CODE')}_CHUNK",
            "content_snippet": chunk.get("content", "")[:1000],
            "source_type": "code",
            "source_tool": "hybrid_rag",
            "retrieval_method": "hybrid",
            "relevance_score": scored.final_score,
            "component_scores": {
                "lexical": scored.lexical_score,
                "vector": scored.vector_score,
                "graph": scored.graph_score,
                "metadata": scored.metadata_score,
            },
        }

    @staticmethod
    def from_graph_node(node: Dict[str, Any], relevance_score: float = 0.7) -> Dict[str, Any]:
        return {
            "id": str(node.get("id")),
            "project_id": node.get("project_id"),
            "file": node.get("file_path", ""),
            "line_start": node.get("line_start"),
            "line_end": node.get("line_end"),
            "symbol": node.get("label", ""),
            "symbol_type": node.get("node_type"),
            "evidence_type": f"{node.get('node_type', 'GRAPH')}_NODE",
            "content_snippet": f"{node.get('node_type')}: {node.get('label')}",
            "source_type": "graph",
            "source_tool": "knowledge_graph",
            "retrieval_method": "graph_traversal",
            "relevance_score": relevance_score,
        }

    @staticmethod
    def to_schema_item(evidence_dict: Dict[str, Any]) -> EvidenceItem:
        """Convert an internal evidence dictionary to the public API EvidenceItem schema."""
        return EvidenceItem(
            id=evidence_dict.get("id"),
            file=evidence_dict.get("file", ""),
            line_start=evidence_dict.get("line_start"),
            line_end=evidence_dict.get("line_end"),
            evidence_type=evidence_dict.get("evidence_type", "CODE_CHUNK"),
            content_snippet=evidence_dict.get("content_snippet"),
            source_tool=evidence_dict.get("source_tool", "hybrid_rag"),
        )
