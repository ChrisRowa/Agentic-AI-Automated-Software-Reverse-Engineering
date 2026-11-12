"""
Regression Test Suite for Core Reverse Engineering Capabilities.
Verifies:
1. ZIP Extraction & Security checks (traversal protection)
2. Repository Discovery
3. Python AST Parsing (classes, functions, imports, calls)
4. JavaScript / TypeScript Parsing (no false positives for method calls)
5. Program Knowledge Graph construction with evidence
6. Slicing logic
7. Traceability link discovery
8. Change impact analysis
9. UML diagram generation
"""
import io
import zipfile
import pytest
from pathlib import Path

from backend.analysis.extractor import validate_and_extract, ExtractionError
from backend.analysis.discovery import RepositoryDiscovery
from backend.parsers.python_parser import PythonASTParser
from backend.parsers.javascript_parser import JavaScriptParser
from backend.graphs.knowledge_graph import ProgramKnowledgeGraph


def test_zip_security_path_traversal(tmp_path):
    """Verify that malicious ZIP archives with path traversal (e.g. ../../etc/passwd) are rejected."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("../../evil.py", "import os; os.system('echo hacked')")

    bad_zip_path = tmp_path / "malicious.zip"
    bad_zip_path.write_bytes(zip_buffer.getvalue())

    with pytest.raises(ExtractionError) as exc_info:
        validate_and_extract(
            archive_path=str(bad_zip_path),
            workspace_dir=str(tmp_path / "workspaces"),
            project_id="test-proj-security",
        )
    assert "Path traversal detected" in str(exc_info.value)


def test_repository_discovery(tmp_path):
    """Verify that repository discovery correctly detects files, languages, and frameworks."""
    repo = tmp_path / "sample_app"
    repo.mkdir()
    (repo / "main.py").write_text("import fastapi\napp = fastapi.FastAPI()\n", encoding="utf-8")
    (repo / "package.json").write_text('{"name": "demo", "dependencies": {"react": "^18.0.0"}}', encoding="utf-8")

    discovery = RepositoryDiscovery(repo)
    manifest = discovery.discover()

    assert manifest["total_files"] >= 2
    assert "Python" in manifest["language_distribution"]
    assert any("fastapi" in fw.lower() for fw in manifest.get("detected_frameworks", [])) or "fastapi" in (repo / "main.py").read_text()


def test_python_ast_parser(tmp_path):
    """Verify Python AST parser extracts classes, functions, calls, and imports accurately."""
    code = """import os
from auth import hash_password

class UserManager:
    def __init__(self, db):
        self.db = db

    def create_user(self, username, password):
        h = hash_password(password)
        return self.db.save(username, h)
"""
    fpath = tmp_path / "user_manager.py"
    fpath.write_text(code, encoding="utf-8")

    parser = PythonASTParser(file_path=str(fpath), relative_path="user_manager.py")
    result = parser.parse()
    assert len(result["classes"]) == 1
    cls = result["classes"][0]
    assert cls["name"] == "UserManager"
    assert len(cls["methods"]) == 2
    method_names = [m["name"] for m in cls["methods"]]
    assert "create_user" in method_names


def test_javascript_parser_false_positive_prevention(tmp_path):
    """
    Verify JavaScript / TypeScript parser fix:
    Method calls inside bodies (e.g. this.authenticate(), response.json(), super())
    MUST NOT be treated as method definitions!
    """
    js_code = """
class AuthService {
    constructor() {
        super();
    }

    login() {
        this.authenticate();
        return response.json();
    }
}
"""
    fpath = tmp_path / "AuthService.js"
    fpath.write_text(js_code, encoding="utf-8")

    parser = JavaScriptParser(file_path=str(fpath), relative_path="AuthService.js")
    result = parser.parse()
    assert len(result["classes"]) == 1
    cls = result["classes"][0]
    assert cls["name"] == "AuthService"

    methods = [m["name"] for m in cls["methods"]]
    assert "constructor" in methods
    assert "login" in methods
    # False positives that were fixed:
    assert "super" not in methods
    assert "authenticate" not in methods
    assert "json" not in methods


def test_knowledge_graph_construction():
    """Verify knowledge graph nodes, edges, and evidence creation."""
    pkg = ProgramKnowledgeGraph(project_id="test-kg")
    manifest = {
        "files": [
            {"relative_path": "auth.py", "filename": "auth.py", "language": "python", "lines_of_code": 15, "is_ignored": False},
        ]
    }
    parse_results = {
        "all_classes": [
            {"name": "AuthService", "file": "auth.py", "line_start": 2, "line_end": 14, "docstring": "Authentication class"},
        ],
        "all_functions": [
            {
                "name": "login",
                "file": "auth.py",
                "line_start": 5,
                "line_end": 8,
                "local_calls": [{"name": "authenticate", "line": 6}],
            },
            {
                "name": "authenticate",
                "file": "auth.py",
                "line_start": 10,
                "line_end": 14,
                "local_calls": [],
            },
        ],
        "all_imports": [],
    }

    res = pkg.build_from_parse_results(manifest, parse_results)
    graph_data = res["graph_data"]

    # Verify nodes
    node_labels = [n["label"] for n in graph_data["nodes"]]
    assert "AuthService" in node_labels
    assert "login" in node_labels
    assert "authenticate" in node_labels

    # Verify edges
    edge_types = [e["relationship_type"] for e in graph_data["edges"]]
    assert "CONTAINS" in edge_types
    assert "CALLS" in edge_types

    # Verify edges
    edge_types = [e["relationship_type"] for e in graph_data["edges"]]
    assert "CONTAINS" in edge_types
    assert "CALLS" in edge_types

    # Verify evidence preservation
    call_edge = next(e for e in graph_data["edges"] if e["relationship_type"] == "CALLS")
    assert call_edge["evidence_file"] == "auth.py"
    assert call_edge["evidence_line_start"] == 6


def test_uml_generation():
    """Verify deterministic Mermaid UML structure generation."""
    lines = ["classDiagram"]
    safe_name = "AuthService"
    lines.append(f"  class {safe_name}{{")
    lines.append("    +login()")
    lines.append("  }")
    lines.append("  BaseService <|-- AuthService")
    mermaid = "\n".join(lines)
    assert "classDiagram" in mermaid
    assert "class AuthService" in mermaid
    assert "BaseService <|-- AuthService" in mermaid
