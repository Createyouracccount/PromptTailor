"""R39 속도 실험: claude -p 호출 변형별 재작성 지연 실측.

변형:
  A baseline  — 현행 (--strict-mcp-config, 기본 시스템 프롬프트 ~8k 토큰)
  B minsys    — A + --system-prompt (최소 시스템 프롬프트로 교체)
  C minsys+ss — B + --setting-sources '' (settings/CLAUDE.md 로드 생략)

각 변형 n회, 동일 메타프롬프트(모호 프롬프트 1건), 재작성 JSON 파싱 성공까지를
1회로 측정. 결과는 runs/latency_experiment.json에 저장.

Usage: python3 eval/measure_latency.py [--n 3]
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from prompt_tailor.engine import (  # noqa: E402
    DEFAULT_REWRITER_MODEL,
    build_meta_prompt,
    parse_json_output,
)

RAW = "로그인 버그 고쳐줘"
TARGET = "fable-5"

MIN_SYSTEM = "You are a prompt rewriting engine. Output only the requested JSON."

VARIANTS = {
    "A_baseline": [],
    "B_minsys": ["--system-prompt", MIN_SYSTEM],
    "C_minsys_nosettings": ["--system-prompt", MIN_SYSTEM, "--setting-sources", ""],
}


def run_once(extra_args: list[str], meta: str) -> dict:
    cmd = ["claude", "-p", "--model", DEFAULT_REWRITER_MODEL,
           "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}'] + extra_args
    t0 = time.time()
    proc = subprocess.run(cmd, input=meta, capture_output=True, text=True, timeout=120)
    dt = time.time() - t0
    rec = {"seconds": round(dt, 1), "rc": proc.returncode}
    if proc.returncode != 0:
        rec["stderr"] = proc.stderr[:300]
        return rec
    try:
        data = parse_json_output(proc.stdout)
        rec["parsed"] = True
        rec["action"] = data.get("action")
        rec["output_chars"] = len(proc.stdout)
    except Exception as e:
        rec["parsed"] = False
        rec["parse_error"] = str(e)[:200]
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3)
    args = ap.parse_args()

    meta = build_meta_prompt(RAW, TARGET, concise=True, intent_routing=False)
    results: dict = {"raw": RAW, "target": TARGET, "rewriter": DEFAULT_REWRITER_MODEL,
                     "min_system": MIN_SYSTEM, "variants": {}}
    for name, extra in VARIANTS.items():
        runs = []
        for i in range(args.n):
            rec = run_once(extra, meta)
            runs.append(rec)
            print(f"{name} #{i + 1}: {rec['seconds']}s rc={rec['rc']} "
                  f"parsed={rec.get('parsed')} action={rec.get('action')}")
        ok = [r["seconds"] for r in runs if r.get("parsed")]
        results["variants"][name] = {
            "runs": runs,
            "n_ok": len(ok),
            "median_s": round(statistics.median(ok), 1) if ok else None,
        }
    out = ROOT / "runs" / "latency_experiment.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v["median_s"] for k, v in results["variants"].items()}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
