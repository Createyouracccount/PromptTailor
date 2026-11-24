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

**Inside Claude Code** — `/pm rough request` (v0.3+): the session model itself reads your request *in the context of the conversation* — resolving "this / that / go ahead / the second one" to what you were actually talking about — then decides: answer it (questions stay questions), run it as-is (already clear), or fill the gaps (scope, done-criteria, `[assumption]`-tagged defaults) and run it. It prints two lines first — **Interpretation** and **Clarified** — then starts working. Unclear points are resolved by investigating or by a stated default rather than by asking you back; it asks first only for hard-to-undo actions or when there is no basis for a default. No separate rewrite call, so there is no wait (backend < 0.1s). If `/pm` reports "Unknown command" (some clients, e.g. the VSCode extension, register plugin commands under their namespace), use `/prompt-tailor:pm` instead.

**`/prompt-tailor:feedback [what was wrong]`** — when a `/pm` result missed, run this right after. The session model writes one case (the raw request, the context needed to read it, what `/pm` understood, what went wrong, what it should have done) to `~/.claude/prompt-tailor/cases.jsonl` on your machine. `prompt-tailor cases` lists them; `prompt-tailor cases --export bench/private/cases.jsonl` turns them into context-benchmark items, and `python3 bench/run_v03_bench.py context --items bench/private/cases.jsonl --out runs/private/run.json` runs them, so real misses become regression tests for the next rule change. Exported items contain your real requests: keep them in the gitignored `bench/private/` and `runs/private/` and never commit them. The public benchmark ([bench/context_set.jsonl](bench/context_set.jsonl)) uses synthetic examples only. See [Privacy rules](#privacy-rules).

> Before v0.3, `/pm` sent your text to a separate `claude -p` (haiku) process that could not see the conversation. Most real `/pm` uses turned out to be follow-ups that only make sense with the conversation, so v0.3 moved the rewrite into the session. The context-blind path remains for the CLI, MCP, and hook, where no conversation is available.

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

- **v0.3 in-session `/pm` vs v0.2.5 (2026-11-24, session model stand-in: sonnet; judge: sonnet)** — on a new 12-item *context* benchmark ([bench/context_set.jsonl](bench/context_set.jsonl): conversation excerpt + follow-up such as "ok go ahead" / "re-run that" / "is this handled?"; synthetic examples, no real requests), both versions picked the right target 12/12 in both runs (the v0.2.5 template's "prefer conversation context" rule already recovers the context-blind rewrite). Where v0.3 differs is response quality: blind pairwise **10–1–1 and 11–0–1** for v0.3 (judges cited v0.2.5's leaked "rewrite/changes" chatter and scope creep). On the 10 vague tasks, responses that ended by only asking questions: **v0.3 0/10, v0.2.5 1/10**; questions were never turned into tasks (0/10 violations); already-clear requests kept as-is **17/20**. A first stall run was invalidated (the harness disabled tools without telling the executor) and is kept on record. Details: [runs/MEASUREMENT_LOG.md](runs/MEASUREMENT_LOG.md)

**What this means**: the measured benefit is on vague, underspecified requests — the golden set's territory. Already-clear requests should be left alone, so since v0.2.0 the rewriter runs a **clarity gate** first: if your request is already specific it returns it untouched (`action: keep`; the hook then injects nothing). Gate accuracy on a balanced 40-prompt benchmark, measured over **3 repeated runs from a neutral cwd**: **90–95%** — vague recall 59/60 (misses almost never in the harmful direction), clear recall 16–18/20. An earlier single-run figure of 98% did not reproduce and has been retired. Dataset, runner, per-run results, and the stubborn borderline cases are documented in [BENCHMARK.md](BENCHMARK.md).

## Usage records, privacy, and how to help improve it

Every rewrite path logs one privacy-safe event (action, source, target model, latency, prompt *length* — **never prompt text**) to `~/.claude/prompt-tailor/usage.jsonl` on your machine. **Nothing is ever transmitted** — there is no telemetry; we cannot see your usage.

```bash
prompt-tailor stats           # summarize your own records: keep/rewrite rate, latency, errors
prompt-tailor stats --share   # numbers-only markdown block, safe to paste into an issue
```

Because there is no telemetry, improvement runs on what you choose to share: if a rewrite hurt (wrong scope, wrong gate decision, invented specifics), file a [bad-rewrite report](../../issues/new?template=bad-rewrite.yml) — reports feed the public [benchmark](BENCHMARK.md) and golden set that gate every change.

### Privacy rules

Real requests stay on the machine that typed them. That covers `/pm` logs, `cases.jsonl` and anything exported from it. Public benchmarks, tests and docs use synthetic examples written from scratch. Don't paraphrase a real request: a reworded sentence still carries what the person was working on.

- **Local only**: `~/.claude/prompt-tailor/` (usage, cases), the installed plugin's `runs/*.log`, and this checkout's `runs/*.log`, `bench/private/` and `runs/private/` (all gitignored).
- **Pre-commit check**: `git config core.hooksPath .githooks` enables [scripts/check_private.py](scripts/check_private.py). It compares staged files against your local logs and feedback cases, and blocks the commit if a long run of a real request appears. It prints only the overlapping fragment. Run `python3 scripts/check_private.py --all` to check every tracked file.
- **CI check**: CI can't see your logs. Instead it fails if a tracked `bench/*.jsonl` item is marked `"private": true`, which every `cases --export` item is.

## What we do NOT guarantee

- **Higher task success is not proven — including on vague requests.** Prompt-quality wins are judge-based; the outcome data so far is the 3-task pilot (raw won 3–0) and the 10-task vague A/B (4–4 draw). Both ran headless single-turn, which structurally penalizes rewrites that ask good clarifying questions — interactive use may differ, but we have not measured that. The v0.3 measurements are also headless, single-judge, small-n, and use sonnet as a stand-in for your session model (real use is usually Opus/Fable); the context benchmark is synthetic: it mimics common follow-up patterns but contains no real requests.
- The rewriter occasionally adds specifics without an `[assumption]` tag (fidelity 4.8, not 5.0), and can misclassify intent.
- All experiments are small-n, single-LLM-judge, and were run in this repo's environment.

## Development

```bash
python3 -m unittest discover tests   # 66 offline tests, no LLM calls
python3 eval/run_eval.py             # golden-set evaluation (spawns claude)
```

Project docs (Korean): [PLAN.md](PLAN.md) · [ARCHITECTURE.md](ARCHITECTURE.md) · [RESEARCH.md](RESEARCH.md) · gate criteria in [GATES.md](GATES.md).

## License

[MIT](LICENSE)
