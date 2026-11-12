"""
Repository Discovery Module.
Scans an extracted repository to detect languages, frameworks,
files, symbols at a high level, and produces a repository manifest.
"""
import os
import re
import json
import hashlib
import structlog
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict

from backend.analysis.extractor import (
    should_ignore_path, is_binary_file, get_file_content_safe,
    IGNORED_DIRS, BINARY_EXTENSIONS
)

logger = structlog.get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Language detection by extension
# ─────────────────────────────────────────────────────────────────────────────

LANGUAGE_EXTENSIONS: Dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".go": "Go",
    ".rs": "Rust",
    ".cs": "C#",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".c": "C",
    ".h": "C/C++ Header",
    ".hpp": "C++ Header",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".scala": "Scala",
    ".r": "R",
    ".R": "R",
    ".m": "MATLAB/Objective-C",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "SASS",
    ".less": "LESS",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".dart": "Dart",
    ".lua": "Lua",
    ".sh": "Shell",
    ".bash": "Bash",
    ".zsh": "Zsh",
    ".fish": "Fish",
    ".ps1": "PowerShell",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
    ".toml": "TOML",
    ".xml": "XML",
    ".sql": "SQL",
    ".graphql": "GraphQL",
    ".gql": "GraphQL",
    ".proto": "Protobuf",
    ".tf": "Terraform",
    ".hcl": "HCL",
    ".md": "Markdown",
    ".rst": "reStructuredText",
    ".txt": "Text",
    ".dockerfile": "Dockerfile",
    ".makefile": "Makefile",
}

# Supported for deep analysis (AST + call graph)
DEEPLY_SUPPORTED = {"Python", "JavaScript", "TypeScript", "Java"}

CONFIG_FILENAMES = {
    "package.json", "tsconfig.json", "babel.config.js", "webpack.config.js",
    "vite.config.ts", "vite.config.js", ".eslintrc", ".eslintrc.json",
    "requirements.txt", "pyproject.toml", "setup.py", "setup.cfg", "Pipfile",
    "pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle",
    "Cargo.toml", "go.mod", "go.sum",
    "Gemfile", "composer.json",
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    ".env", ".env.example", ".env.local",
    "Makefile", "CMakeLists.txt",
    "README.md", "README.rst", "README.txt",
    ".gitignore", ".gitattributes",
    "jest.config.js", "jest.config.ts",
    "pytest.ini", "pyproject.toml", "tox.ini",
    "nginx.conf", "apache.conf",
}

DOC_EXTENSIONS = {".md", ".rst", ".txt", ".adoc"}

TEST_INDICATORS = {"test_", "_test.", "spec.", ".spec.", ".test.", "tests/", "test/", "__tests__/"}

FRAMEWORK_INDICATORS: Dict[str, List[str]] = {
    "Django": ["manage.py", "django", "DJANGO_SETTINGS_MODULE"],
    "Flask": ["from flask", "import flask", "Flask(__name__)"],
    "FastAPI": ["from fastapi", "import fastapi", "FastAPI()"],
    "Express": ["express()", "require('express')", "require(\"express\")"],
    "React": ["import React", "from 'react'", "from \"react\""],
    "Vue": ["createApp", "from 'vue'", ".vue"],
    "Angular": ["@NgModule", "@Component", "angular"],
    "Spring": ["@SpringBootApplication", "@RestController", "spring.application"],
    "Nest.js": ["@Module", "@Controller", "@Injectable", "from '@nestjs"],
    "Next.js": ["next/router", "getServerSideProps", "next.config"],
    "Svelte": [".svelte", "svelte"],
    "Laravel": ["artisan", "Illuminate\\"],
    "Rails": ["config/routes.rb", "ActiveRecord"],
}


def detect_framework(files: List[Path], content_samples: Dict[str, str]) -> List[str]:
    """Detect frameworks from filenames and content samples."""
    detected = []
    filenames = {f.name.lower() for f in files} | {f.name for f in files}
    all_content = " ".join(content_samples.values())

    for framework, indicators in FRAMEWORK_INDICATORS.items():
        for ind in indicators:
            if ind.lower() in all_content.lower() or ind in filenames:
                if framework not in detected:
                    detected.append(framework)
                break
    return detected


def is_test_file(path: Path) -> bool:
    path_str = str(path).replace("\\", "/")
    return any(ind in path_str.lower() for ind in TEST_INDICATORS)


def is_config_file(path: Path) -> bool:
    return path.name in CONFIG_FILENAMES or path.suffix.lower() in {
        ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".env"
    }


def is_doc_file(path: Path) -> bool:
    return path.suffix.lower() in DOC_EXTENSIONS


def count_lines(content: str) -> int:
    return len(content.splitlines()) if content else 0


def file_hash(path: Path) -> str:
    try:
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


