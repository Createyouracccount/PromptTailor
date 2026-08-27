"""R39 핵심 실험: 모호한 요청에서 재작성이 실제 작업 결과를 개선하는가? (n=10)

R34 파일럿(명확 과제 3건, 원문 3:0 승)의 반대편 — 도구가 이득을 주장하는
영역(모호·불충분 요청)을 결과 데이터로 처음 검증한다.

설계 (R23 방법론 의무 + R34 프로토콜 승계):
  - 과제 10건: 모호/불충분하지만 자기완결적(레포·네트워크 불필요, headless 실행 가능).
    언어·형식·엣지케이스 미지정 — 골든셋과 같은 모호성 계층.
  - 재작성: 실사용 /pm 경로와 동일(concise + intent routing), target=haiku.
    게이트가 keep을 반환하면 비교 불성립으로 기록(재작성 없음 = 두 팔 동일).
  - 생성 순서는 항목 짝수/홀수로 교대, 제시 위치(A/B)는 반대 짝수성으로 교대
    — 순서·위치 비교락 방지. 배정 기록으로 사후 역맹검.
  - 심판(sonnet)은 원 요청과 두 결과물만 본다(재작성문 비노출). 원시 출력 보존.
  - 중립 cwd에서 실행할 것 (레포 컨텍스트 누출 방지).

Usage: (레포 밖 cwd에서) python3 <repo>/eval/ab_vague_outcome.py [--workers 3]
Writes eval/ab_vague_outcome_results.json.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from prompt_tailor.engine import call_claude, parse_json_output, rewrite  # noqa: E402

# 모호하지만 자기완결적: 대상 언어·입출력 형식·범위·엣지케이스 전부 미지정
TASKS = [
    "파일 백업하는 거 하나 만들어줘",
    "비밀번호 만들어주는 프로그램 짜줘",
    "텍스트에서 이메일 주소들 뽑아줘야 되는데 만들어줘",
    "할일 관리하는 간단한 거 만들어줘",
    "단위 변환기 만들어줘",
    "로그 파일 분석하는 거 필요해",
    "숫자 맞추기 게임 만들어줘",
    "돈 계산 관련 유틸 좀",
    "마크다운 변환하는 거 만들어줘",
    "데이터 정리 스크립트 하나 부탁해",
]
EXECUTOR = "claude-haiku-4-5"
JUDGE = "claude-sonnet-5"

RESULT_JUDGE = """당신은 결과물 품질 심판이다. 사용자가 아래 요청을 했고, 두 결과물 A와 B를 받았다.
어느 결과물이 사용자의 실제 필요를 더 잘 충족하는지 평가하라.

<사용자_요청>
{task}
</사용자_요청>

<결과물_A>
{a}
</결과물_A>

<결과물_B>
{b}
</결과물_B>

기준: 정확성(코드가 실제로 동작하고 엣지케이스를 다루는가), 완결성(바로 쓸 수 있는가),
적합성(요청 범위를 벗어난 과잉이나 미달이 없는가). 요청이 모호한 경우, 합리적 해석과
그 해석의 명시(가정 표시)도 완결성의 일부다.
verdict: "A" | "B" | "tie"

JSON만 출력:
{{"a_score": n, "b_score": n, "verdict": "A|B|tie", "reason": "한 문장"}}
"""


def process(args: tuple[int, str]) -> dict:
    i, task = args
    rec: dict = {"index": i, "task": task}
    try:
        r = rewrite(task, "haiku-4-5", concise=True, retries=1, timeout=90)
        rec["action"] = r.action
        rec["rewritten_prompt"] = r.rewritten_prompt
        if r.action == "keep":
            # 게이트가 이미 명확 판정 — 두 팔이 동일하므로 비교 불성립
            rec["winner"] = "gate-keep"
            return rec

        gen_order = ["raw", "rewritten"] if i % 2 == 0 else ["rewritten", "raw"]
        for arm in gen_order:
            prompt = task if arm == "raw" else r.rewritten_prompt
            t0 = time.time()
            out = call_claude(prompt, EXECUTOR, timeout=240)
            rec[arm] = {"output": out, "wall_s": round(time.time() - t0, 1)}

        a_arm, b_arm = ("rewritten", "raw") if i % 2 == 0 else ("raw", "rewritten")
        rec["assignment"] = {"A": a_arm, "B": b_arm}
        judge_out = call_claude(
            RESULT_JUDGE.format(task=task, a=rec[a_arm]["output"], b=rec[b_arm]["output"]),
            JUDGE, timeout=180)
        rec["judge_raw"] = judge_out
        rec["judge"] = parse_json_output(judge_out)
        v = rec["judge"]["verdict"]
        rec["winner"] = "tie" if v == "tie" else rec["assignment"].get(v, "?")
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {e}"
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(process, enumerate(TASKS)))

    for rec in results:
        print(f"[{rec['index']}] winner={rec.get('winner', 'ERROR')} "
              f"| {rec.get('judge', {}).get('reason', rec.get('error', ''))[:110]}")

    out_path = ROOT / "eval" / "ab_vague_outcome_results.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    wins: dict = {"raw": 0, "rewritten": 0, "tie": 0, "gate-keep": 0, "error": 0}
    for rec in results:
        wins[rec.get("winner", "error")] = wins.get(rec.get("winner", "error"), 0) + 1
    print(f"\nvague task-outcome wins: {wins}")
    print(f"written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
