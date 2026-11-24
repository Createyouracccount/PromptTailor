"""Phase 4 (v0.3) measurements — GATES.md G4-2 / G4-3 / G4-4.

Simulates what a user actually experiences with /pm, for both versions:

  v0.2.5 arm: context-blind haiku rewrite (the v0.2.5 engine, loaded from
              git) -> old pm.md template with the backend JSON inlined.
  v0.3   arm: new pm.md template with the in-session brief inlined.

Both arms are then run by the same session-model stand-in (sonnet, headless,
tools disabled) with the same conversation and the same bench-mode suffix,
so the only difference is the /pm mechanism.

Subcommands:
  context  G4-2 interpretation vs. expected + blind pairwise, and the
           question-preservation half of G4-3 (bench/context_set.jsonl)
  stall    G4-3 "asked questions only, produced nothing" rate on the 10
           vague tasks from eval/ab_vague_outcome.py
  keep     G4-4 keep rate on the 20 clear items of bench/gate_set.jsonl
           (v0.3 arm only)

Run from a neutral cwd (outside the repo):
  python3 <repo>/bench/run_v03_bench.py context --out <repo>/runs/v03/context_run1.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from prompt_tailor.engine import parse_json_output  # noqa: E402
from prompt_tailor.session import KEEP_MARKER, build_session_brief  # noqa: E402

SESSION_MODEL = "sonnet"   # stand-in for the user's session model (cost; GATES Phase 4)
JUDGE_MODEL = "sonnet"
BASELINE_REF = "64aea85"   # v0.2.5 release commit
TARGET = "opus-5"          # the user's usual session model in real usage logs

OLD_PM_TEMPLATE = """\
## 재작성 결과

{backend}

## 지시

1. 첫 출력으로 변경 요약(changes)을 한 줄로 사용자에게 보여준 뒤 작업을 시작하라. 생략하지 마라.
2. 위 "재작성 결과"의 rewritten_prompt를 사용자의 실제 요청으로 간주하고 그대로 수행하라.
3. 사용자에게 보이는 모든 응답은 원문 "{raw}"와 같은 언어로 작성하라 (한국어 원문이면 한국어로).
4. [가정]으로 표시된 부분은 단정하지 말고 작업 중에 확인하라.
5. 재작성 결과가 에러이면 원문 "{raw}"를 그대로 수행하라. 단, 원문도 비어 있으면 아무 작업도 하지 말고 usage 안내 한 줄만 사용자에게 보여줘라.
6. 재작성기는 대화 맥락 없이 원문 텍스트만 본다. rewritten_prompt가 현재 대화 맥락과 어긋나면(예: "이제", "그럼", "아까 그거" 같은 지시어가 앞선 대화를 가리키는데 재작성이 범위를 다른 곳으로 넓힌 경우) 맥락상의 원문 의도를 우선하고, 그렇게 판단했음을 사용자에게 한 줄로 알려라.
"""

NEW_PM_TEMPLATE = """\
<RAW>
{raw}
</RAW>

## 처리 절차

{brief}"""

SESSION_FRAME = """\
{conversation_block}사용자가 이제 슬래시 명령을 실행했고, 명령은 아래 내용으로 확장되었다:
<command>
{command}
</command>

[벤치 모드] 이 환경에서는 도구를 실행할 수 없다. 이 명령을 받았을 때 네가 보낼 첫 응답의 앞부분만 써라:
사용자에게 처음 보여줄 내용과, 이어서 무엇을 어떻게 할지(첫 행동 계획)를 최대 8줄로.
"""

EXEC_FRAME = """\
사용자가 슬래시 명령을 실행했고, 명령은 아래 내용으로 확장되었다:
<command>
{command}
</command>

[벤치 환경] 이 환경에서는 도구(파일 읽기·쓰기·셸)를 실행할 수 없다. 파일을 만드는 대신 결과물(코드 등)을 응답 안에 직접 써라.
"""
# stall_run1 (2026-11-24) omitted the notice above: with --tools "" both arms
# emitted tool calls as text and the judge counted them as stalls. Kept on
# record in MEASUREMENT_LOG; stall_run2+ use this frame.

CONTEXT_JUDGE = """\
당신은 해석 정확도 심판이다. Claude Code 세션의 직전 대화와 사용자의 후속 요청이 있고,
두 응답 A와 B는 그 요청을 받은 어시스턴트의 첫 응답(앞부분)이다.

<직전_대화>
{context}
</직전_대화>

<사용자_요청>
{raw}
</사용자_요청>

<맥락상_올바른_해석>
{expected}
</맥락상_올바른_해석>

<응답_A>
{a}
</응답_A>

<응답_B>
{b}
</응답_B>

