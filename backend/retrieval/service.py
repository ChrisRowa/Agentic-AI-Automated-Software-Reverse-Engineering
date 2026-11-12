"""
Hybrid Retrieval Service.
Orchestrates code chunking, vector embeddings, lexical search, graph context expansion,
and evidence-grounded candidate ranking.
"""
import time
import structlog
from typing import Dict, Any, List, Optional
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from backend.retrieval.chunker import CodeChunker
from backend.retrieval.embeddings import get_embedding_provider
from backend.retrieval.lexical import LexicalRetriever, tokenize_code, GENERIC_CODE_TERMS
from backend.retrieval.vector_store import VectorStore
from backend.retrieval.graph_retriever import GraphAwareRetriever
from backend.retrieval.ranker import HybridRanker
from backend.retrieval.evidence import EvidenceBuilder

logger = structlog.get_logger(__name__)


class RetrievalService:
    """
    Central service coordinating Hybrid RAG indexing and multi-channel retrieval.
    """

    def __init__(self):
        self.chunker = CodeChunker()
        self.vector_store = VectorStore()
        self.ranker = HybridRanker(relevance_threshold=0.25)
        # In-memory lexical & graph retrievers per project: project_id -> LexicalRetriever / GraphAwareRetriever
        self._lexical_retrievers: Dict[str, LexicalRetriever] = {}
        self._graph_retrievers: Dict[str, GraphAwareRetriever] = {}

    async def index_project(
        self,
        project_id: str,
        extraction_path: str,
        manifest: Dict[str, Any],
        parse_results: Dict[str, Any],
        graph_data: Dict[str, Any],
        file_id_map: Optional[Dict[str, str]] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        Extract code chunks, compute vector embeddings, index lexical tokens,
        and build graph traversal indices for the project.
        """
        start_time = time.time()
        logger.info("Starting hybrid RAG indexing", project_id=project_id)

        # 1. Structural Code Chunking
        chunks = self.chunker.chunk_repository(
            project_id=project_id,
            extraction_path=extraction_path,
            manifest=manifest,
            parse_results=parse_results,
            file_id_map=file_id_map,
        )

        if not chunks:
            logger.warning("No code chunks generated for project", project_id=project_id)
            return {"project_id": project_id, "chunks_count": 0, "status": "empty"}

        # 2. Embedding Generation
        emb_provider = get_embedding_provider()
        context_texts = [c["contextualized_text"] for c in chunks]

        emb_start = time.time()
        try:
            embeddings = emb_provider.embed_batch(context_texts)
        except Exception as e:
            logger.warning("Embedding generation failed; degrading to lexical + graph retrieval", error=str(e))
            embeddings = [[0.0] * emb_provider.dimension for _ in chunks]
        emb_duration = time.time() - emb_start

        # 3. Store Vectors & Chunks (PostgreSQL + Local isolated index)
        await self.vector_store.add_chunks(
            project_id=project_id,
            chunks=chunks,
            embeddings=embeddings,
            db=db,
        )

        # 4. Build Lexical Retriever
        lex_retriever = LexicalRetriever(chunks)
        self._lexical_retrievers[project_id] = lex_retriever

        # 5. Build Graph Retriever
        graph_retriever = GraphAwareRetriever(graph_data)
        self._graph_retrievers[project_id] = graph_retriever

        total_duration = time.time() - start_time
        logger.info(
            "Hybrid RAG indexing complete",
            project_id=project_id,
            chunks_count=len(chunks),
            embedding_duration_sec=round(emb_duration, 2),
            total_duration_sec=round(total_duration, 2),
        )

        return {
            "project_id": project_id,
            "chunks_count": len(chunks),
            "embedding_dimension": emb_provider.dimension,
            "embedding_provider": type(emb_provider).__name__,
            "indexing_duration_seconds": round(total_duration, 3),
            "status": "ready",
        }

    async def retrieve(
        self,
        project_id: str,
        query: str,
        top_k: int = 10,
        intent: Optional[str] = None,
        filter_file: Optional[str] = None,
        filter_symbol: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        Execute Hybrid Retrieval combining:
        - Lexical (BM25 + Identifier Normalization + Generic Filtering)
        - Vector (Semantic Cosine Similarity)
        - Graph (Knowledge Graph Call/Dependency Traversal)
        - Metadata (Symbol & File Structure)
        """
        retrieval_start = time.time()
        logger.info("Executing hybrid retrieval", project_id=project_id, query=query[:80], intent=intent)

        # Ensure project lexical index is ready
        if project_id not in self._lexical_retrievers:
            chunks = self.vector_store.get_all_chunks(project_id)
            if chunks:
                self._lexical_retrievers[project_id] = LexicalRetriever(chunks)

        lex_retriever = self._lexical_retrievers.get(project_id)
        graph_retriever = self._graph_retrievers.get(project_id) or GraphAwareRetriever()

        chunks_by_id = {c["chunk_id"]: c for c in self.vector_store.get_all_chunks(project_id)}
        if not chunks_by_id:
            return {
                "query": query,
                "intent": intent,
                "has_sufficient_evidence": False,
                "evidence": [],
                "call_paths": [],
                "top_candidates": [],
                "message": "No indexed chunks found for this project.",
            }

        # ── 1. Lexical Retrieval ──────────────────────────────────────────
        lex_scores = {}
        if lex_retriever:
            lex_results = lex_retriever.search(query, top_k=top_k * 3)
            lex_scores = dict(lex_results)

        # ── 2. Vector Retrieval ───────────────────────────────────────────
        vec_scores = {}
        emb_provider = get_embedding_provider()
        try:
            q_emb = emb_provider.embed_text(query)
            vec_results = await self.vector_store.search(
                project_id=project_id,
                query_embedding=q_emb,
                top_k=top_k * 3,
                db=db,
            )
            vec_scores = dict(vec_results)
        except Exception as e:
            logger.warning("Vector search unavailable; proceeding with lexical + graph", error=str(e))

        # ── 3. Graph Context Expansion ────────────────────────────────────
        query_tokens = tokenize_code(query)
        # Select seed candidates from top lexical and vector matches
        seed_symbols = set()
        for cid in list(lex_scores.keys())[:5] + list(vec_scores.keys())[:5]:
            c = chunks_by_id.get(cid)
            if c:
                if c.get("symbol_name"):
                    seed_symbols.add(c["symbol_name"])
                if c.get("class_name"):
                    seed_symbols.add(c["class_name"])

        # Also add informative query tokens
        for t in query_tokens:
            if t not in GENERIC_CODE_TERMS and len(t) > 2:
                seed_symbols.add(t)

        graph_context = graph_retriever.expand_graph_context(list(seed_symbols))
        graph_scores_raw = graph_context.get("graph_scores", {})
        call_paths = graph_context.get("call_paths", [])

        # Map node graph scores back to matching chunk IDs
        graph_chunk_scores = {}
        for cid, chunk in chunks_by_id.items():
            sym = chunk.get("symbol_name") or chunk.get("class_name")
            if sym:
                # Check if this symbol matched a node with graph score
                for nid, gscore in graph_scores_raw.items():
                    if sym.lower() in nid.lower() or nid.lower() in sym.lower():
                        graph_chunk_scores[cid] = max(graph_chunk_scores.get(cid, 0.0), gscore)

        # ── 4. Hybrid Ranking ─────────────────────────────────────────────
        scored_candidates = self.ranker.rank(
            chunks_by_id=chunks_by_id,
            lexical_scores=lex_scores,
            vector_scores=vec_scores,
            graph_scores=graph_chunk_scores,
            intent=intent,
            filter_file=filter_file,
            filter_symbol=filter_symbol,
            top_k=top_k,
        )

        # ── 5. Generic-Term False Match & Insufficient Evidence Safeguard ─
        # Check if the query had informative terms (e.g. "Bitcoin", "payment")
        informative_query_tokens = [t for t in query_tokens if t not in GENERIC_CODE_TERMS]
        has_informative_query = len(informative_query_tokens) > 0

        # Does the top candidate have sufficient relevance?
        top_score = scored_candidates[0].final_score if scored_candidates else 0.0
        top_lex_score = scored_candidates[0].lexical_score if scored_candidates else 0.0

        # If informative query terms exist, require multi-term matching (Phase 13)
        unique_informative = list(set(informative_query_tokens))
        matched_informative_set = set()
        if has_informative_query and scored_candidates:
            for cand in scored_candidates[:5]:
                cand_text = f"{cand.chunk.get('symbol_name', '')} {cand.chunk.get('content', '')} {cand.chunk.get('file_path', '')}".lower()
                for inf in unique_informative:
                    if inf in cand_text:
                        matched_informative_set.add(inf)

        matched_ratio = len(matched_informative_set) / len(unique_informative) if unique_informative else 0.0

        is_insufficient = False
        if not scored_candidates or top_score < self.ranker.relevance_threshold:
            is_insufficient = True
        elif has_informative_query and len(matched_informative_set) == 0:
            is_insufficient = True
        elif len(unique_informative) >= 3 and matched_ratio < 0.40 and len(matched_informative_set) < 2:
            is_insufficient = True

        if is_insufficient:
            logger.info("Insufficient evidence found for query", query=query, top_score=top_score)
            return {
                "query": query,
                "intent": intent,
                "has_sufficient_evidence": False,
                "evidence": [],
                "call_paths": [],
                "top_candidates": [s.to_dict() for s in scored_candidates[:3]],
                "message": "No sufficiently relevant repository evidence found.",
                "duration_ms": round((time.time() - retrieval_start) * 1000, 2),
            }

        # ── 6. Build Grounded Evidence Objects ─────────────────────────────
        evidence_items = []
        for scored in scored_candidates:
            ev = EvidenceBuilder.from_scored_chunk(scored)
            evidence_items.append(ev)

        # Add graph node context items if relevant
        for rnode in graph_context.get("related_nodes", [])[:3]:
            if rnode.get("file_path"):
                evidence_items.append(EvidenceBuilder.from_graph_node(rnode, relevance_score=0.75))

        logger.info(
            "Hybrid retrieval succeeded",
            query=query[:60],
            candidates_returned=len(evidence_items),
            top_score=top_score,
            duration_ms=round((time.time() - retrieval_start) * 1000, 2),
        )

        return {
            "query": query,
            "intent": intent,
            "has_sufficient_evidence": True,
            "evidence": evidence_items[:top_k],
            "call_paths": call_paths,
            "top_candidates": [s.to_dict() for s in scored_candidates],
            "message": None,
            "duration_ms": round((time.time() - retrieval_start) * 1000, 2),
        }


# Singleton service instance
retrieval_service = RetrievalService()
