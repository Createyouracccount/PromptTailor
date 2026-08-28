"""prompt-tailor CLI.

Usage:
    prompt-tailor "대충 쓴 요청" --model fable-5
    echo "요청" | prompt-tailor --model opus-5
    prompt-tailor stats [--json] [--share]
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from . import __version__
from .engine import (
    DEFAULT_REWRITER_MODEL,
    MODEL_ALIASES,
    ClaudeCLINotFoundError,
    rewrite,
)
from .usage import format_stats, load_events, record_event, summarize


def stats_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="prompt-tailor stats",
        description="로컬 사용 기록 요약 (프롬프트 원문 미포함, 어디로도 전송되지 않음)",
    )
    parser.add_argument("--json", action="store_true", help="요약을 JSON으로 출력")
    parser.add_argument(
        "--share", action="store_true",
        help="GitHub 이슈에 붙여넣기 좋은 숫자-전용 마크다운 블록 출력",
    )
    parser.add_argument(
        "--last", type=int, metavar="N", default=None,
        help="최근 N일 기록만 집계 (기본: 전체)",
    )
    args = parser.parse_args(argv)
    summary = summarize(load_events(last_days=args.last))
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(format_stats(summary, share=args.share))
    return 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv[:1] == ["stats"]:
        return stats_main(argv[1:])
    parser = argparse.ArgumentParser(
        prog="prompt-tailor",
        description="대충 쓴 요청을 대상 Claude 모델에 맞는 프롬프트로 재작성합니다.",
    )
    parser.add_argument("raw", nargs="?", help="원본 프롬프트 (생략 시 stdin에서 읽음)")
    parser.add_argument(
        "-m", "--model", default="fable-5",
        help=f"대상 모델 (기본: fable-5; 허용: {sorted(set(MODEL_ALIASES.values()))})",
    )
    parser.add_argument(
        "--rewriter-model", default=DEFAULT_REWRITER_MODEL,
        help=f"재작성에 사용할 모델 (기본: {DEFAULT_REWRITER_MODEL})",
    )
    parser.add_argument(
        "--concise", action="store_true",
        help="축약 메타프롬프트 사용 (빠름 — 훅 자동 모드와 동일 경로, 품질 경미 하락 가능)",
    )
    parser.add_argument("--json", action="store_true", help="JSON으로 출력")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)

    raw = args.raw if args.raw is not None else sys.stdin.read()
    if not raw.strip():
        parser.error("빈 프롬프트입니다.")

    t0 = time.time()
    try:
        result = rewrite(raw, args.model, rewriter_model=args.rewriter_model, concise=args.concise)
    except ClaudeCLINotFoundError as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        record_event("cli", "error", detail=type(e).__name__)
        print(f"재작성 실패: {e}", file=sys.stderr)
        return 1
    record_event(
        "cli", result.action, target=result.target_model,
        latency_s=time.time() - t0, prompt_chars=len(raw),
    )

    if args.json:
        print(json.dumps({
            "action": result.action,
            "intent": result.intent,
            "target_model": result.target_model,
            "rewritten_prompt": result.rewritten_prompt,
            "changes": result.changes,
        }, ensure_ascii=False, indent=2))
    else:
        print(result.rewritten_prompt)
        print("\n--- changes (변경 요약) ---", file=sys.stderr)
        for c in result.changes:
            print(f"• {c}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
