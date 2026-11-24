"""Local failure cases — the improvement loop's raw material (v0.3).

usage.jsonl tells us *how often* /pm runs but never *whether it helped*.
`/prompt-tailor:feedback` closes that gap: when a /pm result was off, the
session model (which still has the conversation) writes one case — the raw
request, the context needed to read it, what /pm understood, what went
wrong, and what it should have done.

Cases live next to usage.jsonl in ~/.claude/prompt-tailor/cases.jsonl.
Unlike usage events they DO contain prompt text, so they are written only
when the user explicitly runs the feedback command, and they never leave
the machine. `prompt-tailor cases --export` turns them into
bench/context_set.jsonl-format items so real failures become regression
tests for the next rule change.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from .usage import usage_path

CATEGORIES = (
    "context_miss",      # 지시어·후속 요청을 맥락과 다르게 해석
    "over_scope",        # 요청보다 넓게 부풀림
    "under_scope",       # 요청의 일부를 빠뜨림
    "stalled",           # 되묻기만 하고 결과물이 없음
    "question_to_task",  # 질문을 실행 과제로 바꿈
    "wrong_keep",        # 보강이 필요했는데 그대로 수행 (또는 그 반대)
    "invented",          # 없는 사실을 지어냄
    "other",
)
REQUIRED = ("raw", "problem")
FIELDS = ("raw", "context", "interpretation", "problem", "expected", "category", "note")
MAX_FIELD_CHARS = 2000


def cases_path() -> Path:
    return usage_path().parent / "cases.jsonl"


def normalize_case(data: dict) -> dict:
    """Validate and trim a case dict. Raises ValueError on missing essentials."""
    if not isinstance(data, dict):
        raise ValueError("case must be a JSON object")
    case: dict = {}
    for key in FIELDS:
        val = data.get(key)
        if val is None:
            continue
        val = str(val).strip()
        if val:
            case[key] = val[:MAX_FIELD_CHARS]
    missing = [k for k in REQUIRED if not case.get(k)]
    if missing:
        raise ValueError(f"missing required field(s): {', '.join(missing)}")
    if case.get("category") not in CATEGORIES:
        case["category"] = "other"
    return case


def record_case(data: dict, version: str | None = None) -> tuple[dict, int]:
    """Append one case; return (stored case, total case count)."""
    case = normalize_case(data)
    case = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **case}
    if version:
        case["version"] = version
    path = cases_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(case, ensure_ascii=False) + "\n")
    return case, len(load_cases())


def load_cases() -> list[dict]:
    path = cases_path()
    if not path.exists():
        return []
    out = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(d, dict) and d.get("raw"):
                out.append(d)
    return out


def to_bench_items(cases: list[dict], prefix: str = "case") -> list[dict]:
    """Map cases to context-bench items (same schema as bench/context_set.jsonl)."""
    items = []
    for i, c in enumerate(cases, 1):
        kind = "question" if c.get("category") == "question_to_task" else "followup"
        items.append({
            "id": f"{prefix}{i:03d}",
            "kind": kind,
            "context": c.get("context", ""),
            "raw": c["raw"],
            "expected": c.get("expected") or f"(미기재) 문제: {c['problem']}",
            "source": f"feedback:{c.get('category', 'other')}:{c.get('ts', '')}",
            "private": True,  # real prompt text — keep under gitignored bench/private/
        })
    return items


def format_cases(cases: list[dict]) -> str:
    if not cases:
        return f"기록된 사례가 없습니다. (파일: {cases_path()})\n/pm 결과가 별로였을 때 /prompt-tailor:feedback 으로 기록하세요."
    by_cat: dict[str, int] = {}
    for c in cases:
        by_cat[c.get("category", "other")] = by_cat.get(c.get("category", "other"), 0) + 1
    lines = [f"PromptTailor 실패 사례 {len(cases)}건 — 파일: {cases_path()} (로컬 전용)", ""]
    lines.append("  유형별: " + " · ".join(f"{k} {v}" for k, v in sorted(by_cat.items(), key=lambda x: -x[1])))
    lines.append("")
    for c in cases[-10:]:
        raw = c["raw"].replace("\n", " ")
        lines.append(f"  [{c.get('ts', '?')}] {c.get('category', 'other')}: {raw[:50]!r}")
        lines.append(f"      문제: {c['problem'][:90]}")
    if len(cases) > 10:
        lines.append(f"  … 최근 10건만 표시 (전체 {len(cases)}건)")
    return "\n".join(lines)
