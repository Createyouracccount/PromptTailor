"""Target-model auto-detection.

Priority (measured 2026-08-11, see LOOP_LOG.md R1):
  1. explicit argument (CLI --model)
  2. transcript JSONL last assistant record's message.model
     (hook input itself carries NO model field — measured). Hooks get
     transcript_path; slash commands (/pm) don't, so the transcript is found
     from CLAUDE_CODE_SESSION_ID → <config>/projects/*/<id>.jsonl (R46: the
     model picked in the app never reaches settings.json, so settings alone
     reported "sonnet" while the session ran Opus 5.5)
  3. project .claude/settings.local.json / settings.json "model"
  4. user ~/.claude/settings.json "model"  (may carry suffix like "[1m]")
  5. None (caller falls back to default)
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

TAIL_BYTES = 4 * 1024 * 1024  # transcripts grow to many MB; the answer is near the end


def normalize_model(model_id: str | None) -> str | None:
    """Map any model id/alias spelling to a profile stem."""
    if not model_id:
        return None
    m = re.sub(r"\[.*?\]", "", model_id).strip().lower()  # strip "[1m]" etc.
    if "fable" in m or "mythos" in m:
        return "fable-5"
    if "opus" in m:
        return "opus-5"
    if "sonnet" in m:
        return "sonnet-5"
    if "haiku" in m:
        return "haiku-4-5"
    return None


def _tail_lines(path: Path, max_bytes: int = TAIL_BYTES) -> list[str]:
    with path.open("rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - max_bytes))
        data = f.read()
    lines = data.decode("utf-8", errors="replace").splitlines()
    return lines[1:] if size > max_bytes else lines  # first line may be cut


def _model_from_transcript(transcript_path: str | None) -> str | None:
    if not transcript_path:
        return None
    p = Path(transcript_path)
    if not p.is_file():
        return None
    try:
        lines = _tail_lines(p)
    except OSError:
        return None
    for line in reversed(lines):
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and d.get("type") == "assistant":
            model = (d.get("message") or {}).get("model")
            if model and normalize_model(model):  # skip "<synthetic>" error records
                return model
    return None


def session_transcript_path() -> str | None:
    """Current Claude Code session's transcript, for callers without hook input."""
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if not re.fullmatch(r"[0-9A-Za-z-]{8,64}", sid):
        return None
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    try:
        hits = sorted((config / "projects").glob(f"*/{sid}.jsonl"),
                      key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return None
    return str(hits[0]) if hits else None


def _model_from_settings(cwd: str | None) -> str | None:
    candidates: list[Path] = []
    if cwd:
        candidates += [
            Path(cwd) / ".claude" / "settings.local.json",
            Path(cwd) / ".claude" / "settings.json",
        ]
    candidates.append(Path.home() / ".claude" / "settings.json")
    for p in candidates:
        try:
            model = json.loads(p.read_text(encoding="utf-8")).get("model")
        except (OSError, json.JSONDecodeError):
            continue
        if model:
            return model
    return None


def detect_model_with_source(hook_input: dict | None = None) -> tuple[str | None, str | None]:
    """Return (profile stem, source) — source is "transcript", "settings" or None."""
    hook_input = hook_input or {}
    transcript = hook_input.get("transcript_path") or session_transcript_path()
    for source, raw in (
        ("transcript", lambda: _model_from_transcript(transcript)),
        ("settings", lambda: _model_from_settings(hook_input.get("cwd"))),
    ):
        stem = normalize_model(raw())
        if stem:
            return stem, source
    return None, None


def detect_model(hook_input: dict | None = None) -> str | None:
    """Return a profile stem (e.g. 'fable-5') or None if undetectable."""
    return detect_model_with_source(hook_input)[0]
