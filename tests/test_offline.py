"""Offline unit tests — no `claude` calls, no network.

Run: python3 -m unittest discover tests -v
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from prompt_tailor.detect import (  # noqa: E402
    _model_from_settings,
    _model_from_transcript,
    detect_model,
    normalize_model,
)
from prompt_tailor.engine import (  # noqa: E402
    build_meta_prompt,
    parse_json_output,
    resolve_profile,
)


def _load_pm_hook():
    """pm_hook.py lives in a hyphenated dir (claude-code/hooks) — load by path."""
    path = ROOT / "claude-code" / "hooks" / "pm_hook.py"
    spec = importlib.util.spec_from_file_location("pm_hook", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pm_hook = _load_pm_hook()


class TestParseJsonOutput(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(parse_json_output('{"a": 1}'), {"a": 1})

    def test_fenced_json(self):
        text = 'result:\n```json\n{"intent": "fix"}\n```\ndone'
        self.assertEqual(parse_json_output(text), {"intent": "fix"})

    def test_json_with_surrounding_text(self):
        self.assertEqual(parse_json_output('note {"a": "b"} trailing'), {"a": "b"})

    def test_no_json_raises(self):
        with self.assertRaises(ValueError):
            parse_json_output("no json here")


class TestResolveProfile(unittest.TestCase):
    def test_aliases(self):
        self.assertEqual(resolve_profile("fable"), "fable-5")
        self.assertEqual(resolve_profile("claude-opus-5"), "opus-5")
        self.assertEqual(resolve_profile("HAIKU-4-5"), "haiku-4-5")

    def test_unknown_raises(self):
        with self.assertRaises(ValueError):
            resolve_profile("gpt-4")


class TestBuildMetaPrompt(unittest.TestCase):
    def test_full_contains_raw_and_rules(self):
        meta = build_meta_prompt("로그인 버그 고쳐줘", "fable-5")
        self.assertIn("로그인 버그 고쳐줘", meta)
        self.assertIn("[가정", meta)

    def test_concise_is_much_shorter(self):
        raw = "로그인 버그 고쳐줘"
        full = build_meta_prompt(raw, "fable-5")
        concise = build_meta_prompt(raw, "fable-5", concise=True)
        self.assertIn(raw, concise)
        # Latency gate relies on the condensed meta staying small (LOOP_LOG R7).
        # Bound raised 700->900 for intent rules (R22), 900->1100 for the
        # clarity gate (R35); hook E2E latency re-measured after each change.
        self.assertLess(len(concise), 1100)
        self.assertLess(len(concise), len(full) / 3)

    def test_concise_exists_for_all_profiles(self):
        for stem in ("fable-5", "opus-5", "sonnet-5", "haiku-4-5"):
            meta = build_meta_prompt("x" * 20, stem, concise=True)
            self.assertIn(stem, meta)

    def test_lean_concise_has_no_intent_block_and_stays_small(self):
        raw = "로그인 버그 고쳐줘"
        lean = build_meta_prompt(raw, "fable-5", concise=True, intent_routing=False)
        routed = build_meta_prompt(raw, "fable-5", concise=True)
        self.assertNotIn("fix/debug:", lean)
        self.assertIn("fix/debug:", routed)
        # hook latency budget depends on the lean meta staying small (R7, R22;
        # +clarity gate line R35 — E2E re-measured)
        self.assertLess(len(lean), 700)

    def test_full_meta_includes_intent_rules(self):
        meta = build_meta_prompt("로그인 버그 고쳐줘", "fable-5")
        self.assertIn("fix/debug:", meta)


class TestRewriteRetry(unittest.TestCase):
    """Retry loop must treat timeouts as attempt failures, not crash through."""

    def _patch_call_claude(self, side_effects):
        import prompt_tailor.engine as engine
        calls = {"n": 0}

        def fake(prompt, model, timeout=180):
            effect = side_effects[min(calls["n"], len(side_effects) - 1)]
            calls["n"] += 1
            if isinstance(effect, Exception):
                raise effect
            return effect

        self._orig = engine.call_claude
        engine.call_claude = fake
        self.addCleanup(lambda: setattr(engine, "call_claude", self._orig))
        return calls

    def test_timeout_is_retried(self):
        import subprocess as sp

        from prompt_tailor.engine import rewrite

        ok = '{"intent": "fix", "rewritten_prompt": "다시 쓴 프롬프트", "changes": ["c"]}'
        calls = self._patch_call_claude([sp.TimeoutExpired(cmd="claude", timeout=1), ok])
        result = rewrite("로그인 버그 고쳐줘", "fable-5", retries=1)
        self.assertEqual(calls["n"], 2)
        self.assertEqual(result.rewritten_prompt, "다시 쓴 프롬프트")

    def test_exhausted_retries_raise_runtime_error(self):
        import subprocess as sp

        from prompt_tailor.engine import rewrite

        self._patch_call_claude([sp.TimeoutExpired(cmd="claude", timeout=1)])
        with self.assertRaises(RuntimeError):
            rewrite("로그인 버그 고쳐줘", "fable-5", retries=1)


class TestNormalizeModel(unittest.TestCase):
    def test_strips_suffix(self):
        self.assertEqual(normalize_model("claude-fable-5[1m]"), "fable-5")

    def test_families(self):
        self.assertEqual(normalize_model("mythos"), "fable-5")
        self.assertEqual(normalize_model("claude-opus-5"), "opus-5")
        self.assertEqual(normalize_model("claude-sonnet-5"), "sonnet-5")
        self.assertEqual(normalize_model("claude-haiku-4-5-20251001"), "haiku-4-5")

    def test_unknown_and_empty(self):
        self.assertIsNone(normalize_model("gpt-4"))
        self.assertIsNone(normalize_model(None))
        self.assertIsNone(normalize_model(""))


class TestDetection(unittest.TestCase):
    def test_transcript_last_assistant_wins(self):
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps({"type": "assistant", "message": {"model": "claude-opus-5"}}) + "\n")
            f.write("not json\n")
            f.write(json.dumps({"type": "user", "message": {}}) + "\n")
            f.write(json.dumps({"type": "assistant", "message": {"model": "claude-sonnet-5"}}) + "\n")
            path = f.name
        self.assertEqual(_model_from_transcript(path), "claude-sonnet-5")

    def test_transcript_missing_file(self):
        self.assertIsNone(_model_from_transcript("/nonexistent/path.jsonl"))
        self.assertIsNone(_model_from_transcript(None))

    def test_settings_local_priority(self):
        with tempfile.TemporaryDirectory() as cwd:
            claude_dir = Path(cwd) / ".claude"
            claude_dir.mkdir()
            (claude_dir / "settings.json").write_text('{"model": "claude-opus-5"}')
            (claude_dir / "settings.local.json").write_text('{"model": "claude-haiku-4-5"}')
            self.assertEqual(_model_from_settings(cwd), "claude-haiku-4-5")

    def test_detect_model_transcript_beats_settings(self):
        with tempfile.TemporaryDirectory() as cwd:
            claude_dir = Path(cwd) / ".claude"
            claude_dir.mkdir()
            (claude_dir / "settings.json").write_text('{"model": "claude-opus-5"}')
            transcript = Path(cwd) / "t.jsonl"
            transcript.write_text(
                json.dumps({"type": "assistant", "message": {"model": "claude-sonnet-5"}}) + "\n"
            )
            got = detect_model({"transcript_path": str(transcript), "cwd": cwd})
            self.assertEqual(got, "sonnet-5")


class TestHookSkipRules(unittest.TestCase):
    def test_slash_command(self):
        self.assertEqual(pm_hook.should_skip("/help me"), "slash-command")

    def test_raw_tag(self):
        self.assertEqual(pm_hook.should_skip("#raw 그대로 보내줘 이 프롬프트를 절대 바꾸지 마라"), "raw-tag")
        self.assertEqual(pm_hook.should_skip("앞말 #raw 그대로 보내줘 절대 바꾸지 말고 진행해라"), "raw-tag")

    def test_rawdata_is_not_raw_tag(self):
        # "#rawdata ..." must not match the opt-out tag (measured false positive, R5)
        self.assertNotEqual(
            pm_hook.should_skip("#rawdata 처리하는 코드 만들어줘 데이터 파이프라인으로 구성해서"),
            "raw-tag",
        )

    def test_too_short(self):
        self.assertEqual(pm_hook.should_skip("짧음"), "too-short")
        self.assertEqual(pm_hook.should_skip("hi there"), "too-short")

    def test_seven_token_target_prompt_not_skipped(self):
        # "배포 자동화 하고싶어 도와줘" = ~7 tokens; was skipped under the old
        # <10 threshold — must pass through after the approved amendment (<6).
        self.assertIsNone(pm_hook.should_skip("배포 자동화 하고싶어 도와줘"))

    def test_already_detailed(self):
        self.assertEqual(pm_hook.should_skip("가" * 801), "already-detailed")

    def test_normal_prompt_not_skipped(self):
        self.assertIsNone(pm_hook.should_skip("로그인 버그 고쳐줘 재현 방법은 잘 모르겠는데 자꾸 세션이 끊겨"))


class TestMcpServerProtocol(unittest.TestCase):
    """Protocol-level tests — no LLM calls (tools/call with empty raw only)."""

    def _req(self, method, params=None, req_id=1):
        from prompt_tailor.mcp_server import handle_request
        return handle_request({"jsonrpc": "2.0", "id": req_id, "method": method,
                               "params": params or {}})

    def test_initialize(self):
        resp = self._req("initialize", {"protocolVersion": "2025-06-18"})
        self.assertEqual(resp["result"]["serverInfo"]["name"], "prompt-tailor")
        self.assertIn("tools", resp["result"]["capabilities"])

    def test_tools_list(self):
        resp = self._req("tools/list")
        tools = resp["result"]["tools"]
        self.assertEqual([t["name"] for t in tools], ["refine_prompt", "usage_stats"])
        self.assertIn("raw", tools[0]["inputSchema"]["required"])

    def test_notification_returns_none(self):
        from prompt_tailor.mcp_server import handle_request
        self.assertIsNone(handle_request({"jsonrpc": "2.0",
                                          "method": "notifications/initialized"}))

    def test_unknown_method_errors(self):
        resp = self._req("resources/list")
        self.assertEqual(resp["error"]["code"], -32601)

    def test_unknown_tool_errors(self):
        resp = self._req("tools/call", {"name": "nope", "arguments": {}})
        self.assertEqual(resp["error"]["code"], -32602)

    def test_empty_raw_is_tool_error(self):
        resp = self._req("tools/call", {"name": "refine_prompt", "arguments": {"raw": " "}})
        self.assertTrue(resp["result"]["isError"])


class TestEstimateTokens(unittest.TestCase):
    def test_korean_uses_half_chars(self):
        text = "가나다라마바사아자차"  # 10 Korean chars -> ~5 tokens
        self.assertEqual(pm_hook.estimate_tokens(text), 5)

    def test_english_uses_quarter_chars(self):
        text = "abcdefgh" * 5  # 40 ASCII chars, one word -> 10
        self.assertEqual(pm_hook.estimate_tokens(text), 10)

    def test_word_count_floor(self):
        self.assertGreaterEqual(pm_hook.estimate_tokens("a b c d e f g h i j k l"), 12)


class TestUsageRecords(unittest.TestCase):
    def setUp(self):
        import os
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["PROMPT_TAILOR_DATA_DIR"] = self._tmp.name

    def tearDown(self):
        import os
        del os.environ["PROMPT_TAILOR_DATA_DIR"]
        self._tmp.cleanup()

    def test_record_and_load_roundtrip(self):
        from prompt_tailor import usage
        usage.record_event("hook", "rewrite", target="fable-5", latency_s=14.23, prompt_chars=40)
        usage.record_event("hook", "keep", target="fable-5", latency_s=9.0, prompt_chars=120)
        usage.record_event("pm", "error", detail="TimeoutExpired")
        events = usage.load_events()
        self.assertEqual(len(events), 3)
        self.assertEqual(events[0]["latency_s"], 14.2)
        self.assertNotIn("prompt", events[0])  # privacy: no prompt text field

    def test_no_prompt_text_anywhere(self):
        from prompt_tailor import usage
        secret = "회사 기밀 프롬프트 내용"
        usage.record_event("cli", "rewrite", target="haiku-4-5", prompt_chars=len(secret))
        content = usage.usage_path().read_text(encoding="utf-8")
        self.assertNotIn(secret, content)

    def test_summarize(self):
        from prompt_tailor import usage
        usage.record_event("hook", "rewrite", target="fable-5", latency_s=10.0)
        usage.record_event("hook", "rewrite", target="fable-5", latency_s=20.0)
        usage.record_event("hook", "keep", latency_s=8.0)
        usage.record_event("hook", "skip", detail="too-short")
        usage.record_event("mcp", "error", detail="RuntimeError")
        s = usage.summarize(usage.load_events())
        self.assertEqual(s["total"], 5)
        self.assertEqual(s["by_action"]["rewrite"], 2)
        self.assertEqual(s["keep_rate"], 0.33)  # 1 keep / 3 gated
        self.assertEqual(s["latency"]["rewrite"]["avg_s"], 15.0)
        self.assertEqual(s["skip_reasons"], {"too-short": 1})
        self.assertEqual(s["by_source"], {"hook": 4, "mcp": 1})

    def test_summarize_empty_and_torn_line(self):
        from prompt_tailor import usage
        s = usage.summarize(usage.load_events())
        self.assertEqual(s["total"], 0)
        self.assertIsNone(s["keep_rate"])
        usage.usage_path().parent.mkdir(parents=True, exist_ok=True)
        usage.usage_path().write_text('{"ts": "x", "source": "hook", "act\n', encoding="utf-8")
        self.assertEqual(usage.load_events(), [])  # torn write tolerated

    def test_format_stats_and_share(self):
        from prompt_tailor import usage
        usage.record_event("hook", "rewrite", target="fable-5", latency_s=10.0)
        usage.record_event("pm", "keep", latency_s=8.0)
        s = usage.summarize(usage.load_events())
        text = usage.format_stats(s)
        self.assertIn("rewrite", text)
        self.assertIn("keep 비율", text)
        share = usage.format_stats(s, share=True)
        self.assertIn("| rewrite | 1", share)
        self.assertIn("no prompt text", share)

    def test_last_days_filter(self):
        from prompt_tailor import usage
        usage.record_event("hook", "rewrite", target="fable-5")  # now
        old = {"ts": "2020-01-01T00:00:00", "source": "cli", "action": "keep"}
        with usage.usage_path().open("a", encoding="utf-8") as f:
            f.write(json.dumps(old) + "\n")
        self.assertEqual(len(usage.load_events()), 2)
        recent = usage.load_events(last_days=7)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["action"], "rewrite")

    def test_mcp_usage_stats_tool(self):
        from prompt_tailor import mcp_server, usage
        usage.record_event("mcp", "rewrite", target="fable-5", latency_s=12.0)
        resp = mcp_server.handle_request(
            {"jsonrpc": "2.0", "id": 9, "method": "tools/list"})
        names = [t["name"] for t in resp["result"]["tools"]]
        self.assertEqual(names, ["refine_prompt", "usage_stats"])
        resp = mcp_server.handle_request(
            {"jsonrpc": "2.0", "id": 10, "method": "tools/call",
             "params": {"name": "usage_stats", "arguments": {}}})
        summary = resp["result"]["structuredContent"]
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["by_source"], {"mcp": 1})

    def test_cli_stats_runs(self):
        import contextlib
        import io
        from prompt_tailor import usage
        from prompt_tailor.cli import main as cli_main
        usage.record_event("cli", "rewrite", target="fable-5", latency_s=12.0)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cli_main(["stats"])
        self.assertEqual(rc, 0)
        self.assertIn("rewrite", buf.getvalue())
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cli_main(["stats", "--json"])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(buf.getvalue())["total"], 1)


if __name__ == "__main__":
    unittest.main()
