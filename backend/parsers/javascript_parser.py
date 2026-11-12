"""
JavaScript / TypeScript parser using regex-based and basic AST analysis.
For production, this wraps a Node.js analysis script using tree-sitter.
Extracts: classes, functions, imports, exports, calls, interfaces.
"""
import re
import json
import subprocess
import structlog
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = structlog.get_logger(__name__)


class JavaScriptParser:
    """
    Parses JavaScript/TypeScript files using regex-based analysis.
    Designed to be replaced by tree-sitter JS parser once installed.
    """

    def __init__(self, file_path: str, relative_path: str, language: str = "JavaScript"):
        self.file_path = Path(file_path)
        self.relative_path = relative_path
        self.language = language
        self.source: Optional[str] = None

    def parse(self) -> Dict[str, Any]:
        try:
            self.source = self.file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return self._error_result(f"File read error: {e}")

        return {
            "file": self.relative_path,
            "language": self.language,
            "classes": self._extract_classes(),
            "functions": self._extract_functions(),
            "imports": self._extract_imports(),
            "exports": self._extract_exports(),
            "calls": self._extract_calls(),
            "interfaces": self._extract_interfaces() if self.language == "TypeScript" else [],
            "errors": [],
            "success": True,
        }

    def _extract_classes(self) -> List[Dict[str, Any]]:
        classes = []
        pattern = re.compile(
            r"class\s+(\w+)(?:\s+extends\s+([\w.]+))?(?:\s+implements\s+([\w,\s]+))?\s*\{",
            re.MULTILINE,
        )
        lines = self.source.splitlines()

        for m in pattern.finditer(self.source):
            line_num = self.source[:m.start()].count("\n") + 1
            name = m.group(1)
            base = m.group(2)
            implements = [i.strip() for i in m.group(3).split(",")] if m.group(3) else []

            # Extract methods within this class block
            methods = self._extract_class_methods(m.start(), name)

            classes.append({
                "name": name,
                "line_start": line_num,
                "line_end": None,
                "extends": base,
                "implements": implements,
                "methods": methods,
            })
        return classes

    def _extract_class_methods(self, class_start: int, class_name: str) -> List[Dict]:
        """
        Extract methods from a class body strictly at class member scope (depth == 1).
        Distinguishes MethodDefinition from CallExpression (e.g. super(), authenticate(), json()).
        Handles comments and string literals so braces inside them don't throw off depth tracking.
        """
        methods = []
        brace_depth = 0
        in_class = False
        i = class_start
        n = len(self.source)

        in_single_quote = False
        in_double_quote = False
        in_template_literal = False
        in_line_comment = False
        in_block_comment = False

        NON_METHOD_NAMES = {
            "if", "for", "while", "switch", "catch", "super", "return",
            "throw", "new", "import", "export", "default", "case", "try",
            "finally", "typeof", "instanceof", "void", "delete", "in", "of",
        }

        while i < n:
            ch = self.source[i]
            next_ch = self.source[i + 1] if i + 1 < n else ""

            # 1. Handle comments & string states
            if in_line_comment:
                if ch == "\n":
                    in_line_comment = False
                i += 1
                continue
            if in_block_comment:
                if ch == "*" and next_ch == "/":
                    in_block_comment = False
                    i += 2
                    continue
                i += 1
                continue
            if in_single_quote:
                if ch == "\\" and i + 1 < n:
                    i += 2
                    continue
                if ch == "'":
                    in_single_quote = False
                i += 1
                continue
            if in_double_quote:
                if ch == "\\" and i + 1 < n:
                    i += 2
                    continue
                if ch == '"':
                    in_double_quote = False
                i += 1
                continue
            if in_template_literal:
                if ch == "\\" and i + 1 < n:
                    i += 2
                    continue
                if ch == "`":
                    in_template_literal = False
                i += 1
                continue

            # Check starts of comments/strings
            if ch == "/" and next_ch == "/":
                in_line_comment = True
                i += 2
                continue
            if ch == "/" and next_ch == "*":
                in_block_comment = True
                i += 2
                continue
            if ch == "'":
                in_single_quote = True
                i += 1
                continue
            if ch == '"':
                in_double_quote = True
                i += 1
                continue
            if ch == "`":
                in_template_literal = True
                i += 1
                continue

            # 2. Check for method declaration strictly at class member level (depth == 1)
            if in_class and brace_depth == 1:
                remainder = self.source[i:]
                method_pattern = (
                    r'^[\s\r\n]*(?:(?:public|private|protected|readonly|static|async)\s+)*'
                    r'(?:(?:get|set)\s+)?([a-zA-Z_$][\w$]*)\s*\(([^)]*)\)\s*(?::\s*[^{;]+)?\s*\{'
                )
                arrow_pattern = (
                    r'^[\s\r\n]*(?:(?:public|private|protected|readonly|static)\s+)*'
                    r'([a-zA-Z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*(?::\s*[^=>]+)?\s*=>\s*\{'
                )
                m = re.match(method_pattern, remainder) or re.match(arrow_pattern, remainder)
                if m:
                    mname = m.group(1)
                    if mname not in NON_METHOD_NAMES:
                        line_num = self.source[:i + m.start(1)].count("\n") + 1
                        methods.append({
                            "name": mname,
                            "class_name": class_name,
                            "line_start": line_num,
                            "is_async": "async" in m.group(0),
                        })
                    open_brace_idx = remainder.rfind("{", 0, m.end())
                    if open_brace_idx != -1:
                        i += open_brace_idx
                        brace_depth += 1
                        i += 1
                        continue

            # 3. Track braces for class
            if ch == '{':
                brace_depth += 1
                if brace_depth == 1:
                    in_class = True
            elif ch == '}':
                brace_depth -= 1
                if in_class and brace_depth == 0:
                    break

            i += 1

        return methods

    def _extract_functions(self) -> List[Dict[str, Any]]:
        functions = []
        patterns = [
            # function declaration
            re.compile(r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)", re.MULTILINE),
            # arrow function assigned to const/let/var
            re.compile(r"(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*=>", re.MULTILINE),
        ]
        seen = set()
        for pattern in patterns:
            for m in pattern.finditer(self.source):
                name = m.group(1)
                if name in seen:
                    continue
                seen.add(name)
                line_num = self.source[:m.start()].count("\n") + 1
                params_str = m.group(2) if m.group(2) else ""
                params = [p.strip().split(":")[0].strip() for p in params_str.split(",") if p.strip()]
                functions.append({
                    "name": name,
                    "line_start": line_num,
                    "parameters": [{"name": p} for p in params if p],
                    "is_async": "async" in self.source[max(0, m.start()-10):m.start()+20],
                    "is_exported": "export" in self.source[max(0, m.start()-10):m.start()+20],
                })
        return functions

    def _extract_imports(self) -> List[Dict[str, Any]]:
        imports = []
        # ES6 imports
        for m in re.finditer(
            r"import\s+(?:{([^}]+)}|(\w+)|\*\s+as\s+(\w+))\s+from\s+['\"]([^'\"]+)['\"]",
            self.source
        ):
            line_num = self.source[:m.start()].count("\n") + 1
            source = m.group(4)
            named = m.group(1)
            default = m.group(2)
            namespace = m.group(3)
            imports.append({
                "type": "es6_import",
                "module": source,
                "named": [n.strip() for n in named.split(",")] if named else [],
                "default": default,
                "namespace": namespace,
                "line": line_num,
                "is_relative": source.startswith("."),
            })
        # CommonJS require
        for m in re.finditer(
            r"(?:const|let|var)\s+(?:{([^}]+)}|(\w+))\s*=\s*require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",
            self.source
        ):
            line_num = self.source[:m.start()].count("\n") + 1
            imports.append({
                "type": "require",
                "module": m.group(3),
                "name": m.group(2) or m.group(1),
                "line": line_num,
                "is_relative": m.group(3).startswith("."),
            })
        return imports

    def _extract_exports(self) -> List[Dict[str, Any]]:
        exports = []
        for m in re.finditer(r"export\s+(?:default\s+)?(?:class|function|const|let|var)\s+(\w+)", self.source):
            exports.append({
                "name": m.group(1),
                "line": self.source[:m.start()].count("\n") + 1,
                "is_default": "default" in self.source[m.start():m.start()+20],
            })
        return exports

    def _extract_calls(self) -> List[Dict[str, Any]]:
        calls = []
        for m in re.finditer(r"(\w+(?:\.\w+)*)\s*\(", self.source):
            name = m.group(1)
            # Filter out language keywords
            if name not in {"if", "for", "while", "switch", "catch", "function", "class", "return", "new"}:
                calls.append({
                    "name": name,
                    "line": self.source[:m.start()].count("\n") + 1,
                })
        return calls[:500]  # Cap to avoid noise

    def _extract_interfaces(self) -> List[Dict[str, Any]]:
        """TypeScript interface extraction."""
        interfaces = []
        for m in re.finditer(r"interface\s+(\w+)(?:\s+extends\s+([\w,\s]+))?\s*\{", self.source):
            line_num = self.source[:m.start()].count("\n") + 1
            interfaces.append({
                "name": m.group(1),
                "extends": [e.strip() for e in m.group(2).split(",")] if m.group(2) else [],
                "line_start": line_num,
            })
        return interfaces

    def _error_result(self, message: str) -> Dict[str, Any]:
        return {
            "file": self.relative_path,
            "language": self.language,
            "classes": [], "functions": [], "imports": [],
            "exports": [], "calls": [],
            "errors": [{"message": message}],
            "success": False,
        }


class TypeScriptParser(JavaScriptParser):
    """TypeScript parser — extends JS parser with TS-specific patterns."""

    def __init__(self, file_path: str, relative_path: str):
        super().__init__(file_path, relative_path, language="TypeScript")
