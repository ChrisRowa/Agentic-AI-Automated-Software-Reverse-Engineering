"""
Parser dispatcher — selects the right parser for each language.
Handles multi-language repository parsing.
"""
import structlog
from pathlib import Path
from typing import Dict, Any, Optional

from backend.parsers.python_parser import PythonASTParser
from backend.parsers.javascript_parser import JavaScriptParser, TypeScriptParser

logger = structlog.get_logger(__name__)

# Languages we can deeply analyze
SUPPORTED_PARSERS = {
    "Python": PythonASTParser,
    "JavaScript": JavaScriptParser,
    "TypeScript": TypeScriptParser,
}


def parse_file(
    file_path: str,
    relative_path: str,
    language: str,
) -> Optional[Dict[str, Any]]:
    """
    Parse a single file and return extracted AST/structure information.
    Returns None if the language is not supported.
    """
    parser_class = SUPPORTED_PARSERS.get(language)
    if not parser_class:
        return {
            "file": relative_path,
            "language": language,
            "supported": False,
            "message": f"Language {language} not yet supported for deep analysis.",
            "classes": [],
            "functions": [],
            "imports": [],
            "calls": [],
            "success": False,
        }

    try:
        parser = parser_class(file_path=file_path, relative_path=relative_path)
        result = parser.parse()
        result["supported"] = True
        return result
    except Exception as e:
        logger.warning("Parser error", file=relative_path, language=language, error=str(e))
        return {
            "file": relative_path,
            "language": language,
            "supported": True,
            "classes": [],
            "functions": [],
            "imports": [],
            "calls": [],
            "errors": [{"message": str(e)}],
            "success": False,
        }


def parse_repository(
    extraction_path: str,
    file_records: list,
) -> Dict[str, Any]:
    """
    Parse all supported files in the repository.
    Returns aggregate parse results.
    """
    from pathlib import Path
    root = Path(extraction_path)

    results = []
    all_classes = []
    all_functions = []
    all_imports = []
    all_calls = []
    parse_errors = []
    unsupported_languages = set()

    total = len(file_records)
    parsed = 0

    for i, file_record in enumerate(file_records):
        language = file_record.get("language")
        if not language or file_record.get("is_config_file") or file_record.get("is_documentation"):
            continue

        rel_path = file_record["relative_path"]
        abs_path = root / rel_path

        if not abs_path.exists():
            continue

        result = parse_file(
            file_path=str(abs_path),
            relative_path=rel_path,
            language=language,
        )

        if not result:
            continue

        results.append(result)

        if not result.get("supported", True):
            unsupported_languages.add(language)
            continue

        if result.get("success"):
            parsed += 1
            for cls in result.get("classes", []):
                cls["file"] = rel_path
                cls["language"] = language
                all_classes.append(cls)

            for fn in result.get("functions", []):
                fn["file"] = rel_path
                fn["language"] = language
                all_functions.append(fn)

            for imp in result.get("imports", []):
                imp["file"] = rel_path
                all_imports.append(imp)

            for call in result.get("calls", []):
                call["file"] = rel_path
                all_calls.append(call)
        else:
            parse_errors.extend(result.get("errors", []))

    logger.info(
        "Repository parsing complete",
        total_files=total,
        parsed=parsed,
        classes=len(all_classes),
        functions=len(all_functions),
        imports=len(all_imports),
    )

    return {
        "file_results": results,
        "all_classes": all_classes,
        "all_functions": all_functions,
        "all_imports": all_imports,
        "all_calls": all_calls,
        "parse_errors": parse_errors,
        "unsupported_languages": list(unsupported_languages),
        "stats": {
            "total_files": total,
            "parsed_files": parsed,
            "total_classes": len(all_classes),
            "total_functions": len(all_functions),
            "total_imports": len(all_imports),
            "total_calls": len(all_calls),
        },
    }
