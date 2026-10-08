"""Extract user utterances from Pi session JSONL files."""

import hashlib
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from app.models import Utterance

UTTERANCES_FILENAME = "utterances.jsonl"

# Temporary confirm whitelist for R003; final vocabulary belongs to R004.
CONFIRM_UTTERANCES = frozenset(
    {
        "好",
        "行",
        "嗯",
        "对",
        "可以",
        "继续",
        "ok",
        "okay",
        "yes",
        "y",
        "continue",
    }
)

# Whole-utterance slash commands only; absolute paths and API paths stay.
_SLASH_COMMAND_RE = re.compile(r"^/[A-Za-z][\w-]*(?:\s+.*)?$")
_ABSOLUTE_OR_API_PREFIXES = (
    "/Users/",
    "/home/",
    "/var/",
    "/tmp/",
    "/etc/",
    "/opt/",
    "/usr/",
    "/api/",
    "/v1/",
    "/v2/",
)


def join_user_text(content: Any) -> str:
    """Join text parts from a user message content payload."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts)


def is_slash_command(text: str) -> bool:
    """Return True when the whole utterance is a slash command."""
    stripped = text.strip()
    if not stripped.startswith("/"):
        return False
    if stripped.startswith(_ABSOLUTE_OR_API_PREFIXES):
        return False
    return _SLASH_COMMAND_RE.fullmatch(stripped) is not None


def is_confirm_utterance(text: str) -> bool:
    """Return True for low-information confirmation short replies."""
    return text.strip().casefold() in CONFIRM_UTTERANCES


def make_utterance_id(session_id: str, entry_id: str) -> str:
    """Build a stable short hash from session_id + entry_id."""
    digest = hashlib.sha256(f"{session_id}:{entry_id}".encode()).hexdigest()
    return digest[:16]


def project_key_from_source(source_file: Path) -> str:
    """Use the sessions subdirectory name as project_key when present."""
    parts = source_file.parts
    if len(parts) >= 2:
        return parts[0]
    return source_file.stem


def _iter_session_files(sessions_dir: Path) -> Iterator[Path]:
    yield from sorted(sessions_dir.rglob("*.jsonl"))


def _parse_json_line(line: str) -> dict[str, Any] | None:
    stripped = line.strip()
    if not stripped:
        return None
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _extract_from_file(path: Path, sessions_dir: Path) -> tuple[list[Utterance], dict[str, int]]:
    stats = {
        "skipped_slash": 0,
        "skipped_confirm": 0,
        "skipped_empty": 0,
        "skipped_no_session": 0,
    }
    utterances: list[Utterance] = []
    session_id = ""
    cwd = ""
    relative = path.relative_to(sessions_dir).as_posix()
    project_key = project_key_from_source(Path(relative))

    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            entry = _parse_json_line(line)
            if entry is None:
                continue

            entry_type = entry.get("type")
            if entry_type == "session":
                session_id = str(entry.get("id") or session_id)
                cwd = str(entry.get("cwd") or cwd)
                continue

            if entry_type != "message":
                continue

            message = entry.get("message")
            if not isinstance(message, dict) or message.get("role") != "user":
                continue

            if not session_id:
                stats["skipped_no_session"] += 1
                continue

            text = join_user_text(message.get("content")).strip()
            if not text:
                stats["skipped_empty"] += 1
                continue
            if is_slash_command(text):
                stats["skipped_slash"] += 1
                continue
            if is_confirm_utterance(text):
                stats["skipped_confirm"] += 1
                continue

            entry_id = str(entry.get("id") or "")
            timestamp = str(entry.get("timestamp") or "")
            utterances.append(
                Utterance(
                    utterance_id=make_utterance_id(session_id, entry_id),
                    session_id=session_id,
                    entry_id=entry_id,
                    timestamp=timestamp,
                    cwd=cwd,
                    project_key=project_key,
                    text=text,
                    char_len=len(text),
                    source_file=relative,
                )
            )

    return utterances, stats


def extract_sessions(sessions_dir: Path, out_dir: Path) -> dict[str, Any]:
    """Scan sessions JSONL files and write filtered utterances.jsonl."""
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / UTTERANCES_FILENAME

    utterance_count = 0
    session_file_count = 0
    skipped_slash = 0
    skipped_confirm = 0
    skipped_empty = 0
    skipped_no_session = 0
    project_keys: set[str] = set()

    with output_path.open("w", encoding="utf-8") as handle:
        for path in _iter_session_files(sessions_dir):
            session_file_count += 1
            utterances, stats = _extract_from_file(path, sessions_dir)
            skipped_slash += stats["skipped_slash"]
            skipped_confirm += stats["skipped_confirm"]
            skipped_empty += stats["skipped_empty"]
            skipped_no_session += stats["skipped_no_session"]
            for utterance in utterances:
                handle.write(json.dumps(utterance.to_dict(), ensure_ascii=False) + "\n")
                utterance_count += 1
                project_keys.add(utterance.project_key)

    return {
        "sessions_dir": str(sessions_dir),
        "out_dir": str(out_dir),
        "output_path": str(output_path),
        "session_file_count": session_file_count,
        "utterance_count": utterance_count,
        "project_count": len(project_keys),
        "skipped_slash": skipped_slash,
        "skipped_confirm": skipped_confirm,
        "skipped_empty": skipped_empty,
        "skipped_no_session": skipped_no_session,
    }


def extract_summary_lines(payload: dict[str, Any]) -> list[str]:
    """Render a compact human summary for extract results."""
    return [
        f"sessions_dir: {payload['sessions_dir']}",
        f"output_path: {payload['output_path']}",
        f"session_file_count: {payload['session_file_count']}",
        f"utterance_count: {payload['utterance_count']}",
        f"project_count: {payload['project_count']}",
        f"skipped_slash: {payload['skipped_slash']}",
        f"skipped_confirm: {payload['skipped_confirm']}",
        f"skipped_empty: {payload['skipped_empty']}",
    ]
