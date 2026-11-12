"""
Hybrid RAG & Code-Aware Retrieval Package.
"""
from backend.retrieval.chunker import CodeChunker
from backend.retrieval.embeddings import (
    EmbeddingProvider,
    SentenceTransformerEmbeddingProvider,
    DeterministicHashingEmbeddingProvider,
    get_embedding_provider,
)
from backend.retrieval.lexical import LexicalRetriever, tokenize_code
from backend.retrieval.vector_store import VectorStore
from backend.retrieval.graph_retriever import GraphAwareRetriever
from backend.retrieval.ranker import HybridRanker, ScoredChunk
from backend.retrieval.evidence import EvidenceBuilder
from backend.retrieval.service import RetrievalService, retrieval_service

__all__ = [
    "CodeChunker",
    "EmbeddingProvider",
    "SentenceTransformerEmbeddingProvider",
    "DeterministicHashingEmbeddingProvider",
    "get_embedding_provider",
    "LexicalRetriever",
    "tokenize_code",
    "VectorStore",
    "GraphAwareRetriever",
    "HybridRanker",
    "ScoredChunk",
    "EvidenceBuilder",
    "RetrievalService",
    "retrieval_service",
]
