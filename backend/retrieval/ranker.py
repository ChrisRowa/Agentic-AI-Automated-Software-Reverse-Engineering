"""
Hybrid Ranker for Code Retrieval.
Combines Lexical (BM25), Semantic (Vector), Graph, and Metadata signals into a transparent,
explainable score with configurable weights and component attribution.
"""
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ScoredChunk:
    chunk_id: str
    chunk: Dict[str, Any]
    lexical_score: float
    vector_score: float
    graph_score: float
    metadata_score: float
    final_score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "file_path": self.chunk.get("file_path"),
            "symbol": self.chunk.get("symbol_name") or self.chunk.get("class_name"),
            "start_line": self.chunk.get("start_line"),
            "end_line": self.chunk.get("end_line"),
            "lexical_score": round(self.lexical_score, 4),
            "vector_score": round(self.vector_score, 4),
            "graph_score": round(self.graph_score, 4),
            "metadata_score": round(self.metadata_score, 4),
            "final_score": round(self.final_score, 4),
        }


class HybridRanker:
    """
    Ranks candidates across multiple retrieval channels with explainable component weights.
    """

    def __init__(
        self,
        weight_lexical: float = 0.35,
        weight_vector: float = 0.35,
        weight_graph: float = 0.20,
        weight_metadata: float = 0.10,
        relevance_threshold: float = 0.25,
    ):
        self.w_lex = weight_lexical
        self.w_vec = weight_vector
        self.w_graph = weight_graph
        self.w_meta = weight_metadata
        self.relevance_threshold = relevance_threshold

    def rank(
        self,
        chunks_by_id: Dict[str, Dict[str, Any]],
        lexical_scores: Dict[str, float],
        vector_scores: Dict[str, float],
        graph_scores: Dict[str, float],
        intent: Optional[str] = None,
        filter_file: Optional[str] = None,
        filter_symbol: Optional[str] = None,
        top_k: int = 10,
    ) -> List[ScoredChunk]:
        """
        Merge candidate scores from all channels and produce sorted ScoredChunks.
        """
        all_candidate_ids = set(lexical_scores.keys()) | set(vector_scores.keys()) | set(graph_scores.keys())
        scored: List[ScoredChunk] = []

        for cid in all_candidate_ids:
            chunk = chunks_by_id.get(cid)
            if not chunk:
                continue

            # Optional metadata filters
            if filter_file and filter_file not in chunk.get("file_path", ""):
                continue
            if filter_symbol and filter_symbol.lower() not in (chunk.get("symbol_name") or "").lower():
                continue

            s_lex = float(lexical_scores.get(cid, 0.0))
            s_vec = float(vector_scores.get(cid, 0.0))
            s_graph = float(graph_scores.get(cid, 0.0))

            # Compute metadata score
            s_meta = 0.0
            if chunk.get("symbol_type") in ("FUNCTION", "METHOD", "CLASS"):
                s_meta += 0.5
            if not chunk.get("metadata", {}).get("is_test", False):
                s_meta += 0.3
            if chunk.get("metadata", {}).get("docstring"):
                s_meta += 0.2
            s_meta = min(1.0, s_meta)

            # Intent-aware dynamic weight tuning
            w_lex = self.w_lex
            w_vec = self.w_vec
            w_graph = self.w_graph
            w_meta = self.w_meta

            if intent in ("dependency", "call_graph", "feature_flow"):
                # Boost graph weight for relational questions
                w_graph += 0.15
                w_vec -= 0.10
                w_lex -= 0.05
            elif intent in ("architecture", "system_overview"):
                # Boost vector and metadata weights for conceptual questions
                w_vec += 0.10
                w_meta += 0.05
                w_graph -= 0.15

            # Calculate composite final score
            final = (s_lex * w_lex) + (s_vec * w_vec) + (s_graph * w_graph) + (s_meta * w_meta)

            # Cap between 0 and 1
            final = max(0.0, min(1.0, final))

            scored.append(
                ScoredChunk(
                    chunk_id=cid,
                    chunk=chunk,
                    lexical_score=s_lex,
                    vector_score=s_vec,
                    graph_score=s_graph,
                    metadata_score=s_meta,
                    final_score=final,
                )
            )

        # Sort descending by final score
        scored.sort(key=lambda x: x.final_score, reverse=True)
        return scored[:top_k]
