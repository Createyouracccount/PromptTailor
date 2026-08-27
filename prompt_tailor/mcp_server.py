"""MCP server exposing prompt-tailor as a `refine_prompt` tool.

Stdio transport, newline-delimited JSON-RPC 2.0 — no dependencies beyond the
standard library, so any MCP client (Cursor, Claude Code, Claude Desktop)
can spawn it with:

    python3 -m prompt_tailor.mcp_server

Registration examples are in the README.
"""

from __future__ import annotations

import json
import sys
import time

from . import __version__
from .engine import ClaudeCLINotFoundError, rewrite
from .usage import load_events, record_event, summarize

PROTOCOL_VERSION = "2025-06-18"

STATS_TOOL_DEF = {
    "name": "usage_stats",
    "description": (
        "이 기기의 prompt-tailor 로컬 사용 기록 요약을 반환한다 "
        "(keep/rewrite 비율, 지연, 경로별 — 프롬프트 원문은 기록에 없음). "
        "LLM 호출 없이 즉시 응답."
    ),
    "inputSchema": {"type": "object", "properties": {}},
}

TOOL_DEF = {
    "name": "refine_prompt",
    "description": (
        "대충 쓴 요청(raw)을 대상 Claude 모델에 맞는 프롬프트로 재작성한다. "
        "결과의 rewritten_prompt를 실제 요청으로 사용하라. "
        "[가정: ...]으로 표시된 부분은 단정하지 말고 작업 중 확인할 것."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "raw": {"type": "string", "description": "재작성할 원본 요청"},
            "target_model": {
                "type": "string",
                "description": "대상 모델 (fable-5 | opus-5 | sonnet-5 | haiku-4-5, 기본 fable-5)",
                "default": "fable-5",
            },
            "concise": {
                "type": "boolean",
                "description": "축약 메타프롬프트 사용 (빠름, 기본 true)",
                "default": True,
            },
        },
        "required": ["raw"],
    },
}


def _handle_tool_call(arguments: dict) -> dict:
    raw = arguments.get("raw", "")
    if not raw.strip():
        return {"content": [{"type": "text", "text": "error: empty raw prompt"}], "isError": True}
    t0 = time.time()
    try:
        r = rewrite(
            raw,
            arguments.get("target_model") or "fable-5",
            retries=1,
            timeout=60,
            concise=bool(arguments.get("concise", True)),
        )
        payload = {
            "action": r.action,
            "intent": r.intent,
            "target_model": r.target_model,
            "rewritten_prompt": r.rewritten_prompt,
            "changes": r.changes,
        }
        record_event("mcp", r.action, target=r.target_model,
                     latency_s=time.time() - t0, prompt_chars=len(raw))
        return {
            "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}],
            "structuredContent": payload,
        }
    except (ValueError, RuntimeError, ClaudeCLINotFoundError) as e:
        record_event("mcp", "error", latency_s=time.time() - t0, detail=type(e).__name__)
        return {"content": [{"type": "text", "text": f"error: {e}"}], "isError": True}


def handle_request(req: dict) -> dict | None:
    """Return a JSON-RPC response dict, or None for notifications."""
    method = req.get("method")
    req_id = req.get("id")
    params = req.get("params") or {}

    if req_id is None:  # notification (e.g. notifications/initialized)
        return None

    if method == "initialize":
        client_version = params.get("protocolVersion", PROTOCOL_VERSION)
        result = {
            "protocolVersion": client_version,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "prompt-tailor", "version": __version__},
        }
    elif method == "tools/list":
        result = {"tools": [TOOL_DEF, STATS_TOOL_DEF]}
    elif method == "tools/call":
        name = params.get("name")
        if name == "refine_prompt":
            result = _handle_tool_call(params.get("arguments") or {})
        elif name == "usage_stats":
            summary = summarize(load_events())
            result = {
                "content": [{"type": "text", "text": json.dumps(summary, ensure_ascii=False, indent=2)}],
                "structuredContent": summary,
            }
        else:
            return {"jsonrpc": "2.0", "id": req_id,
                    "error": {"code": -32602, "message": f"unknown tool: {name}"}}
    elif method == "ping":
        result = {}
    else:
        return {"jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": f"method not found: {method}"}}

    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle_request(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
