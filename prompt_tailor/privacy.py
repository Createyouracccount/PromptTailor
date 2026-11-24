"""Keep real user prompts out of the repository.

Real /pm requests live only on the user's machine:
  - runs/pm_command.log, runs/hook.log (this checkout, gitignored)
  - ~/.claude/plugins/cache/prompt-tailor/*/*/runs/*.log (installed plugin)
  - ~/.claude/prompt-tailor/cases.jsonl (/prompt-tailor:feedback cases)

Benchmarks, tests and docs must use synthetic examples. `find_leaks` checks
file contents against those local sources by normalized text overlap, so a
paraphrase that keeps a long run of the original wording is still caught.
`scripts/check_private.py` runs it as a pre-commit hook; CI cannot see the
local logs, so CI instead rejects tracked items marked `"private": true`
(what `prompt-tailor cases --export` writes).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .usage import usage_path

# Korean: a run of WINDOW characters (whitespace removed) holding at least
# MIN_HANGUL syllables. Other text: WORDS consecutive words. Shorter real
# prompts are matched only as a whole quoted string.
WINDOW = 9
MIN_HANGUL = 5
WORDS = 6
MIN_WHOLE = 5
_HANGUL = re.compile(r"[가-힣ㄱ-ㅎ]")

_LOG_RAW = re.compile(r"""(?:raw=|\): )'(.*?)'?$""")


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text.replace("\\n", "\n"))


def _plugin_cache_logs() -> list[Path]:
    base = Path.home() / ".claude" / "plugins" / "cache" / "prompt-tailor"
    if not base.is_dir():
        return []
    return sorted(base.glob("*/*/runs/*.log"))


def default_sources(extra: list[Path] | None = None) -> list[Path]:
    # The installed plugin's logs hold real usage. This checkout's own
    # runs/*.log hold development test inputs that the golden sets reuse on
    # purpose, so they are opt-in (extra sources) rather than defaults.
    paths: list[Path] = list(_plugin_cache_logs())
    paths.append(usage_path().parent / "cases.jsonl")
    paths += extra or []
    return [p for p in paths if p.is_file()]


def load_private_texts(sources: list[Path]) -> list[str]:
    """Pull user-written text out of the local logs and cases file."""
    texts: list[str] = []
    for path in sources:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            if path.suffix == ".jsonl":
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(d, dict):
                    texts += [str(d[k]) for k in ("raw", "context", "expected") if d.get(k)]
            else:
                m = _LOG_RAW.search(line)
                if m:
                    texts.append(m.group(1))
    return [t for t in texts if len(_norm(t)) >= MIN_WHOLE]


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _keys(text: str) -> list[str]:
    """Overlap keys for one text: Hangul-rich char windows + word windows."""
    keys = []
    n = _norm(text)
    for j in range(len(n) - WINDOW + 1):
        g = n[j:j + WINDOW]
        if len(_HANGUL.findall(g)) >= MIN_HANGUL:
            keys.append(g)
    w = _words(text)
    keys += [" ".join(w[j:j + WORDS]) for j in range(len(w) - WORDS + 1)]
    return keys


def build_index(private_texts: list[str]) -> tuple[dict[str, int], dict[str, int]]:
    """Return (overlap key → text id, short whole text → text id)."""
    keys: dict[str, int] = {}
    whole: dict[str, int] = {}
    for i, t in enumerate(private_texts):
        ks = _keys(t)
        if not ks:
            whole.setdefault(_norm(t), i)
        for k in ks:
            keys.setdefault(k, i)
    return keys, whole


def find_leaks(files: dict[str, str], private_texts: list[str]) -> list[tuple[str, str]]:
    """Return (file, matched snippet) pairs. The snippet is the overlapping
    run only — never the full private text — so the report itself is safe
    to show."""
    keys, whole = build_index(private_texts)
    leaks: list[tuple[str, str]] = []
    for name, content in files.items():
        present = set(_keys(content))
        seen: set[int] = set()
        for k, i in keys.items():
            if i not in seen and k in present:
                seen.add(i)
                leaks.append((name, k))
        for w, i in whole.items():
            if i not in seen and _quoted(w, content):
                seen.add(i)
                leaks.append((name, w))
    return leaks


def _quoted(short: str, content: str) -> bool:
    # Short prompts ("ok check it") are only flagged as a whole quoted string,
    # otherwise common words would trip the check.
    for q in re.findall(r"""["'“‘「](.{1,40}?)["'”’」]""", content):
        if _norm(q) == short:
            return True
    return False


def private_marked_ids(jsonl_text: str) -> list[str]:
    """IDs of JSONL items marked private (exported real cases)."""
    out = []
    for line in jsonl_text.splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and (d.get("private") or str(d.get("source", "")).startswith("feedback:")):
            out.append(str(d.get("id", "?")))
    return out