class RepositoryDiscovery:
    """
    Scans an extracted repository and builds a repository manifest.
    Does NOT execute any code.
    """

    def __init__(self, extraction_path: str):
        self.root = Path(extraction_path)
        self.manifest: Dict[str, Any] = {}

    def discover(self) -> Dict[str, Any]:
        """Run full repository discovery. Returns manifest dict."""
        logger.info("Starting repository discovery", path=str(self.root))

        all_files: List[Path] = []
        lang_counts: Dict[str, int] = defaultdict(int)
        lang_loc: Dict[str, int] = defaultdict(int)
        file_records: List[Dict[str, Any]] = []
        content_samples: Dict[str, str] = {}

        # Walk directory tree
        for dirpath, dirnames, filenames in os.walk(self.root):
            rel_dir = Path(dirpath).relative_to(self.root)

            # Prune ignored dirs in-place
            dirnames[:] = [
                d for d in dirnames
                if d not in IGNORED_DIRS and not d.startswith(".")
            ]

            for fname in filenames:
                fpath = Path(dirpath) / fname
                rel_path = fpath.relative_to(self.root)

                if should_ignore_path(rel_path):
                    continue
                if is_binary_file(fpath):
                    continue

                try:
                    size = fpath.stat().st_size
                except OSError:
                    continue

                # Skip huge files
                if size > 1_000_000:
                    continue

                ext = fpath.suffix.lower()
                language = LANGUAGE_EXTENSIONS.get(ext) or LANGUAGE_EXTENSIONS.get(fpath.suffix)

                # Read content (capped)
                content = get_file_content_safe(fpath, max_size_bytes=500_000)
                loc = count_lines(content) if content else 0

                if language:
                    lang_counts[language] += 1
                    lang_loc[language] += loc

                    # Collect small content samples for framework detection
                    if len(content_samples) < 50 and content:
                        content_samples[str(rel_path)] = content[:2000]

                file_records.append({
                    "relative_path": str(rel_path).replace("\\", "/"),
                    "filename": fname,
                    "extension": ext,
                    "language": language,
                    "size_bytes": size,
                    "lines_of_code": loc,
                    "is_test_file": is_test_file(fpath),
                    "is_config_file": is_config_file(fpath),
                    "is_documentation": is_doc_file(fpath),
                    "content_hash": file_hash(fpath),
                    "module_name": self._infer_module(rel_path),
                })
                all_files.append(fpath)

        # Determine primary language
        primary_language = None
        if lang_counts:
            primary_language = max(lang_counts, key=lambda k: lang_loc.get(k, 0))

        # Language distribution as percentages
        total_loc = sum(lang_loc.values()) or 1
        lang_distribution = {
            lang: round(loc / total_loc * 100, 1)
            for lang, loc in sorted(lang_loc.items(), key=lambda x: -x[1])
        }

        # Detect frameworks
        frameworks = detect_framework(all_files, content_samples)

        # Detect project type
        project_type = self._detect_project_type(file_records, frameworks)

        # Find configuration files
        config_files = [f["relative_path"] for f in file_records if f["is_config_file"]]
        doc_files = [f["relative_path"] for f in file_records if f["is_documentation"]]
        test_files = [f["relative_path"] for f in file_records if f["is_test_file"]]

        # Build folder tree
        folder_tree = self._build_folder_tree(file_records)

        self.manifest = {
            "root_path": str(self.root),
            "total_files": len(file_records),
            "total_loc": sum(lang_loc.values()),
            "primary_language": primary_language,
            "language_distribution": lang_distribution,
            "detected_frameworks": frameworks,
            "project_type": project_type,
            "files": file_records,
            "config_files": config_files,
            "doc_files": doc_files,
            "test_files": test_files,
            "folder_tree": folder_tree,
            "deeply_supported_languages": [
                lang for lang in lang_counts if lang in DEEPLY_SUPPORTED
            ],
            "unsupported_languages": [
                lang for lang in lang_counts if lang not in DEEPLY_SUPPORTED
            ],
        }

        logger.info(
            "Repository discovery complete",
            files=len(file_records),
            languages=list(lang_counts.keys()),
            primary=primary_language,
            frameworks=frameworks,
        )
        return self.manifest

    def _infer_module(self, rel_path: Path) -> str:
        """Infer module name from relative path."""
        parts = rel_path.parts
        if len(parts) > 1:
            return parts[0]
        return rel_path.stem

    def _detect_project_type(
        self, files: List[Dict], frameworks: List[str]
    ) -> str:
        """Heuristically determine project type."""
        filenames = {f["filename"].lower() for f in files}
        paths = " ".join(f["relative_path"] for f in files).lower()

        if "manage.py" in filenames or "Django" in frameworks:
            return "Django Web Application"
        if "Flask" in frameworks:
            return "Flask Web Application"
        if "FastAPI" in frameworks:
            return "FastAPI Web Application"
        if "Next.js" in frameworks or "React" in frameworks:
            return "React/Next.js Frontend"
        if "Angular" in frameworks:
            return "Angular Frontend"
        if "Vue" in frameworks:
            return "Vue.js Frontend"
        if "Spring" in frameworks:
            return "Spring Boot Application"
        if "package.json" in {f["filename"] for f in files}:
            return "Node.js Application"
        if "cargo.toml" in filenames:
            return "Rust Application"
        if "go.mod" in filenames:
            return "Go Application"
        if "setup.py" in filenames or "pyproject.toml" in filenames:
            return "Python Library/Application"
        if "pom.xml" in filenames or "build.gradle" in filenames:
            return "Java Application"
        return "Software Project"

    def _build_folder_tree(self, files: List[Dict]) -> List[Dict]:
        """Build hierarchical folder tree for UI display."""
        tree: Dict[str, Any] = {"name": "root", "type": "directory", "children": {}}

        for f in files:
            parts = f["relative_path"].replace("\\", "/").split("/")
            node = tree["children"]
            for i, part in enumerate(parts):
                if i == len(parts) - 1:
                    node[part] = {
                        "name": part,
                        "type": "file",
                        "path": f["relative_path"],
                        "language": f["language"],
                        "is_test": f["is_test_file"],
                        "is_config": f["is_config_file"],
                    }
                else:
                    if part not in node:
                        node[part] = {"name": part, "type": "directory", "children": {}}
                    node = node[part]["children"]

        def to_list(d: Dict) -> List[Dict]:
            result = []
            for name, v in sorted(d.items()):
                if v["type"] == "directory":
                    result.append({
                        "name": v["name"],
                        "type": "directory",
                        "children": to_list(v.get("children", {})),
                    })
                else:
                    result.append(v)
            return result

        return to_list(tree["children"])
