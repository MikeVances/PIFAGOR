"""Card queue utilities for managing incoming/action/archive files."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from services import (
    INCOMING_PHOTOS_DIR,
    ACTIONS_QUEUE_DIR,
    ACTIONS_IN_PROGRESS_DIR,
    ARCHIVE_PHOTOS_DIR,
    ERROR_PHOTOS_DIR,
)

SEQUENCE_FILE = ACTIONS_QUEUE_DIR / "sequence.txt"

DIRECTORIES = (
    INCOMING_PHOTOS_DIR,
    ACTIONS_QUEUE_DIR,
    ACTIONS_IN_PROGRESS_DIR,
    ARCHIVE_PHOTOS_DIR,
    ERROR_PHOTOS_DIR,
)


def ensure_dirs() -> None:
    for directory in DIRECTORIES:
        directory.mkdir(parents=True, exist_ok=True)


def _list_files(directory: Path) -> list[Path]:
    return sorted(
        f for f in directory.iterdir() if f.is_file() and not f.name.startswith(".")
    )


def _load_sequence() -> int:
    if not SEQUENCE_FILE.exists():
        return 0
    try:
        return int(SEQUENCE_FILE.read_text().strip() or 0)
    except ValueError:
        return 0


def _save_sequence(value: int) -> None:
    SEQUENCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEQUENCE_FILE.write_text(str(value))


def _build_queue_filename(ext: str) -> str:
    current = _load_sequence() + 1
    _save_sequence(current)
    normalized_ext = ext.lower() if ext else ""
    return f"card_{current:05d}{normalized_ext}"


def get_in_progress_file() -> Optional[Path]:
    ensure_dirs()
    files = _list_files(ACTIONS_IN_PROGRESS_DIR)
    return files[0] if files else None


def push_next_card() -> Dict[str, Optional[str]]:
    """Move next card from incoming to in-progress if needed."""
    ensure_dirs()
    current = get_in_progress_file()
    if current:
        return {
            "ok": True,
            "pushed": False,
            "filename": current.name,
            "reason": "already_in_progress",
        }

    incoming_files = _list_files(INCOMING_PHOTOS_DIR)
    if not incoming_files:
        return {
            "ok": True,
            "pushed": False,
            "filename": None,
            "reason": "no_files_in_incoming",
        }

    next_file = incoming_files[0]
    new_name = _build_queue_filename(next_file.suffix)
    target = ACTIONS_IN_PROGRESS_DIR / new_name
    next_file.rename(target)

    return {
        "ok": True,
        "pushed": True,
        "filename": target.name,
        "reason": None,
    }


def mark_card_processed(filename: str, success: bool = True) -> Dict[str, Optional[str]]:
    """Move processed file to archive or error folder and optionally prefetch next."""
    ensure_dirs()
    src = ACTIONS_IN_PROGRESS_DIR / filename
    if not src.exists():
        return {
            "ok": False,
            "pushed": False,
            "filename": None,
            "reason": "file_not_found",
        }

    target_dir = ARCHIVE_PHOTOS_DIR if success else ERROR_PHOTOS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    dst = target_dir / src.name
    src.rename(dst)

    next_info = push_next_card()
    return {
        "ok": True,
        "archived_filename": dst.name,
        "next_filename": next_info.get("filename"),
        "reason": next_info.get("reason"),
    }


def get_file_path(filename: str) -> Optional[Path]:
    ensure_dirs()
    candidate = ACTIONS_IN_PROGRESS_DIR / filename
    if candidate.exists():
        return candidate
    return None
