"""
Code-aware Chunker for Hybrid RAG.
Respects program structure (classes, functions, methods, modules, docs)
while preserving exact line numbers and providing contextualized text representations.
"""
import uuid
import structlog
from typing import Dict, List, Any, Optional
from pathlib import Path

logger = structlog.get_logger(__name__)


class CodeChunker:
    """
    Splits repository source code into structural, contextualized chunks.
    Hierarchy:
      Repository -> File -> Class/Module -> Function/Method -> Bounded Chunk
    """

    def __init__(self, max_chunk_lines: int = 120, min_chunk_lines: int = 3):
        self.max_chunk_lines = max_chunk_lines
        self.min_chunk_lines = min_chunk_lines

    def chunk_repository(
        self,
        project_id: str,
        extraction_path: str,
        manifest: Dict[str, Any],
        parse_results: Dict[str, Any],
        file_id_map: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Produce a list of code chunk dictionaries for the entire repository.
        """
        logger.info("Starting code-aware chunking", project_id=project_id)
        chunks = []
        file_id_map = file_id_map or {}

        # Index parse results by file
        file_classes = {}
        for cls in parse_results.get("all_classes", []):
            fpath = cls.get("file")
            file_classes.setdefault(fpath, []).append(cls)

        file_functions = {}
        for fn in parse_results.get("all_functions", []):
            fpath = fn.get("file")
            file_functions.setdefault(fpath, []).append(fn)

        for file_rec in manifest.get("files", []):
            if file_rec.get("is_ignored"):
                continue

            rel_path = file_rec.get("relative_path")
            full_path = Path(extraction_path) / rel_path
            if not full_path.exists() or not full_path.is_file():
                continue

            try:
                content = full_path.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                logger.warning("Could not read file for chunking", file=rel_path, error=str(e))
                continue

            file_id = file_id_map.get(rel_path)
            language = file_rec.get("language") or "text"
            is_doc = file_rec.get("is_documentation", False)

            # Chunk file
            file_chunks = self.chunk_file(
                project_id=project_id,
                file_id=file_id,
                file_path=rel_path,
                content=content,
                language=language,
                is_documentation=is_doc,
                classes=file_classes.get(rel_path, []),
                functions=file_functions.get(rel_path, []),
            )
            chunks.extend(file_chunks)

        logger.info("Chunking complete", project_id=project_id, total_chunks=len(chunks))
        return chunks

    def chunk_file(
        self,
        project_id: str,
        file_id: Optional[str],
        file_path: str,
        content: str,
        language: str,
        is_documentation: bool = False,
        classes: Optional[List[Dict]] = None,
        functions: Optional[List[Dict]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Chunk a single file using AST symbol bounds where available,
        falling back to bounded block chunking for remaining code or documentation.
        """
        lines = content.splitlines()
        total_lines = len(lines)
        if total_lines == 0:
            return []

        chunks = []
        covered_lines = set()
        classes = classes or []
        functions = functions or []

        # 1. Process Functions and Methods first (most specific structural units)
        for fn in functions:
            start = fn.get("line_start")
            end = fn.get("line_end") or start
            if not start or start < 1 or start > total_lines:
                continue

            start = max(1, start)
            end = min(total_lines, max(start, end))

            fn_snippet = "\n".join(lines[start - 1:end])
            if not fn_snippet.strip():
                continue

            for l in range(start, end + 1):
                covered_lines.add(l)

            cls_name = fn.get("class_name")
            fn_name = fn.get("name", "anonymous")
            symbol_type = "method" if cls_name else "function"

            contextualized = self._build_contextualized_text(
                project_id=project_id,
                file_path=file_path,
                language=language,
                symbol_name=fn_name,
                symbol_type=symbol_type,
                class_name=cls_name,
                start_line=start,
                end_line=end,
                signature=fn.get("signature"),
                docstring=fn.get("docstring"),
                content=fn_snippet,
            )

            chunks.append({
                "chunk_id": str(uuid.uuid4()),
                "project_id": project_id,
                "file_id": file_id,
                "file_path": file_path,
                "language": language,
                "symbol_name": fn_name,
                "symbol_type": symbol_type.upper(),
                "class_name": cls_name,
                "start_line": start,
                "end_line": end,
                "chunk_type": symbol_type,
                "content": fn_snippet,
                "contextualized_text": contextualized,
                "metadata": {
                    "signature": fn.get("signature"),
                    "docstring": fn.get("docstring"),
                    "is_async": fn.get("is_async", False),
                    "parameters": fn.get("parameters", []),
                    "lines_count": end - start + 1,
                },
            })

        # 2. Process Classes (class header, docstrings, member declarations)
        for cls in classes:
            start = cls.get("line_start")
            end = cls.get("line_end") or start
            if not start or start < 1 or start > total_lines:
                continue

            start = max(1, start)
            end = min(total_lines, max(start, end))

            # Include class header + overview up to 60 lines or full class
            class_overview_end = min(end, start + min(self.max_chunk_lines, 60))
            cls_snippet = "\n".join(lines[start - 1:class_overview_end])
            cls_name = cls.get("name", "UnknownClass")

            contextualized = self._build_contextualized_text(
                project_id=project_id,
                file_path=file_path,
                language=language,
                symbol_name=cls_name,
                symbol_type="class",
                class_name=cls_name,
                start_line=start,
                end_line=end,
                signature=f"class {cls_name}",
                docstring=cls.get("docstring"),
                content=cls_snippet,
            )

            chunks.append({
                "chunk_id": str(uuid.uuid4()),
                "project_id": project_id,
                "file_id": file_id,
                "file_path": file_path,
                "language": language,
                "symbol_name": cls_name,
                "symbol_type": "CLASS",
                "class_name": cls_name,
                "start_line": start,
                "end_line": end,
                "chunk_type": "class",
                "content": cls_snippet,
                "contextualized_text": contextualized,
                "metadata": {
                    "base_classes": cls.get("base_classes", []),
                    "methods_count": len(cls.get("methods", [])),
                    "docstring": cls.get("docstring"),
                    "lines_count": end - start + 1,
                },
            })

        # 3. Bounded chunking for uncovered lines (imports, top-level code, docs, unsupported files)
        current_block = []
        block_start = None

        for idx, line in enumerate(lines, start=1):
            if idx in covered_lines:
                if current_block:
                    self._flush_uncovered_block(
                        chunks, current_block, block_start, idx - 1,
                        project_id, file_id, file_path, language, is_documentation
                    )
                    current_block = []
                    block_start = None
                continue

            if block_start is None:
                block_start = idx

            current_block.append(line)

            # If block reaches maximum size, flush it
            if len(current_block) >= self.max_chunk_lines:
                self._flush_uncovered_block(
                    chunks, current_block, block_start, idx,
                    project_id, file_id, file_path, language, is_documentation
                )
                current_block = []
                block_start = None

        # Flush trailing block
        if current_block:
            self._flush_uncovered_block(
                chunks, current_block, block_start, total_lines,
                project_id, file_id, file_path, language, is_documentation
            )

        # Fallback: if no chunks were created (e.g. tiny file or weird bounds), create full file chunk
        if not chunks and content.strip():
            contextualized = self._build_contextualized_text(
                project_id=project_id,
                file_path=file_path,
                language=language,
                symbol_name=Path(file_path).stem,
                symbol_type="file",
                class_name=None,
                start_line=1,
                end_line=total_lines,
                signature=None,
                docstring=None,
                content=content[:3000],
            )
            chunks.append({
                "chunk_id": str(uuid.uuid4()),
                "project_id": project_id,
                "file_id": file_id,
                "file_path": file_path,
                "language": language,
                "symbol_name": Path(file_path).stem,
                "symbol_type": "FILE",
                "class_name": None,
                "start_line": 1,
                "end_line": total_lines,
                "chunk_type": "file",
                "content": content,
                "contextualized_text": contextualized,
                "metadata": {"lines_count": total_lines},
            })

        return chunks

    def _flush_uncovered_block(
        self,
        chunks: List[Dict],
        block_lines: List[str],
        start: int,
        end: int,
        project_id: str,
        file_id: Optional[str],
        file_path: str,
        language: str,
        is_documentation: bool,
    ):
        text = "\n".join(block_lines).strip()
        if not text:
            return

        # Determine chunk type
        chunk_type = "documentation" if is_documentation else "module_section"
        sym_name = Path(file_path).name

        contextualized = self._build_contextualized_text(
            project_id=project_id,
            file_path=file_path,
            language=language,
            symbol_name=sym_name,
            symbol_type=chunk_type,
            class_name=None,
            start_line=start,
            end_line=end,
            signature=None,
            docstring=None,
            content=text,
        )

        chunks.append({
            "chunk_id": str(uuid.uuid4()),
            "project_id": project_id,
            "file_id": file_id,
            "file_path": file_path,
            "language": language,
            "symbol_name": sym_name,
            "symbol_type": chunk_type.upper(),
            "class_name": None,
            "start_line": start,
            "end_line": end,
            "chunk_type": chunk_type,
            "content": text,
            "contextualized_text": contextualized,
            "metadata": {"lines_count": end - start + 1, "is_documentation": is_documentation},
        })

    def _build_contextualized_text(
        self,
        project_id: str,
        file_path: str,
        language: str,
        symbol_name: Optional[str],
        symbol_type: str,
        class_name: Optional[str],
        start_line: int,
        end_line: int,
        signature: Optional[str],
        docstring: Optional[str],
        content: str,
    ) -> str:
        """
        Construct a searchable, contextualized text header prepended to the snippet.
        Crucial for high-quality lexical and semantic embedding retrieval.
        """
        hierarchy = []
        if class_name:
            hierarchy.append(f"Class: {class_name}")
        if symbol_name and symbol_name != class_name:
            hierarchy.append(f"Symbol: {symbol_name} ({symbol_type})")

        header_lines = [
            f"Repository Project: {project_id}",
            f"File: {file_path}",
            f"Language: {language}",
            f"Type: {symbol_type}",
            f"Lines: {start_line}-{end_line}",
        ]
        if hierarchy:
            header_lines.append(f"Hierarchy: {' -> '.join(hierarchy)}")
        if signature:
            header_lines.append(f"Signature: {signature}")
        if docstring:
            header_lines.append(f"Docstring: {docstring.strip()}")

        header = "\n".join(header_lines)
        return f"{header}\n\nSource:\n{content}"
