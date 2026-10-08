"""Extract user utterances from Pi session JSONL files."""

import hashlib
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from app.models import ExtractResult, Utterance

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

# Whole-utterance slash commands only. The command name must be followed by
# whitespace or end of text, so absolute paths and API paths never match.
_SLASH_COMMAND_RE = re.compile(r"/[A-Za-z][\w-]*(?:\s.*)?", re.DOTALL)


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
    """Parse one JSONL line; return None for blank lines, raise ValueError unless it is a JSON object."""
    stripped = line.strip()
    if not stripped:
        return None
    payload = json.loads(stripped)
    if not isinstance(payload, dict):
        raise ValueError("JSONL line is not an object")
    return payload


def _iter_file_utterances(path: Path, sessions_dir: Path, result: ExtractResult) -> Iterator[Utterance]:
    """Yield kept utterances from one session file, counting skips into result."""
    session_id = ""
    cwd = ""
    relative = path.relative_to(sessions_dir).as_posix()
    project_key = project_key_from_source(Path(relative))

    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                entry = _parse_json_line(line)
            except ValueError:  # JSONDecodeError is a ValueError subclass
                result.skipped_malformed += 1
                continue
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
                result.skipped_no_session += 1
                continue

            text = join_user_text(message.get("content")).strip()
            if not text:
                result.skipped_empty += 1
                continue
            if is_slash_command(text):
                result.skipped_slash += 1
                continue
            if is_confirm_utterance(text):
                result.skipped_confirm += 1
                continue

            entry_id = str(entry.get("id") or "")
            yield Utterance(
                utterance_id=make_utterance_id(session_id, entry_id),
                session_id=session_id,
                entry_id=entry_id,
                timestamp=str(entry.get("timestamp") or ""),
                cwd=cwd,
                project_key=project_key,
                text=text,
                char_len=len(text),
                source_file=relative,
            )


def extract_sessions(sessions_dir: Path, out_dir: Path) -> ExtractResult:
    """Scan sessions JSONL files and atomically write filtered utterances.jsonl."""
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / UTTERANCES_FILENAME
    tmp_path = output_path.with_name(output_path.name + ".tmp")
    result = ExtractResult(sessions_dir=str(sessions_dir), out_dir=str(out_dir), output_path=str(output_path))
    project_keys: set[str] = set()

    try:
        with tmp_path.open("w", encoding="utf-8") as handle:
            for path in _iter_session_files(sessions_dir):
                result.session_file_count += 1
                for utterance in _iter_file_utterances(path, sessions_dir, result):
                    handle.write(json.dumps(utterance.to_dict(), ensure_ascii=False) + "\n")
                    result.utterance_count += 1
                    project_keys.add(utterance.project_key)
        tmp_path.replace(output_path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise

    result.project_count = len(project_keys)
    return result
