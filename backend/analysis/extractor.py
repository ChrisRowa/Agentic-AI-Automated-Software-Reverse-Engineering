"""
Secure ZIP/archive extraction with path traversal prevention.
Never executes uploaded code — only reads file structure.
"""
import zipfile
import os
import hashlib
import shutil
import structlog
from pathlib import Path
from typing import Tuple, List, Dict, Any, Optional
from backend.core.config import settings

logger = structlog.get_logger(__name__)

# Directories to skip during analysis (not extraction — we still extract them)
IGNORED_DIRS = {
    "node_modules", ".git", "__pycache__", ".pytest_cache",
    "build", "dist", ".gradle", "target", ".next", ".nuxt",
    "vendor", ".tox", "venv", ".venv", "env", ".env",
    "coverage", ".coverage", "htmlcoverage", ".nyc_output",
    "out", "bin", "obj", ".idea", ".vscode", ".vs",
    "Pods", "DerivedData", ".sass-cache",
}

BINARY_EXTENSIONS = {
    ".pyc", ".class", ".o", ".obj", ".exe", ".dll", ".so",
    ".dylib", ".jar", ".war", ".ear", ".zip", ".tar", ".gz",
    ".bz2", ".xz", ".7z", ".rar", ".png", ".jpg", ".jpeg",
    ".gif", ".bmp", ".svg", ".ico", ".pdf", ".doc", ".docx",
    ".ppt", ".pptx", ".xls", ".xlsx", ".mp3", ".mp4", ".avi",
    ".mov", ".woff", ".woff2", ".ttf", ".eot",
}

DANGEROUS_EXTENSIONS = {
    ".sh", ".bash", ".bat", ".cmd", ".ps1", ".exe", ".dll",
    ".so", ".dylib",
}


class ExtractionError(Exception):
    """Raised when archive extraction fails validation."""
    pass


def validate_and_extract(
    archive_path: str,
    workspace_dir: str,
    project_id: str,
) -> Tuple[str, Dict[str, Any]]:
    """
    Validate a ZIP archive and extract it securely.
    Returns (extraction_path, manifest).
    Never executes any code from the archive.
    """
    archive_path = Path(archive_path)
    workspace = Path(workspace_dir) / project_id
    workspace.mkdir(parents=True, exist_ok=True)

    extraction_path = workspace / "source"
    extraction_path.mkdir(parents=True, exist_ok=True)

    logger.info("Starting archive validation", archive=str(archive_path))

    # ── Security checks ──────────────────────────────────────────────────
    if not archive_path.exists():
        raise ExtractionError(f"Archive not found: {archive_path}")

    size_bytes = archive_path.stat().st_size
    if size_bytes > settings.max_upload_size_bytes:
        raise ExtractionError(
            f"Archive size {size_bytes} exceeds limit {settings.max_upload_size_bytes}"
        )

    if not zipfile.is_zipfile(archive_path):
        raise ExtractionError("File is not a valid ZIP archive")

    with zipfile.ZipFile(archive_path, "r") as zf:
        members = zf.infolist()

        # Check file count
        if len(members) > settings.max_files_in_archive:
            raise ExtractionError(
                f"Archive contains {len(members)} files, exceeding limit {settings.max_files_in_archive}"
            )

        # Validate each member for path traversal
        for member in members:
            member_path = Path(member.filename)

            # Path traversal check: no absolute paths, no ".." components
            if member_path.is_absolute():
                raise ExtractionError(
                    f"Path traversal detected: absolute path {member.filename}"
                )
            parts = member_path.parts
            if any(part in ("..", "~") for part in parts):
                raise ExtractionError(
                    f"Path traversal detected: {member.filename}"
                )

            # Check individual file size
            if member.file_size > settings.max_single_file_size_bytes:
                logger.warning(
                    "Skipping oversized file",
                    file=member.filename,
                    size=member.file_size,
                )
                continue

            # Ensure the final path is inside extraction_path
            target = (extraction_path / member.filename).resolve()
            if not str(target).startswith(str(extraction_path.resolve())):
                raise ExtractionError(
                    f"Path traversal detected after resolve: {member.filename}"
                )

        # ── Safe extraction ──────────────────────────────────────────────
        extracted_count = 0
        skipped_count = 0

        for member in members:
            if member.file_size > settings.max_single_file_size_bytes:
                skipped_count += 1
                continue

            member_path = Path(member.filename)
            target = extraction_path / member_path

            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue

            target.parent.mkdir(parents=True, exist_ok=True)

            with zf.open(member) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)

            extracted_count += 1

    # Compute archive hash
    with open(archive_path, "rb") as f:
        archive_hash = hashlib.sha256(f.read()).hexdigest()

    manifest = {
        "extraction_path": str(extraction_path),
        "workspace_path": str(workspace),
        "archive_hash": archive_hash,
        "archive_size_bytes": size_bytes,
        "extracted_files": extracted_count,
        "skipped_files": skipped_count,
        "total_members": len(members),
    }

    logger.info(
        "Archive extracted successfully",
        extracted=extracted_count,
        skipped=skipped_count,
        path=str(extraction_path),
    )
    return str(extraction_path), manifest


def cleanup_workspace(workspace_dir: str, project_id: str):
    """Remove workspace directory for a project."""
    workspace = Path(workspace_dir) / project_id
    if workspace.exists():
        shutil.rmtree(workspace)
        logger.info("Workspace cleaned up", project_id=project_id)


def should_ignore_path(path: Path) -> bool:
    """Return True if a path should be ignored during analysis."""
    for part in path.parts:
        if part in IGNORED_DIRS:
            return True
    return False


def is_binary_file(path: Path) -> bool:
    """Return True if the file extension indicates binary content."""
    return path.suffix.lower() in BINARY_EXTENSIONS


def get_file_content_safe(file_path: Path, max_size_bytes: int = 1_000_000) -> Optional[str]:
    """Read file content safely, returning None if binary or too large."""
    import re
    try:
        if file_path.stat().st_size > max_size_bytes:
            return None
        if is_binary_file(file_path):
            return None
        content = file_path.read_text(encoding="utf-8", errors="replace")
        return content
    except Exception:
        return None


# Make Optional available
from typing import Optional
