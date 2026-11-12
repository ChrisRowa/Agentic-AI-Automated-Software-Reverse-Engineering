"""
Vector Store for Code Chunks.
Integrates with PostgreSQL + pgvector when available, and provides a resilient
isolated local file/in-memory vector index fallback so semantic search operates seamlessly offline.
Ensures strict multi-tenant / multi-project isolation.
"""
import os
import json
import structlog
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from backend.core.config import settings

logger = structlog.get_logger(__name__)


class VectorStore:
    """
    Manages vector storage and cosine similarity search for repository code chunks.
    Guarantees strict project isolation by partitioning storage and queries by project_id.
    """

    def __init__(self, index_base_dir: Optional[str] = None):
        self.index_base_dir = Path(index_base_dir or settings.workspace_dir)
        # In-memory cache: project_id -> {"chunks": {chunk_id: chunk_dict}, "vectors": np.ndarray, "ids": [chunk_ids]}
        self._cache: Dict[str, Dict[str, Any]] = {}

    def _get_project_index_dir(self, project_id: str) -> Path:
        proj_dir = self.index_base_dir / project_id / "index"
        proj_dir.mkdir(parents=True, exist_ok=True)
        return proj_dir

    def _load_project_cache(self, project_id: str):
        if project_id in self._cache:
            return

        proj_dir = self._get_project_index_dir(project_id)
        index_file = proj_dir / "vector_index.json"
        vec_file = proj_dir / "vectors.npy"

        if index_file.exists() and vec_file.exists():
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    index_data = json.load(f)

                vectors = np.load(vec_file)
                self._cache[project_id] = {
                    "chunks": index_data.get("chunks", {}),
                    "ids": index_data.get("ids", []),
                    "vectors": vectors,
                }
                logger.info("Loaded cached vector index", project_id=project_id, count=len(vectors))
                return
            except Exception as e:
                logger.warning("Failed to load local vector index cache", project_id=project_id, error=str(e))

        self._cache[project_id] = {"chunks": {}, "ids": [], "vectors": np.empty((0, 384), dtype=np.float32)}

    async def add_chunks(
        self,
        project_id: str,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
        db: Optional[AsyncSession] = None,
    ):
        """
        Store chunks and their vector embeddings.
        Writes to PostgreSQL if session is active and saves to local project vector index.
        """
        if not chunks or not embeddings or len(chunks) != len(embeddings):
            return

        logger.info("Adding chunks to vector store", project_id=project_id, count=len(chunks))

        # 1. Update In-Memory & Local Index
        self._load_project_cache(project_id)
        chunk_map = self._cache[project_id]["chunks"]
        ids = self._cache[project_id]["ids"]
        existing_vecs = self._cache[project_id]["vectors"]

        new_ids = []
        new_vecs = []

        for chunk, emb in zip(chunks, embeddings):
            cid = chunk["chunk_id"]
            chunk_map[cid] = chunk
            new_ids.append(cid)
            new_vecs.append(emb)

        new_vec_arr = np.array(new_vecs, dtype=np.float32)
        # Normalize vectors for cosine similarity
        norms = np.linalg.norm(new_vec_arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        new_vec_arr = new_vec_arr / norms

        if existing_vecs.shape[0] > 0 and existing_vecs.shape[1] == new_vec_arr.shape[1]:
            combined_vecs = np.vstack([existing_vecs, new_vec_arr])
            combined_ids = ids + new_ids
        else:
            combined_vecs = new_vec_arr
            combined_ids = new_ids

        self._cache[project_id] = {
            "chunks": chunk_map,
            "ids": combined_ids,
            "vectors": combined_vecs,
        }

        # Persist to local disk
        proj_dir = self._get_project_index_dir(project_id)
        try:
            with open(proj_dir / "vector_index.json", "w", encoding="utf-8") as f:
                json.dump({"chunks": chunk_map, "ids": combined_ids}, f)
            np.save(proj_dir / "vectors.npy", combined_vecs)
        except Exception as e:
            logger.warning("Could not persist local vector index to disk", error=str(e))

        # 2. Persist to PostgreSQL if DB session is available
        if db is not None:
            try:
                from backend.models.database import CodeChunk
                for chunk, emb in zip(chunks, embeddings):
                    db_chunk = CodeChunk(
                        id=chunk["chunk_id"],
                        project_id=project_id,
                        file_id=chunk.get("file_id"),
                        file_path=chunk["file_path"],
                        language=chunk.get("language"),
                        symbol_name=chunk.get("symbol_name"),
                        symbol_type=chunk.get("symbol_type"),
                        class_name=chunk.get("class_name"),
                        start_line=chunk.get("start_line", 1),
                        end_line=chunk.get("end_line", 1),
                        chunk_type=chunk.get("chunk_type", "code"),
                        content=chunk.get("content", ""),
                        contextualized_text=chunk.get("contextualized_text", ""),
                        embedding=emb,
                        chunk_metadata=chunk.get("metadata", {}),
                    )
                    db.add(db_chunk)
                await db.commit()
                logger.info("Chunks successfully persisted to PostgreSQL", count=len(chunks))
            except Exception as e:
                logger.warning("Database persistence for CodeChunk failed, falling back to local index", error=str(e))
                await db.rollback()

    async def search(
        self,
        project_id: str,
        query_embedding: List[float],
        top_k: int = 10,
        db: Optional[AsyncSession] = None,
    ) -> List[Tuple[str, float]]:
        """
        Execute vector similarity search strictly within the specified project.
        Returns list of (chunk_id, cosine_similarity_score).
        """
        # Ensure project cache is loaded
        self._load_project_cache(project_id)
        proj_data = self._cache.get(project_id)
        if not proj_data or proj_data["vectors"].shape[0] == 0:
            return []

        vectors = proj_data["vectors"]
        ids = proj_data["ids"]

        q_vec = np.array(query_embedding, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm > 0:
            q_vec = q_vec / q_norm

        # Cosine similarity = dot product of normalized vectors
        scores = np.dot(vectors, q_vec)

        # Top-k selection
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            score = float(scores[idx])
            # Bound score to [0.0, 1.0]
            norm_score = max(0.0, min(1.0, (score + 1.0) / 2.0 if score < 0 else score))
            results.append((ids[idx], norm_score))

        return results

    def get_chunk(self, project_id: str, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve chunk dictionary by ID within project."""
        self._load_project_cache(project_id)
        return self._cache.get(project_id, {}).get("chunks", {}).get(chunk_id)

    def get_all_chunks(self, project_id: str) -> List[Dict[str, Any]]:
        """Retrieve all chunks for a project."""
        self._load_project_cache(project_id)
        return list(self._cache.get(project_id, {}).get("chunks", {}).values())

    async def clear_project(self, project_id: str, db: Optional[AsyncSession] = None):
        """Clear all stored vectors and chunks for a project."""
        self._cache.pop(project_id, None)
        proj_dir = self._get_project_index_dir(project_id)
        for f in (proj_dir / "vector_index.json", proj_dir / "vectors.npy"):
            if f.exists():
                try:
                    f.unlink()
                except Exception:
                    pass

        if db is not None:
            try:
                from backend.models.database import CodeChunk
                await db.execute(delete(CodeChunk).where(CodeChunk.project_id == project_id))
                await db.commit()
            except Exception as e:
                logger.warning("Could not clear DB chunks", error=str(e))