각 응답에 대해 판정하라:
- correct: 응답이 하려는 일이 "맥락상 올바른 해석"과 일치하는가 (대상·범위가 맞는가). 범위를 크게 넓히거나, 다른 대상을 잡거나, 핵심을 빠뜨리면 false.
- question_preserved: 사용자 요청이 질문이면, 응답이 답변/조사로 유지했는가(요청 안 한 수정·구현·실행으로 바꾸지 않았는가). 질문이 아니면 null.
- stalled: 할 수 있는 일을 하지 않고 사용자에게 되묻기만 했는가.
winner: 사용자가 실제로 원한 것에 더 가까운 쪽 "A" | "B" | "tie".

JSON만 출력:
{{"a": {{"correct": true, "question_preserved": null, "stalled": false}}, "b": {{"correct": true, "question_preserved": null, "stalled": false}}, "winner": "A|B|tie", "reason": "한 문장"}}
"""

STALL_JUDGE = """\
사용자가 아래 요청을 했고, 어시스턴트가 아래처럼 응답했다.

<요청>
{task}
</요청>

<응답>
{out}
</응답>

판정: 응답이 사용 가능한 결과물(코드·구체적 산출물)을 하나도 내지 않고 사용자에게 질문·확인 요청만 하고 끝났으면 stalled=true.
가정을 밝히고 결과물을 냈다면, 끝에 질문이 덧붙어 있어도 stalled=false.

