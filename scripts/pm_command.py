#!/usr/bin/env python3
"""Backend for the /pm slash command (v0.3: in-session rewrite).

Prints the in-session procedure for the session model to follow. No LLM
call and no prompt text: RAW reaches the model through the command
template itself, so the shell never sees user text (no quoting/injection
issues, no auto-mode classifier false positives on words like "prune").

The pre-v0.3 path (a separate context-blind `claude -p` rewrite) is still
available as the `prompt-tailor` CLI / MCP `refine_prompt`.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from prompt_tailor.detect import detect_model  # noqa: E402
from prompt_tailor.session import build_session_brief  # noqa: E402
from prompt_tailor.usage import record_event  # noqa: E402


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):  # Korean brief on Windows legacy codepages
        sys.stdout.reconfigure(encoding="utf-8")
    t0 = time.time()
    try:
        detected = detect_model({"cwd": os.getcwd()})
    except Exception:  # detection is a hint only — never block /pm on it
        detected = None
    print(build_session_brief(detected))
    record_event("pm", "session", target=detected, latency_s=time.time() - t0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
