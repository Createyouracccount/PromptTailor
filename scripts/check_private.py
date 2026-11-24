#!/usr/bin/env python3
"""Block commits that contain real /pm prompts from local logs.

    python3 scripts/check_private.py            # staged files (pre-commit)
    python3 scripts/check_private.py --all      # every tracked file
    git config core.hooksPath .githooks         # enable the hook once

Sources and matching rules: prompt_tailor/privacy.py. Prints only the
overlapping snippet, never the full private prompt.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from prompt_tailor.privacy import default_sources, find_leaks, load_private_texts, private_marked_ids  # noqa: E402

TEXT_SUFFIXES = {".py", ".md", ".json", ".jsonl", ".txt", ".toml", ".yml", ".yaml", ".sh", ".cfg", ""}


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True,
                          encoding="utf-8", check=True).stdout


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="check every tracked file, not just staged ones")
    ap.add_argument("--source", action="append", default=[], metavar="LOG",
                    help="extra private log/jsonl to check against (repeatable)")
    args = ap.parse_args()

    if args.all:
        names = _git("ls-files").splitlines()
        read = lambda n: (REPO_ROOT / n).read_text(encoding="utf-8", errors="replace")
    else:
        names = _git("diff", "--cached", "--name-only", "--diff-filter=ACMR").splitlines()
        read = lambda n: _git("show", f":{n}")
    names = [n for n in names if Path(n).suffix in TEXT_SUFFIXES]

    files = {}
    for n in names:
        try:
            files[n] = read(n)
        except (OSError, subprocess.CalledProcessError):
            continue

    problems = []
    for n, content in files.items():
        ids = private_marked_ids(content) if n.endswith(".jsonl") else []
        if ids:
            problems.append(f"  {n}: private 표시 항목 {', '.join(ids)} (prompt-tailor cases --export 결과는 bench/private/에만)")

    sources = default_sources([Path(p) for p in args.source])
    texts = load_private_texts(sources)
    for name, snippet in find_leaks(files, texts):
        problems.append(f"  {name}: 로컬 실사용 기록과 겹침 → …{snippet}…")

    if problems:
        print("PromptTailor 개인정보 검사 실패 — 실제 사용 문장은 커밋하지 마세요 (합성 예시로 바꾸기):", file=sys.stderr)
        print("\n".join(problems), file=sys.stderr)
        print(f"(검사 원본 {len(sources)}개, 문장 {len(texts)}개. 오탐이면 문구를 바꾸거나 git commit --no-verify)", file=sys.stderr)
        return 1
    print(f"개인정보 검사 통과: 파일 {len(files)}개 · 로컬 원본 {len(sources)}개 · 문장 {len(texts)}개")
    return 0


if __name__ == "__main__":
    sys.exit(main())
