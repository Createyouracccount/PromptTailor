#!/usr/bin/env python3
"""Backend for /prompt-tailor:feedback.

  record_case.py --where   print where cases go and how to record one
  record_case.py < case.json   append one case (JSON object on stdin)

The case text arrives on stdin (heredoc), never as a shell argument.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from prompt_tailor import __version__  # noqa: E402
from prompt_tailor.cases import CATEGORIES, cases_path, load_cases, record_case  # noqa: E402


def main(argv: list[str]) -> int:
    script = Path(__file__).resolve()
    if argv[:1] == ["--where"]:
        print(f"기록 명령: python3 {script} <<'CASE_EOF'\n{{...JSON...}}\nCASE_EOF")
        print(f"저장 위치: {cases_path()} (로컬 전용, 현재 {len(load_cases())}건)")
        print(f"category 허용값: {' | '.join(CATEGORIES)}")
        return 0
    try:
        data = json.loads(sys.stdin.read())
        case, total = record_case(data, version=__version__)
    except (ValueError, json.JSONDecodeError) as e:
        print(f"기록 실패: {e}", file=sys.stderr)
        return 1
    print(f"기록됨: {case['category']} — {cases_path()} (누적 {total}건)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
