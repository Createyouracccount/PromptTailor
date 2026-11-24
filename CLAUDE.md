# PromptTailor: working rules

## Privacy (hard rule)
- Never copy, quote or paraphrase the user's real requests into tracked files. That includes bench items, tests, docs, ledger entries, commit messages and PR text.
- Real requests live in:
  - `~/.claude/prompt-tailor/` (usage.jsonl, cases.jsonl)
  - `~/.claude/plugins/cache/prompt-tailor/*/*/runs/*.log`
  - this repo's `runs/*.log`
  - Claude Code transcripts and history
- If real usage motivates a change, describe the pattern in abstract terms ("short affirmative follow-up") and write a fresh synthetic example.
- Exported feedback cases (`prompt-tailor cases --export`) go only in `bench/private/`, and their run outputs only in `runs/private/`. Both are gitignored.
- Before committing, run `python3 scripts/check_private.py` (or enable the hook: `git config core.hooksPath .githooks`). If it flags something, rewrite the example. Do not bypass the check.
- Ask the user before using anything from their logs, even locally, beyond counting or aggregating it.

## Measurement
- Append-only logs: `runs/MEASUREMENT_LOG.md` (never edit numbers; strike through invalid runs) and `LOOP_LOG.md` (newest first). README states confirmed claims only.
- `GATES.md` changes only with the user's approval.
- Run benchmarks from a neutral cwd with `PROMPT_TAILOR_DATA_DIR` set to a temp dir, so test events never land in the user's real usage log.
