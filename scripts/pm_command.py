#!/usr/bin/env python3
"""Backend for the /pm slash command.

Detects the current session's model (transcript-based detection is not
available here, so settings-based detection is used) and prints the
rewrite as JSON for the command template to consume.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from prompt_tailor.detect import detect_model  # noqa: E402
from prompt_tailor.engine import rewrite  # noqa: E402
from prompt_tailor.usage import record_event  # noqa: E402


def main() -> int:
    raw = " ".join(sys.argv[1:]).strip()
    if not raw:
        # VSCode autocomplete submits the bare command on Enter — seen in real
        # use 2026-08-20. Return a usage hint instead of a bare error.
        print(json.dumps({
            "error": "빈 프롬프트",
            "usage": "/pm <요청> — 명령 뒤에 Space를 누르고 실제 요청을 입력하세요. 예: /pm 로그인 버그 고쳐줘",
        }, ensure_ascii=False))
        return 0
    log_path = REPO_ROOT / "runs" / "pm_command.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    os.environ["PROMPT_TAILOR_ACTIVE"] = "1"  # recursion guard for the hook
    t0 = time.time()
    try:
        target = detect_model({"cwd": os.getcwd()}) or "fable-5"
        # Interactive path — the user waits inline. Condensed meta measured
        # 14.5-21.9s vs full meta avg 41.4s (LOOP_LOG R7); cap each attempt at 60s.
        r = rewrite(raw, target, retries=1, timeout=60, concise=True)
        print(json.dumps({
            "action": r.action,
            "target_model": r.target_model,
            "rewritten_prompt": r.rewritten_prompt,
            "changes": r.changes,
        }, ensure_ascii=False, indent=2))
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} ok target={target} raw={raw[:60]!r}\n")
        record_event("pm", r.action, target=target,
                     latency_s=time.time() - t0, prompt_chars=len(raw))
    except Exception as e:
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False))
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} ERROR {type(e).__name__}: {e}\n")
        record_event("pm", "error", latency_s=time.time() - t0, detail=type(e).__name__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