JSON만 출력: {{"stalled": true, "reason": "한 문장"}}
"""


def call(prompt: str, model: str, timeout: int = 240, tries: int = 2) -> str:
    err = None
    for _ in range(tries):  # transient CLI failures (seen: rc=1 auth warning)
        try:
            return _call_once(prompt, model, timeout)
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            err = e
    raise RuntimeError(str(err))


def _call_once(prompt: str, model: str, timeout: int) -> str:
    proc = subprocess.run(
        ["claude", "-p", "--model", model, "--tools", "",
         "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}'],
        input=prompt, capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude -p rc={proc.returncode}: {proc.stderr[:300]}")
    return proc.stdout.strip()


def call_json(prompt: str, model: str, tries: int = 2) -> tuple[dict, str]:
    last = None
    for _ in range(tries):
        out = call(prompt, model)
        try:
            return parse_json_output(out), out
        except (ValueError, json.JSONDecodeError) as e:
            last = e
    raise RuntimeError(f"judge JSON failed: {last}")


_BASELINE = None


def baseline_engine() -> types.ModuleType:
    """Load the v0.2.5 engine source from git so the baseline is exactly what shipped."""
    global _BASELINE
    if _BASELINE is None:
        src = subprocess.run(
            ["git", "-C", str(ROOT), "show", f"{BASELINE_REF}:prompt_tailor/engine.py"],
            capture_output=True, text=True, check=True).stdout
        mod = types.ModuleType("engine_v025")
        mod.__file__ = str(ROOT / "prompt_tailor" / "engine.py")  # profiles dir is unchanged
        sys.modules["engine_v025"] = mod  # dataclass decorator looks the module up
        exec(compile(src, "engine_v025.py", "exec"), mod.__dict__)
        _BASELINE = mod
    return _BASELINE


def old_command(raw: str) -> tuple[str, dict]:
    eng = baseline_engine()
    try:
        r = eng.rewrite(raw, TARGET, retries=1, timeout=60, concise=True)
        backend = {"action": r.action, "target_model": r.target_model,
                   "rewritten_prompt": r.rewritten_prompt, "changes": r.changes}
    except Exception as e:
        backend = {"error": f"{type(e).__name__}: {e}"}
    cmd = OLD_PM_TEMPLATE.format(backend=json.dumps(backend, ensure_ascii=False, indent=2), raw=raw)
    return cmd, backend


def new_command(raw: str) -> str:
    return NEW_PM_TEMPLATE.format(raw=raw, brief=build_session_brief(TARGET))


def conv_block(context: str) -> str:
    return f"다음은 Claude Code 세션의 직전 대화다:\n<conversation>\n{context}\n</conversation>\n\n" if context else ""


# ---------------------------------------------------------------- context

def run_context_item(args: tuple[int, dict]) -> dict:
    i, item = args
    rec = dict(item)
    try:
        old_cmd, backend = old_command(item["raw"])
        rec["v025_backend"] = backend
        outs = {}
        for arm, cmd in (("v025", old_cmd), ("v03", new_command(item["raw"]))):
            t0 = time.time()
            outs[arm] = call(SESSION_FRAME.format(conversation_block=conv_block(item["context"]), command=cmd),
                             SESSION_MODEL)
            rec[f"{arm}_wall_s"] = round(time.time() - t0, 1)
        rec["v025_out"], rec["v03_out"] = outs["v025"], outs["v03"]
        a_arm, b_arm = ("v03", "v025") if i % 2 == 0 else ("v025", "v03")
        rec["assignment"] = {"A": a_arm, "B": b_arm}
        verdict, raw_judge = call_json(CONTEXT_JUDGE.format(
            context=item["context"], raw=item["raw"], expected=item["expected"],
            a=outs[a_arm], b=outs[b_arm]), JUDGE_MODEL)
        rec["judge_raw"] = raw_judge
        rec["judge"] = {rec["assignment"]["A"]: verdict.get("a", {}),
                        rec["assignment"]["B"]: verdict.get("b", {})}
        w = verdict.get("winner", "tie")
        rec["winner"] = "tie" if w not in ("A", "B") else rec["assignment"][w]
        rec["reason"] = verdict.get("reason", "")
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {e}"
    return rec


def summarize_context(results: list[dict]) -> dict:
    ok = [r for r in results if "judge" in r]
    s: dict = {"n": len(results), "valid": len(ok), "errors": [r["id"] for r in results if "error" in r]}
    for arm in ("v025", "v03"):
        s[f"{arm}_correct"] = sum(1 for r in ok if r["judge"][arm].get("correct") is True)
        qs = [r for r in ok if r["kind"] == "question"]
        s[f"{arm}_question_preserved"] = f"{sum(1 for r in qs if r['judge'][arm].get('question_preserved') is True)}/{len(qs)}"
        # violation = judge explicitly says the question became a task (null = judge did not classify)
        s[f"{arm}_question_violations"] = [r["id"] for r in qs if r["judge"][arm].get("question_preserved") is False]
        s[f"{arm}_stalled"] = sum(1 for r in ok if r["judge"][arm].get("stalled") is True)
        s[f"{arm}_wrong_ids"] = [r["id"] for r in ok if r["judge"][arm].get("correct") is not True]
    s["wins"] = {k: sum(1 for r in ok if r["winner"] == k) for k in ("v03", "v025", "tie")}
    return s


# ---------------------------------------------------------------- stall

def run_stall_item(args: tuple[int, str]) -> dict:
    i, task = args
    rec: dict = {"index": i, "task": task}
    try:
        old_cmd, backend = old_command(task)
        rec["v025_backend"] = backend
        for arm, cmd in (("v025", old_cmd), ("v03", new_command(task))):
            out = call(EXEC_FRAME.format(command=cmd), SESSION_MODEL, timeout=300)
            rec[f"{arm}_out"] = out
            verdict, _ = call_json(STALL_JUDGE.format(task=task, out=out), JUDGE_MODEL)
            rec[f"{arm}_stalled"] = bool(verdict.get("stalled"))
            rec[f"{arm}_reason"] = verdict.get("reason", "")
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {e}"
    return rec


def summarize_stall(results: list[dict]) -> dict:
    ok = [r for r in results if "v03_stalled" in r]
    return {"n": len(results), "valid": len(ok),
            "v025_stalled": sum(r["v025_stalled"] for r in ok),
            "v03_stalled": sum(r["v03_stalled"] for r in ok),
            "errors": [r["index"] for r in results if "error" in r]}


# ---------------------------------------------------------------- keep

CLARIFIED_RE = re.compile(r"\*\*(?:보강|Clarified)\*\*\s*[:：]\s*(.+)")


def run_keep_item(item: dict) -> dict:
    rec = dict(item)
    try:
        out = call(SESSION_FRAME.format(conversation_block="", command=new_command(item["raw"])), SESSION_MODEL)
        rec["v03_out"] = out
        m = CLARIFIED_RE.search(out)
        line = m.group(1).strip() if m else ""
        rec["clarified_line"] = line
        low = line.lower()
        rec["kept"] = bool(line) and (line.strip('"\' ').startswith(KEEP_MARKER) or low.strip('"\' ').startswith("as-is"))
        rec["format_ok"] = bool(m)
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {e}"
    return rec


def summarize_keep(results: list[dict]) -> dict:
    ok = [r for r in results if "kept" in r]
    return {"n": len(results), "valid": len(ok), "kept": sum(r["kept"] for r in ok),
            "format_ok": sum(r["format_ok"] for r in ok),
            "not_kept_ids": [r["id"] for r in ok if not r["kept"]],
            "errors": [r["id"] for r in results if "error" in r]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["context", "stall", "keep"])
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", required=True)
    ap.add_argument("--items", help="context items JSONL (default bench/context_set.jsonl; exported real cases go in bench/private/)")
    args = ap.parse_args()

    if args.mode == "context":
        items_path = Path(args.items) if args.items else ROOT / "bench" / "context_set.jsonl"
        items = [json.loads(l) for l in items_path.open(encoding="utf-8") if l.strip()]
        fn, work, summ = run_context_item, list(enumerate(items)), summarize_context
    elif args.mode == "stall":
        sys.path.insert(0, str(ROOT / "eval"))
        from ab_vague_outcome import TASKS  # noqa: E402
        fn, work, summ = run_stall_item, list(enumerate(TASKS)), summarize_stall
    else:
        items = [json.loads(l) for l in (ROOT / "bench" / "gate_set.jsonl").open(encoding="utf-8")]
        fn, work, summ = run_keep_item, [it for it in items if it["label"] == "keep"], summarize_keep

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(fn, work))
    summary = summ(results)
    summary["wall_s"] = round(time.time() - t0, 1)
    summary["session_model"], summary["judge_model"] = SESSION_MODEL, JUDGE_MODEL
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
