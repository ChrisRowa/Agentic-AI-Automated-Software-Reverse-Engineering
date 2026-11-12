"""
Code-Aware Lexical Retrieval.
Implements robust Lucene-style smoothed BM25 scoring over contextualized code tokens
with camelCase/snake_case identifier expansion, exact symbol boosts, and generic-term filtering.
"""
import re
import math
import structlog
from typing import List, Dict, Any, Tuple, Set, Optional
from collections import Counter

logger = structlog.get_logger(__name__)

# Standard stop words
STOPWORDS: Set[str] = {
    "the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for", "of",
    "with", "by", "from", "as", "about", "into", "through", "what", "where", "which",
    "how", "who", "when", "why", "does", "do", "did", "can", "could", "should", "would",
    "this", "that", "these", "those", "it", "its", "and", "or", "not", "be", "been",
}

# Generic software terms that must NOT produce high-confidence matches on their own
GENERIC_CODE_TERMS: Set[str] = {
    "service", "services", "manager", "managers", "manage", "manages", "managing",
    "controller", "controllers", "system", "systems", "app", "application", "applications",
    "module", "modules", "function", "functions", "method", "methods",
    "class", "classes", "data", "file", "files",
    "handler", "handlers", "handle", "handles", "handling",
    "helper", "helpers", "util", "utils", "utility", "utilities",
    "component", "components", "item", "items", "object", "objects", "entity", "entities",
    "impl", "impls", "base", "core", "test", "tests", "code",
    "run", "runs", "running", "process", "processes", "processing",
    "execute", "executes", "execution", "create", "creates", "creating",
    "get", "gets", "set", "sets", "show", "shows", "list", "lists",
}


def tokenize_code(text: str) -> List[str]:
    """
    Intelligently tokenize source code and natural language queries.
    Splits on punctuation, whitespace, camelCase, PascalCase, and snake_case.
    E.g. 'getUserProfile' -> ['getuserprofile', 'get', 'user', 'profile']
         'payment_service.py' -> ['payment_service', 'payment', 'service', 'py']
    """
    if not text:
        return []

    raw_tokens = re.findall(r"[A-Za-z0-9_]+", text)
    tokens = []

    for raw in raw_tokens:
        lower_raw = raw.lower()
        if lower_raw not in STOPWORDS and len(lower_raw) > 1:
            tokens.append(lower_raw)

        # camelCase / PascalCase sub-token extraction
        sub_tokens = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|\d+", raw)
        if len(sub_tokens) > 1:
            for st in sub_tokens:
                st_lower = st.lower()
                if st_lower not in STOPWORDS and len(st_lower) > 1:
                    tokens.append(st_lower)

        # snake_case sub-token extraction
        if "_" in raw:
            for part in raw.split("_"):
                part_lower = part.lower()
                if part_lower not in STOPWORDS and len(part_lower) > 1:
                    tokens.append(part_lower)

    return tokens


class RobustBM25:
    """
    Lucene-style BM25 with strictly positive smoothed IDF:
    IDF(t) = ln(1.0 + (N - n + 0.5) / (n + 0.5))
    Guarantees consistent ranking for both small test cases and large repositories.
    """

    def __init__(self, corpus: List[List[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.doc_lengths = [len(doc) for doc in corpus]
        self.avg_doc_len = sum(self.doc_lengths) / max(1, self.corpus_size)

        # Compute document frequencies and term frequencies
        self.doc_freqs: Dict[str, int] = Counter()
        self.doc_term_freqs: List[Counter] = []

        for doc in corpus:
            tf = Counter(doc)
            self.doc_term_freqs.append(tf)
            for term in tf.keys():
                self.doc_freqs[term] += 1

        # Precompute strictly positive smoothed IDF
        self.idf: Dict[str, float] = {}
        for term, freq in self.doc_freqs.items():
            self.idf[term] = math.log(1.0 + (self.corpus_size - freq + 0.5) / (freq + 0.5))

    def get_scores(self, query: List[str]) -> List[float]:
        scores = [0.0] * self.corpus_size
        for term in query:
            if term not in self.idf:
                continue
            t_idf = self.idf[term]

            for i in range(self.corpus_size):
                tf = self.doc_term_freqs[i].get(term, 0)
                if tf == 0:
                    continue
                doc_len = self.doc_lengths[i]
                numerator = tf * (self.k1 + 1.0)
                denominator = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / max(1.0, self.avg_doc_len)))
                scores[i] += t_idf * (numerator / denominator)

        return scores


class LexicalRetriever:
    """
    Lexical search engine for repository chunks using smoothed BM25 and identifier heuristics.
    """

    def __init__(self, chunks: Optional[List[Dict[str, Any]]] = None):
        self.chunks = chunks or []
        self.chunk_id_map: Dict[str, Dict[str, Any]] = {c["chunk_id"]: c for c in self.chunks}
        self.corpus_tokens: List[List[str]] = []
        self.bm25: Optional[RobustBM25] = None

        if self.chunks:
            self._build_index()

    def _build_index(self):
        self.corpus_tokens = []
        for c in self.chunks:
            text_to_tokenize = f"{c.get('contextualized_text', '')} {c.get('file_path', '')} {c.get('symbol_name', '')}"
            tokens = tokenize_code(text_to_tokenize)
            self.corpus_tokens.append(tokens)

        if self.corpus_tokens:
            self.bm25 = RobustBM25(self.corpus_tokens)

    def search(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """
        Search chunks for query tokens.
        Applies generic term filtering, exact symbol boosts, and score normalization.
        Returns sorted list of (chunk_id, normalized_lexical_score).
        """
        if not self.chunks or not query.strip() or not self.bm25:
            return []

        query_tokens = tokenize_code(query)
        if not query_tokens:
            return []

        # Identify informative (non-generic) vs generic query tokens
        informative_tokens = [t for t in query_tokens if t not in GENERIC_CODE_TERMS]
        has_informative_tokens = len(informative_tokens) > 0

        raw_scores = self.bm25.get_scores(query_tokens)

        scored_results = []
        max_score = max(raw_scores) if len(raw_scores) > 0 and max(raw_scores) > 0 else 1.0

        for idx, chunk in enumerate(self.chunks):
            base_score = float(raw_scores[idx])
            norm_score = base_score / max_score if max_score > 0 else 0.0

            sym = (chunk.get("symbol_name") or "").lower()
            cls = (chunk.get("class_name") or "").lower()
            fpath = (chunk.get("file_path") or "").lower()

            exact_boost = 0.0
            matched_informative = 0

            for t in query_tokens:
                is_generic = t in GENERIC_CODE_TERMS
                is_exact = (t == sym or t == cls or t in fpath.split("/"))

                if is_exact:
                    exact_boost += 0.4 if not is_generic else 0.05

                # Check if this informative token actually appears in this chunk's tokens
                if not is_generic and t in self.corpus_tokens[idx]:
                    matched_informative += 1

            # ── Generic-Term False-Match Suppression ──────────────────────────
            # If the user asked an informative question (e.g. "Bitcoin payment service"),
            # but this chunk ONLY matched generic terms (e.g. "service"), apply a severe penalty!
            if has_informative_tokens and matched_informative == 0:
                norm_score *= 0.05
                exact_boost *= 0.1

            final_lex_score = min(1.0, norm_score * 0.7 + exact_boost)

            if final_lex_score > 0.05:
                scored_results.append((chunk["chunk_id"], final_lex_score))

        scored_results.sort(key=lambda x: x[1], reverse=True)
        return scored_results[:top_k]
