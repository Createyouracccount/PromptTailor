# PromptTailor

> Model-aware prompt rewriting for Claude Code. Write a rough request — get it rewritten the way your current Claude model works best.

[한국어 README](README.ko.md)

![PromptTailor demo: a vague request gets rewritten; an already-clear one is returned untouched](docs/demo.gif)

*Real calls — only the ~20s waits are cut. Re-render with `vhs docs/demo.tape`.*

## Why

Claude Fable 5, Opus 5, Sonnet 5, and Haiku respond best to *different* prompt styles — Fable wants goals and constraints in prose (no step lists), Opus over-verifies if you tell it to double-check, Haiku wants small numbered steps. PromptTailor keeps these differences as data ([model profiles](prompt_tailor/profiles/)), detects which model you're running, and rewrites your rough request to match — also routing by task intent (fix / build / research / refactor / docs).

Your input language is preserved: English in → English out, Korean in → Korean out.

## Example

```
$ prompt-tailor "fix the login bug asap, users keep getting logged out" --model fable-5
```

> Users are repeatedly logging out unexpectedly. Before fixing, investigate: exact
> reproduction steps (when and under what conditions does this happen?), when this
> started, relevant error logs or console messages, and the login/session management
> code structure.
>
> Once you've identified the reproduction path and root cause, apply the minimum fix
> to prevent unintended logouts. Scope: session and login logic only — do not modify
> other features.
>
> Validation: confirm the issue no longer reproduces through direct testing, or verify
> that related tests pass.

Notice what happened: vague urgency ("asap") became an investigation directive, a scope boundary, and a validation criterion — and nothing was invented. Unknowns become investigation steps; any added specifics are tagged as assumptions.

## Install

**As a Claude Code plugin (recommended):**

```
/plugin marketplace add Createyouracccount/PromptTailor
/plugin install prompt-tailor@prompt-tailor
```

This gives you the `/pm` command with no path setup.

**As a CLI / MCP server:**

```bash
pip install prompt-tailor    # installs `prompt-tailor` and `prompt-tailor-mcp`
```

Requirements: Python 3.10+, the `claude` CLI installed and logged in (no separate API key). Verified in real use on macOS/Linux; on Windows the offline test suite passes in CI (py3.10/3.12), but the end-to-end path with the `claude` CLI is untested.

## Usage

```bash
prompt-tailor "rough request" --model fable-5    # rewrite for a target model
prompt-tailor "rough request" --json             # JSON output
prompt-tailor "rough request" --concise          # faster, condensed meta-prompt
```

**Inside Claude Code** — `/pm rough request`: rewrites for your session's detected model, shows a one-line change summary, then executes the rewritten request. If `/pm` reports "Unknown command" (some clients, e.g. the VSCode extension, register plugin commands under their namespace), use `/prompt-tailor:pm` instead. In auto mode, add the permission rule printed by `claude-code/install.sh` so prompts containing risky-looking words (e.g. "docker prune") aren't false-positive blocked — the backend only rewrites text.

**`/prompt-tailor:loop <goal>` (experimental)** — scaffold an improvement loop instead of rewriting one prompt: extracts your working principles from the conversation (each with its source — nothing invented), drafts a ledger (`LOOP_LOG.md`) and measurable pass/fail gates (`GATES.md`, frozen only with your approval), then runs discover → minimal change → measure → commit rounds. Small one-off tasks are turned away toward `/pm`. No LLM backend call — the session model does the extraction. Not yet separately evaluated.

**Hook auto mode (opt-in)** — rewrite every prompt automatically via a `UserPromptSubmit` hook. Run `bash claude-code/install.sh` for the settings snippet. Escape hatch: include `#raw` in a prompt to pass it through untouched. Prompts under 6 tokens or over 800 chars are skipped; if a rewrite doesn't finish within 28s it fails open (your original prompt goes through).

**Optional direct-API path (opt-in)** — by default every rewrite runs through `claude -p` (login only, no key, uses your subscription quota). If you have an `ANTHROPIC_API_KEY`, you can bypass the CLI startup overhead: `pip install 'prompt-tailor[api]'`, then set `PROMPT_TAILOR_USE_API=1`. Off unless both are set, so nobody is surprise-billed. We have not yet measured its latency, so no speed claim here; CLI-side flag experiments showed no improvement (median ~15s stands — [runs/MEASUREMENT_LOG.md](runs/MEASUREMENT_LOG.md)).

**Cursor / any MCP client** — a built-in stdio MCP server exposes `refine_prompt(raw, target_model, concise)` and `usage_stats` (your local record summary, no LLM call):

```jsonc
// ~/.cursor/mcp.json
{ "mcpServers": { "prompt-tailor": { "command": "prompt-tailor-mcp" } } }
```

```toml
# Codex CLI — ~/.codex/config.toml
[mcp_servers.prompt-tailor]
command = "prompt-tailor-mcp"
```

```bash
claude mcp add prompt-tailor -- prompt-tailor-mcp   # register in Claude Code
```

> **GUI apps may not see your shell PATH.** If the client reports the command not found, use the absolute path from `which prompt-tailor-mcp` as `command`, or use `python3` with `args: ["-m", "prompt_tailor.mcp_server"]`.

