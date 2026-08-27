"""Local usage records — privacy-first, survives plugin updates.

Every rewrite path (hook / /pm / CLI / MCP) appends one JSON line to
``~/.claude/prompt-tailor/usage.jsonl``. That directory is stable: the
plugin cache is wiped on every plugin update, so records kept there
(runs/*.log debug logs) do not accumulate — this file does.

Privacy: events contain NO prompt text — only action, source, target
model, latency, and prompt length. The file never leaves the machine;
``prompt-tailor stats`` summarizes it locally, and ``stats --share``
prints a numbers-only block safe to paste into a GitHub issue.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from statistics import median
from typing import Iterable

# Actions: rewrite | keep | skip | error
VALID_ACTIONS = ("rewrite", "keep", "skip", "error")


def usage_path() -> Path:
    base = os.environ.get("PROMPT_TAILOR_DATA_DIR")
    root = Path(base) if base else Path.home() / ".claude" / "prompt-tailor"
    return root / "usage.jsonl"


def record_event(
    source: str,
    action: str,
    *,
    target: str | None = None,
    latency_s: float | None = None,
    prompt_chars: int | None = None,
    detail: str | None = None,
) -> None:
    """Append one usage event. Never raises — recording must not break a rewrite."""
    try:
        event: dict = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "source": source,
            "action": action,
        }
        if target:
            event["target"] = target
        if latency_s is not None:
            event["latency_s"] = round(latency_s, 1)
        if prompt_chars is not None:
            event["prompt_chars"] = prompt_chars
        if detail:
            event["detail"] = detail
        path = usage_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass


def load_events(last_days: int | None = None) -> list[dict]:
    path = usage_path()
    if not path.exists():
        return []
    cutoff = None
    if last_days is not None:
        # ts is "%Y-%m-%dT%H:%M:%S" — lexicographic compare works on the prefix
        cutoff = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() - last_days * 86400))
    events = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue  # tolerate a torn write
            if isinstance(ev, dict) and ev.get("action") in VALID_ACTIONS:
                if cutoff and str(ev.get("ts", "")) < cutoff:
                    continue
                events.append(ev)
    return events


def summarize(events: Iterable[dict]) -> dict:
    events = list(events)
    by_action: dict[str, int] = {}
    by_source: dict[str, int] = {}
    by_target: dict[str, int] = {}
    latencies: dict[str, list[float]] = {}
    skip_reasons: dict[str, int] = {}
    for ev in events:
        a, s = ev.get("action", "?"), ev.get("source", "?")
        by_action[a] = by_action.get(a, 0) + 1
        by_source[s] = by_source.get(s, 0) + 1
        if ev.get("target"):
            by_target[ev["target"]] = by_target.get(ev["target"], 0) + 1
        if isinstance(ev.get("latency_s"), (int, float)):
            latencies.setdefault(a, []).append(float(ev["latency_s"]))
        if a == "skip" and ev.get("detail"):
            skip_reasons[ev["detail"]] = skip_reasons.get(ev["detail"], 0) + 1
    gated = by_action.get("keep", 0) + by_action.get("rewrite", 0)
    return {
        "total": len(events),
        "first_ts": events[0].get("ts") if events else None,
        "last_ts": events[-1].get("ts") if events else None,
        "by_action": by_action,
        "by_source": by_source,
        "by_target": by_target,
        "skip_reasons": skip_reasons,
        "keep_rate": round(by_action.get("keep", 0) / gated, 2) if gated else None,
        "latency": {
            a: {"n": len(v), "avg_s": round(sum(v) / len(v), 1), "median_s": round(median(v), 1)}
            for a, v in latencies.items()
        },
    }


def format_stats(summary: dict, share: bool = False) -> str:
    if summary["total"] == 0:
        return "기록된 사용 이벤트가 없습니다. (파일: {})".format(usage_path())
    lines = []
    if share:
        lines.append("<!-- prompt-tailor stats --share: numbers only, no prompt text -->")
        lines.append("| metric | value |")
        lines.append("|---|---|")
        lines.append(f"| events | {summary['total']} ({summary['first_ts']} ~ {summary['last_ts']}) |")
        for a in VALID_ACTIONS:
            if a in summary["by_action"]:
                lat = summary["latency"].get(a)
                lat_s = f", median {lat['median_s']}s" if lat else ""
                lines.append(f"| {a} | {summary['by_action'][a]}{lat_s} |")
        if summary["keep_rate"] is not None:
            lines.append(f"| keep rate (gated calls) | {summary['keep_rate']:.0%} |")
        for src, n in sorted(summary["by_source"].items()):
            lines.append(f"| source:{src} | {n} |")
        return "\n".join(lines)
    lines.append(f"PromptTailor 사용 기록 — {summary['first_ts']} ~ {summary['last_ts']} ({summary['total']}건)")
    lines.append(f"파일: {usage_path()} (로컬 전용, 프롬프트 원문 미포함)")
    lines.append("")
    total = summary["total"]
    for a in VALID_ACTIONS:
        n = summary["by_action"].get(a)
        if not n:
            continue
        lat = summary["latency"].get(a)
        lat_s = f"  중앙값 {lat['median_s']}s (평균 {lat['avg_s']}s)" if lat else ""
        lines.append(f"  {a:<8}{n:>4} ({n / total:>4.0%}){lat_s}")
    if summary["keep_rate"] is not None:
        lines.append("")
        lines.append(f"  명확도 게이트 keep 비율: {summary['keep_rate']:.0%} (keep+rewrite 중)")
    if summary["skip_reasons"]:
        reasons = " · ".join(f"{k} {v}" for k, v in sorted(summary["skip_reasons"].items()))
        lines.append(f"  skip 사유: {reasons}")
    srcs = " · ".join(f"{k} {v}" for k, v in sorted(summary["by_source"].items()))
    lines.append(f"  경로별: {srcs}")
    return "\n".join(lines)
