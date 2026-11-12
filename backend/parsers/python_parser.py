"""
Python AST parser using Python's built-in `ast` module.
Extracts: classes, functions, methods, imports, calls, decorators,
docstrings, control flow, data flow hints.
No code execution — pure static analysis.
"""
import ast
import structlog
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

logger = structlog.get_logger(__name__)


class PythonASTParser:
    """
    Parses a Python source file and extracts structural information.
    Uses Python's built-in `ast` module — deterministic, no LLM.
    """

    def __init__(self, file_path: str, relative_path: str):
        self.file_path = Path(file_path)
        self.relative_path = relative_path
        self.source: Optional[str] = None
        self.tree: Optional[ast.AST] = None
        self.errors: List[Dict] = []

    def parse(self) -> Dict[str, Any]:
        """Parse the file and return extracted information."""
        try:
            self.source = self.file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return self._error_result(f"File read error: {e}")

        try:
            self.tree = ast.parse(self.source, filename=str(self.file_path))
        except SyntaxError as e:
            return self._error_result(f"Python syntax error at line {e.lineno}: {e.msg}")

        return {
            "file": self.relative_path,
            "language": "Python",
            "classes": self._extract_classes(),
            "functions": self._extract_module_functions(),
            "imports": self._extract_imports(),
            "calls": self._extract_calls(),
            "module_docstring": ast.get_docstring(self.tree),
            "global_variables": self._extract_globals(),
            "errors": self.errors,
            "success": True,
        }

    def _extract_classes(self) -> List[Dict[str, Any]]:
        classes = []
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if not self._is_top_level_class(node):
                continue

            bases = []
            for base in node.bases:
                try:
                    bases.append(ast.unparse(base))
                except Exception:
                    bases.append("?")

            methods = []
            class_vars = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                    methods.append(self._extract_function_info(item, class_name=node.name))
                elif isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name):
                            class_vars.append(target.id)

            decorators = [self._unparse_decorator(d) for d in node.decorator_list]

            classes.append({
                "name": node.name,
                "line_start": node.lineno,
                "line_end": node.end_lineno,
                "bases": bases,
                "methods": methods,
                "class_variables": class_vars,
                "decorators": decorators,
                "docstring": ast.get_docstring(node),
                "is_abstract": any("ABC" in b or "Abstract" in b for b in bases),
            })
        return classes

    def _extract_module_functions(self) -> List[Dict[str, Any]]:
        """Extract top-level functions (not methods)."""
        functions = []
        for node in self.tree.body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                functions.append(self._extract_function_info(node))
        return functions

    def _extract_function_info(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef,
        class_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Extract detailed information about a function/method."""
        params = []
        for arg in node.args.args:
            param = {"name": arg.arg, "type": None}
            if arg.annotation:
                try:
                    param["type"] = ast.unparse(arg.annotation)
                except Exception:
                    pass
            params.append(param)

        return_type = None
        if node.returns:
            try:
                return_type = ast.unparse(node.returns)
            except Exception:
                pass

        decorators = [self._unparse_decorator(d) for d in node.decorator_list]

        # Extract local calls within this function
        local_calls = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                call_name = self._get_call_name(child)
                if call_name:
                    local_calls.append({
                        "name": call_name,
                        "line": getattr(child, "lineno", None),
                    })

        # Detect if async
        is_async = isinstance(node, ast.AsyncFunctionDef)

        # Detect if property / staticmethod / classmethod
        is_property = any("property" in d for d in decorators)
        is_static = any("staticmethod" in d for d in decorators)
        is_classmethod = any("classmethod" in d for d in decorators)

        return {
            "name": node.name,
            "class_name": class_name,
            "qualified_name": f"{class_name}.{node.name}" if class_name else node.name,
            "line_start": node.lineno,
            "line_end": node.end_lineno,
            "parameters": params,
            "return_type": return_type,
            "decorators": decorators,
            "docstring": ast.get_docstring(node),
            "is_async": is_async,
            "is_property": is_property,
            "is_static": is_static,
            "is_classmethod": is_classmethod,
            "local_calls": local_calls,
            "complexity_indicator": self._estimate_complexity(node),
        }

    def _extract_imports(self) -> List[Dict[str, Any]]:
        imports = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({
                        "type": "import",
                        "module": alias.name,
                        "alias": alias.asname,
                        "line": node.lineno,
                        "is_stdlib": self._is_stdlib(alias.name),
                        "is_relative": False,
                    })
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append({
                        "type": "from_import",
                        "module": module,
                        "name": alias.name,
                        "alias": alias.asname,
                        "line": node.lineno,
                        "is_relative": node.level > 0,
                        "level": node.level,
                        "is_stdlib": self._is_stdlib(module),
                    })
        return imports

    def _extract_calls(self) -> List[Dict[str, Any]]:
        """Extract all function calls in the file with context."""
        calls = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                name = self._get_call_name(node)
                if name:
                    calls.append({
                        "name": name,
                        "line": getattr(node, "lineno", None),
                    })
        return calls

    def _extract_globals(self) -> List[Dict[str, Any]]:
        globals_list = []
        for node in self.tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        globals_list.append({
                            "name": target.id,
                            "line": node.lineno,
                        })
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    ann = None
                    try:
                        ann = ast.unparse(node.annotation)
                    except Exception:
                        pass
                    globals_list.append({
                        "name": node.target.id,
                        "type": ann,
                        "line": node.lineno,
                    })
        return globals_list

    def _get_call_name(self, node: ast.Call) -> Optional[str]:
        """Extract function call name from AST Call node."""
        try:
            if isinstance(node.func, ast.Name):
                return node.func.id
            elif isinstance(node.func, ast.Attribute):
                parts = []
                cur = node.func
                while isinstance(cur, ast.Attribute):
                    parts.append(cur.attr)
                    cur = cur.value
                if isinstance(cur, ast.Name):
                    parts.append(cur.id)
                return ".".join(reversed(parts))
        except Exception:
            pass
        return None

    def _unparse_decorator(self, node: ast.expr) -> str:
        try:
            return ast.unparse(node)
        except Exception:
            return "unknown"

    def _is_top_level_class(self, node: ast.ClassDef) -> bool:
        """Check if a class is at module level (not nested)."""
        for item in self.tree.body:
            if item is node:
                return True
        return False

    def _is_stdlib(self, module: str) -> bool:
        """Rough check if module is from standard library."""
        stdlib_prefixes = {
            "os", "sys", "re", "json", "math", "datetime", "collections",
            "itertools", "functools", "pathlib", "typing", "abc", "io",
            "logging", "unittest", "threading", "multiprocessing", "asyncio",
            "contextlib", "dataclasses", "enum", "hashlib", "hmac",
            "http", "urllib", "socket", "ssl", "struct", "time",
            "copy", "pprint", "string", "textwrap", "uuid", "warnings",
            "inspect", "importlib", "pkgutil", "platform", "shutil",
            "tempfile", "traceback", "types", "weakref", "gc", "dis",
        }
        root = module.split(".")[0] if module else ""
        return root in stdlib_prefixes

    def _estimate_complexity(self, node: ast.FunctionDef) -> str:
        """Estimate cyclomatic complexity (simplified)."""
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler,
                                  ast.With, ast.Assert, ast.comprehension)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        if complexity <= 5:
            return "low"
        elif complexity <= 10:
            return "medium"
        return "high"

    def _error_result(self, message: str) -> Dict[str, Any]:
        return {
            "file": self.relative_path,
            "language": "Python",
            "classes": [],
            "functions": [],
            "imports": [],
            "calls": [],
            "errors": [{"message": message}],
            "success": False,
        }