The rewrite itself always runs through the `claude` CLI, so the machine needs it installed and logged in regardless of which client calls the tool. Rewrites target Claude models; other-model profiles are not provided (or validated).

## Same input, different models (real outputs)

Input: `로그인 버그 고쳐줘` ("fix the login bug" — Korean in, Korean out):

| target `fable-5` | target `haiku-4-5` |
|---|---|
| Prose: symptoms to identify first, then "find the cause and apply the simplest fix; verify by test or manual check". No step lists. | **Step 1** locate the bug (error message? where?) → **Step 2** fix ([assumption] tagged) → **Step 3** test with valid/invalid credentials → deliverable: fixed code + one-line commit message. |

Full texts in [eval/results.json](eval/results.json).

## Measured cost (n=2, 2026-08-15)

| What you pay | Measured |
|---|---|
| Per rewrite call (haiku) | **≈$0.03 API-equivalent** · ~1.8k output tokens · 18–33s wall. ~29.5k input tokens, but ~99% is `claude -p`'s own system prompt (cached: ~8k cache-write + ~21.6k cache-read); the meta-prompt itself adds only hundreds |
| Hook context injection | **+527 input tokens** in your main conversation (measured as token delta), and it stays in history for the rest of the session |
| Subscription users | No per-call bill — it consumes usage quota instead |

Raw data: [runs/cost_measurement.json](runs/cost_measurement.json), method: [eval/measure_cost.py](eval/measure_cost.py).

## Evidence — including the negative result

Every claim is backed by ledgered experiments (blind pairwise LLM judging; [LOOP_LOG.md](LOOP_LOG.md)):

- **Prompt quality** (golden set of 20 *vague* requests): 20/20 judged better than the original (clarity 5.0, fidelity 4.8, actionability 5.0) — [EVAL.md](EVAL.md)
- Model profiles produce structurally different rewrites: 5/5; intent routing beat profile-only meta 4–1–1
- **Task outcome pilot (n=3): the raw prompt won 3–0.** On *already-clear, self-contained* codegen tasks run headless, rewriting hurt: it inflated scope, its investigation directives stalled a run, and its verification demands made the executor fabricate test results — [eval/ab_task_outcome_results.json](eval/ab_task_outcome_results.json)
- **Vague-task outcome A/B (n=10, 8 valid): raw 4 — rewritten 4.** Even on vague requests — the territory where this tool claims benefit — single-turn headless execution showed no outcome-level advantage. Rewrites won when they turned vagueness into a reasonable default implementation; they lost when their investigation directives made the executor ask questions instead of producing anything — [eval/ab_vague_outcome_results.json](eval/ab_vague_outcome_results.json)

**What this means**: the measured benefit is on vague, underspecified requests — the golden set's territory. Already-clear requests should be left alone, so since v0.2.0 the rewriter runs a **clarity gate** first: if your request is already specific it returns it untouched (`action: keep`; the hook then injects nothing). Gate accuracy on a balanced 40-prompt benchmark, measured over **3 repeated runs from a neutral cwd**: **90–95%** — vague recall 59/60 (misses almost never in the harmful direction), clear recall 16–18/20. An earlier single-run figure of 98% did not reproduce and has been retired. Dataset, runner, per-run results, and the stubborn borderline cases are documented in [BENCHMARK.md](BENCHMARK.md).

## Usage records, privacy, and how to help improve it

Every rewrite path logs one privacy-safe event (action, source, target model, latency, prompt *length* — **never prompt text**) to `~/.claude/prompt-tailor/usage.jsonl` on your machine. **Nothing is ever transmitted** — there is no telemetry; we cannot see your usage.

```bash
prompt-tailor stats           # summarize your own records: keep/rewrite rate, latency, errors
prompt-tailor stats --share   # numbers-only markdown block, safe to paste into an issue
```

Because there is no telemetry, improvement runs on what you choose to share: if a rewrite hurt (wrong scope, wrong gate decision, invented specifics), file a [bad-rewrite report](../../issues/new?template=bad-rewrite.yml) — reports feed the public [benchmark](BENCHMARK.md) and golden set that gate every change.

## What we do NOT guarantee

- **Higher task success is not proven — including on vague requests.** Prompt-quality wins are judge-based; the outcome data so far is the 3-task pilot (raw won 3–0) and the 10-task vague A/B (4–4 draw). Both ran headless single-turn, which structurally penalizes rewrites that ask good clarifying questions — interactive use may differ, but we have not measured that.
- The rewriter occasionally adds specifics without an `[assumption]` tag (fidelity 4.8, not 5.0), and can misclassify intent.
- All experiments are small-n, single-LLM-judge, and were run in this repo's environment.

## Development

```bash
python3 -m unittest discover tests   # 48 offline tests, no LLM calls
python3 eval/run_eval.py             # golden-set evaluation (spawns claude)
```

Project docs (Korean): [PLAN.md](PLAN.md) · [ARCHITECTURE.md](ARCHITECTURE.md) · [RESEARCH.md](RESEARCH.md) · gate criteria in [GATES.md](GATES.md).

## License

[MIT](LICENSE)
