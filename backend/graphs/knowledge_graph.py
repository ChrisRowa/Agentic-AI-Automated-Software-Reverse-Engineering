"""
Program Knowledge Graph Builder.
Constructs a NetworkX-based graph from parsed AST/structural data.
Each node and edge carries evidence (file, line, tool).
No LLM involved here — purely deterministic.
"""
import networkx as nx
import structlog
import json
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict

logger = structlog.get_logger(__name__)


class ProgramKnowledgeGraph:
    """
    Builds and manages the repository-level program knowledge graph.
    
    Nodes represent: files, classes, functions, modules, APIs
    Edges represent: CALLS, IMPORTS, DEPENDS_ON, DEFINES, INHERITS, etc.
    Every edge includes evidence metadata.
    """

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.graph = nx.DiGraph()
        self.node_registry: Dict[str, Dict] = {}  # qualified_name -> node data
        self.edge_evidence: Dict[Tuple, List[Dict]] = defaultdict(list)

    def build_from_parse_results(
        self,
        manifest: Dict[str, Any],
        parse_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Build the full knowledge graph from discovery manifest and parse results.
        Returns serializable graph data.
        """
        logger.info("Building Program Knowledge Graph", project_id=self.project_id)

        # Step 1: Add repository node
        repo_id = self._add_node(
            node_id="REPO:root",
            node_type="REPOSITORY",
            label="Repository",
            properties={"project_id": self.project_id},
        )

        # Step 2: Add file nodes and CONTAINS edges from repo → file
        file_nodes: Dict[str, str] = {}  # relative_path -> node_id
        module_nodes: Dict[str, str] = {}  # module_name -> node_id

        for file_rec in manifest.get("files", []):
            if file_rec.get("is_ignored"):
                continue

            file_id = f"FILE:{file_rec['relative_path']}"
            self._add_node(
                node_id=file_id,
                node_type="FILE",
                label=file_rec["filename"],
                qualified_name=file_rec["relative_path"],
                file_path=file_rec["relative_path"],
                language=file_rec.get("language"),
                properties={
                    "extension": file_rec.get("extension"),
                    "lines_of_code": file_rec.get("lines_of_code"),
                    "is_test": file_rec.get("is_test_file"),
                    "is_config": file_rec.get("is_config_file"),
                },
            )
            file_nodes[file_rec["relative_path"]] = file_id

            self._add_edge(
                source_id=repo_id,
                target_id=file_id,
                rel_type="CONTAINS",
                evidence={
                    "file": file_rec["relative_path"],
                    "type": "MANIFEST",
                    "tool": "repository_discovery",
                },
            )

            # Module node
            module = file_rec.get("module_name")
            if module and module not in module_nodes:
                mod_id = f"MODULE:{module}"
                self._add_node(
                    node_id=mod_id,
                    node_type="MODULE",
                    label=module,
                    properties={},
                )
                module_nodes[module] = mod_id
                self._add_edge(repo_id, mod_id, "CONTAINS", {
                    "type": "DISCOVERY", "tool": "repository_discovery"
                })

            if module and module in module_nodes:
                self._add_edge(module_nodes[module], file_id, "CONTAINS", {
                    "file": file_rec["relative_path"],
                    "type": "MODULE_FILE", "tool": "repository_discovery"
                })

        # Step 3: Add class/function/method nodes from parse results
        class_nodes: Dict[str, str] = {}  # qualified_name -> node_id
        function_nodes: Dict[str, str] = {}

        for cls in parse_results.get("all_classes", []):
            qualified = f"{cls['file']}::{cls['name']}"
            cls_id = f"CLASS:{qualified}"
            self._add_node(
                node_id=cls_id,
                node_type="CLASS",
                label=cls["name"],
                qualified_name=qualified,
                file_path=cls["file"],
                line_start=cls.get("line_start"),
                line_end=cls.get("line_end"),
                language=cls.get("language"),
                properties={
                    "bases": cls.get("bases", []),
                    "decorators": cls.get("decorators", []),
                    "docstring": cls.get("docstring"),
                    "is_abstract": cls.get("is_abstract", False),
                },
            )
            class_nodes[qualified] = cls_id
            class_nodes[cls["name"]] = cls_id  # also by simple name

            # FILE DEFINES CLASS
            file_id = file_nodes.get(cls["file"])
            if file_id:
                self._add_edge(file_id, cls_id, "DEFINES", {
                    "file": cls["file"],
                    "line_start": cls.get("line_start"),
                    "line_end": cls.get("line_end"),
                    "type": "AST",
                    "tool": "python_ast",
                })

            # INHERITANCE edges
            for base in cls.get("bases", []):
                base_name = base.split(".")[-1] if "." in base else base
                if base_name in class_nodes:
                    self._add_edge(cls_id, class_nodes[base_name], "INHERITS", {
                        "file": cls["file"],
                        "line_start": cls.get("line_start"),
                        "type": "AST_INHERITANCE",
                        "tool": "python_ast",
                    })

            # Add methods
            for method in cls.get("methods", []):
                mq = f"{cls['file']}::{cls['name']}.{method['name']}"
                mid = f"FUNCTION:{mq}"
                self._add_node(
                    node_id=mid,
                    node_type="METHOD",
                    label=method["name"],
                    qualified_name=mq,
                    file_path=cls["file"],
                    line_start=method.get("line_start"),
                    line_end=method.get("line_end"),
                    language=cls.get("language"),
                    properties={
                        "parameters": method.get("parameters", []),
                        "return_type": method.get("return_type"),
                        "decorators": method.get("decorators", []),
                        "is_async": method.get("is_async", False),
                        "docstring": method.get("docstring"),
                        "complexity": method.get("complexity_indicator"),
                    },
                )
                function_nodes[mq] = mid
                function_nodes[f"{cls['name']}.{method['name']}"] = mid

                self._add_edge(cls_id, mid, "DEFINES", {
                    "file": cls["file"],
                    "line_start": method.get("line_start"),
                    "type": "AST",
                    "tool": "python_ast",
                })

        # Module-level functions
        for fn in parse_results.get("all_functions", []):
            fq = f"{fn['file']}::{fn['name']}"
            fid = f"FUNCTION:{fq}"
            self._add_node(
                node_id=fid,
                node_type="FUNCTION",
                label=fn["name"],
                qualified_name=fq,
                file_path=fn["file"],
                line_start=fn.get("line_start"),
                line_end=fn.get("line_end"),
                language=fn.get("language"),
                properties={
                    "parameters": fn.get("parameters", []),
                    "return_type": fn.get("return_type"),
                    "docstring": fn.get("docstring"),
                    "is_async": fn.get("is_async", False),
                    "complexity": fn.get("complexity_indicator"),
                },
            )
            function_nodes[fq] = fid
            function_nodes[fn["name"]] = fid

            file_id = file_nodes.get(fn["file"])
            if file_id:
                self._add_edge(file_id, fid, "DEFINES", {
                    "file": fn["file"],
                    "line_start": fn.get("line_start"),
                    "type": "AST",
                    "tool": "python_ast",
                })

        # Step 4: Import / dependency edges
        import_graph: Dict[str, List[str]] = defaultdict(list)  # file -> [imported files]

        for imp in parse_results.get("all_imports", []):
            source_file = imp.get("file")
            if not source_file:
                continue

            source_id = file_nodes.get(source_file)
            if not source_id:
                continue

            # Resolve relative imports to actual files
            module = imp.get("module", "")
            target_path = self._resolve_import_to_file(
                module, source_file, list(file_nodes.keys()),
                is_relative=imp.get("is_relative", False),
                level=imp.get("level", 0),
            )

            if target_path and target_path in file_nodes:
                target_id = file_nodes[target_path]
                self._add_edge(source_id, target_id, "IMPORTS", {
                    "file": source_file,
                    "line_start": imp.get("line"),
                    "type": "IMPORT",
                    "tool": "python_ast",
                    "module": module,
                })
                import_graph[source_file].append(target_path)

        # Step 5: Call graph — match function calls to definitions
        call_edges = self._build_call_graph(
            parse_results.get("all_functions", []),
            parse_results.get("all_classes", []),
            function_nodes,
        )

        stats = {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "files": len(file_nodes),
            "modules": len(module_nodes),
            "classes": len(class_nodes) // 2,  # deduplicated
            "functions": len([n for n in self.graph.nodes if n.startswith("FUNCTION:")]),
            "call_edges": call_edges,
            "import_edges": sum(len(v) for v in import_graph.values()),
        }

        logger.info("Knowledge graph built", **stats)
        return {
            "stats": stats,
            "graph_data": self.to_serializable(),
        }

    def _build_call_graph(
        self,
        all_functions: List[Dict],
        all_classes: List[Dict],
        function_nodes: Dict[str, str],
    ) -> int:
        """Build CALLS edges from function call analysis."""
        call_count = 0

        for fn in all_functions:
            caller_name = fn["name"]
            caller_file = fn["file"]
            caller_key = f"{caller_file}::{caller_name}"
            caller_id = function_nodes.get(caller_key) or function_nodes.get(caller_name)

            if not caller_id:
                continue

            for call in fn.get("local_calls", []):
                callee_name = call["name"]
                # Try to find callee
                callee_id = (
                    function_nodes.get(callee_name) or
                    function_nodes.get(f"{caller_file}::{callee_name}")
                )
                if callee_id and callee_id != caller_id:
                    self._add_edge(caller_id, callee_id, "CALLS", {
                        "file": caller_file,
                        "line_start": call.get("line"),
                        "type": "CALL",
                        "tool": "python_ast",
                    })
                    call_count += 1

        # Also process method calls
        for cls in all_classes:
            for method in cls.get("methods", []):
                caller_key = f"{cls['file']}::{cls['name']}.{method['name']}"
                caller_id = function_nodes.get(caller_key)
                if not caller_id:
                    continue
                for call in method.get("local_calls", []):
                    callee_name = call["name"]
                    callee_id = function_nodes.get(callee_name)
                    if callee_id and callee_id != caller_id:
                        self._add_edge(caller_id, callee_id, "CALLS", {
                            "file": cls["file"],
                            "line_start": call.get("line"),
                            "type": "CALL",
                            "tool": "python_ast",
                        })
                        call_count += 1

        return call_count

    def _resolve_import_to_file(
        self,
        module: str,
        source_file: str,
        all_files: List[str],
        is_relative: bool = False,
        level: int = 0,
    ) -> Optional[str]:
        """Try to resolve an import module string to an actual file path."""
        if not module:
            return None

        # Python: relative imports
        if is_relative and level > 0:
            source_parts = source_file.replace("\\", "/").split("/")
            base_parts = source_parts[:-level]
            module_parts = module.split(".")
            candidate_parts = base_parts + module_parts
            for ext in [".py", "/__init__.py"]:
                candidate = "/".join(candidate_parts) + ext.replace("/__init__", "/__init__")
                if candidate in all_files:
                    return candidate
            # Try as __init__.py
            candidate = "/".join(candidate_parts) + "/__init__.py"
            if candidate in all_files:
                return candidate

        # Absolute import — try as file
        module_path = module.replace(".", "/")
        for ext in [".py", ".js", ".ts", ".jsx", ".tsx"]:
            candidate = module_path + ext
            if candidate in all_files:
                return candidate
        # Try as package __init__.py
        candidate = module_path + "/__init__.py"
        if candidate in all_files:
            return candidate

        return None

    def _add_node(
        self,
        node_id: str,
        node_type: str,
        label: str,
        qualified_name: Optional[str] = None,
        file_path: Optional[str] = None,
        line_start: Optional[int] = None,
        line_end: Optional[int] = None,
        language: Optional[str] = None,
        module: Optional[str] = None,
        properties: Optional[Dict] = None,
    ) -> str:
        self.graph.add_node(
            node_id,
            node_type=node_type,
            label=label,
            qualified_name=qualified_name or node_id,
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            language=language,
            module=module,
            properties=properties or {},
        )
        self.node_registry[node_id] = {"label": label, "type": node_type}
        return node_id

    def _add_edge(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        evidence: Dict[str, Any],
    ):
        if not self.graph.has_node(source_id) or not self.graph.has_node(target_id):
            return
        if self.graph.has_edge(source_id, target_id):
            # Add evidence to existing edge
            existing = self.graph[source_id][target_id].get("evidence", [])
            existing.append(evidence)
            self.graph[source_id][target_id]["evidence"] = existing
        else:
            self.graph.add_edge(
                source_id,
                target_id,
                relationship_type=rel_type,
                evidence=[evidence],
                weight=1.0,
                confidence=1.0,
            )

    def to_serializable(self) -> Dict[str, Any]:
        """Convert graph to JSON-serializable format for API responses."""
        nodes = []
        for node_id, data in self.graph.nodes(data=True):
            nodes.append({
                "id": node_id,
                "node_type": data.get("node_type"),
                "label": data.get("label"),
                "qualified_name": data.get("qualified_name"),
                "file_path": data.get("file_path"),
                "line_start": data.get("line_start"),
                "line_end": data.get("line_end"),
                "language": data.get("language"),
                "module": data.get("module"),
                "properties": data.get("properties", {}),
            })

        edges = []
        for src, tgt, data in self.graph.edges(data=True):
            evidence = data.get("evidence", [])
            first_ev = evidence[0] if evidence else {}
            edges.append({
                "id": f"{src}__{tgt}",
                "source_id": src,
                "target_id": tgt,
                "relationship_type": data.get("relationship_type"),
                "evidence_file": first_ev.get("file"),
                "evidence_line_start": first_ev.get("line_start"),
                "evidence_line_end": first_ev.get("line_end"),
                "evidence_type": first_ev.get("type"),
                "evidence_source": first_ev.get("tool"),
                "weight": data.get("weight", 1.0),
                "confidence": data.get("confidence", 1.0),
                "all_evidence": evidence,
            })

        return {"nodes": nodes, "edges": edges}

    def get_call_graph(self, scope_type: Optional[str] = None) -> Dict[str, Any]:
        """Return only CALLS edges for the call graph view."""
        nodes = {}
        edges = []
        for src, tgt, data in self.graph.edges(data=True):
            if data.get("relationship_type") != "CALLS":
                continue
            src_data = dict(self.graph.nodes[src])
            tgt_data = dict(self.graph.nodes[tgt])
            nodes[src] = src_data
            nodes[tgt] = tgt_data
            edges.append({
                "source_id": src,
                "target_id": tgt,
                "evidence": data.get("evidence", []),
            })
        return {
            "nodes": list(nodes.values()),
            "edges": edges,
            "node_ids": list(nodes.keys()),
        }

    def get_dependency_graph(self) -> Dict[str, Any]:
        """Return IMPORTS / DEPENDS_ON edges."""
        nodes = {}
        edges = []
        for src, tgt, data in self.graph.edges(data=True):
            if data.get("relationship_type") not in {"IMPORTS", "DEPENDS_ON"}:
                continue
            nodes[src] = dict(self.graph.nodes[src])
            nodes[tgt] = dict(self.graph.nodes[tgt])
            edges.append({
                "source_id": src,
                "target_id": tgt,
                "relationship_type": data.get("relationship_type"),
                "evidence": data.get("evidence", []),
            })
        return {"nodes": list(nodes.values()), "edges": edges}

    def get_neighbors(self, node_id: str, depth: int = 1) -> Dict[str, Any]:
        """Get neighboring nodes up to a given depth."""
        visited = set()
        frontier = {node_id}
        result_nodes = {}
        result_edges = []

        for _ in range(depth):
            next_frontier = set()
            for n in frontier:
                if n in visited:
                    continue
                visited.add(n)
                if n in self.graph:
                    result_nodes[n] = dict(self.graph.nodes[n])
                    for neighbor in list(self.graph.successors(n)) + list(self.graph.predecessors(n)):
                        next_frontier.add(neighbor)
                        if self.graph.has_edge(n, neighbor):
                            result_edges.append({
                                "source_id": n,
                                "target_id": neighbor,
                                **dict(self.graph[n][neighbor]),
                            })
                        elif self.graph.has_edge(neighbor, n):
                            result_edges.append({
                                "source_id": neighbor,
                                "target_id": n,
                                **dict(self.graph[neighbor][n]),
                            })
            frontier = next_frontier - visited

        return {"nodes": list(result_nodes.values()), "edges": result_edges}

    def find_paths(self, source_id: str, target_id: str) -> List[List[str]]:
        """Find all simple paths between two nodes."""
        try:
            paths = list(nx.all_simple_paths(self.graph, source_id, target_id, cutoff=8))
            return paths[:10]  # Limit to 10 paths
        except nx.NetworkXNoPath:
            return []
        except nx.NodeNotFound:
            return []

    def compute_pagerank(self) -> Dict[str, float]:
        """Compute PageRank for node importance ranking."""
        try:
            return nx.pagerank(self.graph, weight="weight")
        except Exception:
            return {}

    def get_strongly_connected_components(self) -> List[List[str]]:
        """Find strongly connected components (potential cycles)."""
        try:
            sccs = list(nx.strongly_connected_components(self.graph))
            return [list(c) for c in sccs if len(c) > 1]
        except Exception:
            return []
