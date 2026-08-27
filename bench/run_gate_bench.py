"""Clarity-gate benchmark: does the rewriter correctly decide rewrite vs keep?

Dataset: bench/gate_set.jsonl — 40 labeled prompts:
  - 20 "rewrite" (vague; the golden set, where rewrites measured 20/20 better)
  - 20 "keep" (already-clear; includes the 3 task-outcome-pilot prompts where
    the raw prompt beat the rewrite 3-0)

Runs the /pm & MCP path (concise + intent routing) and scores the gate's
action against the label. Reports accuracy, per-class recall, and the
confusion matrix. Raw model outputs preserved in the results file.

Usage: python3 bench/run_gate_bench.py [--workers K]
Writes bench/gate_results.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from prompt_tailor.engine import rewrite  # noqa: E402

TARGET = "fable-5"


def process(item: dict) -> dict:
    rec = dict(item)
    try:
        r = rewrite(item["raw"], TARGET, concise=True, retries=1, timeout=90)
        rec["action"] = r.action
        rec["rewritten_prompt"] = r.rewritten_prompt
        rec["correct"] = (r.action == item["label"])
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {e}"
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default=str(ROOT / "bench" / "gate_results.json"),
                    help="결과 JSON 경로 (안정성 반복 실행 시 회차별 파일 지정)")
    args = ap.parse_args()

    items = [json.loads(l) for l in (ROOT / "bench" / "gate_set.jsonl").open(encoding="utf-8")]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(process, items))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    ok = [r for r in results if "action" in r]
    errors = [r for r in results if "error" in r]
    cm = {"rewrite/rewrite": 0, "rewrite/keep": 0, "keep/keep": 0, "keep/rewrite": 0}
    for r in ok:
        cm[f"{r['label']}/{r['action']}"] += 1
    n = len(ok)
    correct = cm["rewrite/rewrite"] + cm["keep/keep"]
    print(f"n={n} errors={len(errors)}")
    print(f"accuracy: {correct}/{n} = {correct / n:.0%}" if n else "no results")
    print(f"vague recall   (rewrite→rewrite): {cm['rewrite/rewrite']}/{cm['rewrite/rewrite'] + cm['rewrite/keep']}")
    print(f"clear recall   (keep→keep):       {cm['keep/keep']}/{cm['keep/keep'] + cm['keep/rewrite']}")
    print(f"confusion (label/action): {cm}")
    miss = [f"{r['id']}({r['label']}→{r['action']})" for r in ok if not r["correct"]]
    if miss:
        print("misses:", ", ".join(miss))
    for r in errors:
        print(f"ERROR {r['id']}: {r['error']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
