"""Core rewriting engine.

Pipeline: (raw prompt, target model) -> meta-prompt with model profile
-> LLM rewrite via `claude -p` -> parsed result.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

PROFILES_DIR = Path(__file__).parent / "profiles"

# Accepted target-model spellings -> profile file stem
MODEL_ALIASES = {
    "fable-5": "fable-5",
    "claude-fable-5": "fable-5",
    "fable": "fable-5",
    "opus-5": "opus-5",
    "claude-opus-5": "opus-5",
    "opus": "opus-5",
    "sonnet-5": "sonnet-5",
    "claude-sonnet-5": "sonnet-5",
    "sonnet": "sonnet-5",
    "haiku-4-5": "haiku-4-5",
    "claude-haiku-4-5": "haiku-4-5",
    "haiku": "haiku-4-5",
}

DEFAULT_REWRITER_MODEL = "claude-haiku-4-5"


class ClaudeCLINotFoundError(Exception):
    """The `claude` binary is not on PATH. Not retryable — fail fast with guidance."""

# Intent-conditioned guidance: the rewriter classifies intent first, then the
# matching block routes what the rewrite must pin down. Adopted after pairwise
# eval vs the model-profile-only meta (LOOP_LOG R22).
INTENT_RULES = """\
- fix/debug: 증상·재현 경로·기대 동작을 사용자 확인이나 코드 조사로 파악하게 하고(기준 수치·기일을 지어내지 말 것), 최소 수정 범위와 수정 후 검증 방법을 명시
- build: 목표와 의도, 1차 범위(MVP) 경계, 완료 기준을 명시하고 범위 밖 항목은 제외임을 명시
- research: 조사 대상과 산출물 형식(구조·분량)을 지정하고 코드 수정은 하지 않음을 명시
- refactor: 동작 불변 조건과 테스트로 검증함을 명시하고 대상 범위를 한정
- docs: 독자와 형식, 다루는 범위를 지정
- general: 아래 공통·모델 규칙만 적용
단, 의견·질문형 요청은 실행 과제로 변질시키지 말고 답변·평가 과제로 유지하라."""

META_PROMPT_TEMPLATE = """\
당신은 Claude Code 사용자를 위한 프롬프트 재작성 엔진이다. 사용자가 대충 쓴 요청(RAW)을 \
대상 모델({target_model})에 가장 잘 맞는 프롬프트로 재작성한다.

0단계 — 재작성 필요 판정: RAW가 이미 대상·목표·결과물이 구체적이어서 그대로 실행해도 되는 요청이면
(예: "X 파일의 Y를 Z로 바꿔줘", "퀵정렬 함수 짜줘"), action을 "keep"으로 하고 rewritten_prompt에 RAW를
그대로 넣어라. 길이가 아니라 완결성으로 판정하라: 단일 함수·스크립트·쿼리 작성처럼 대상 동작이 완결
지정된 요청은 짧아도 keep이다. 재작성은 모호하거나 범위·완료 기준이 불명확한 요청에만 한다 —
명확한 요청을 부풀리는 것은 실패다.

재작성하는 경우: RAW의 intent를 분류하고(fix|build|research|debug|refactor|docs|general), 해당 유형 규칙을 적용하라:
{intent_rules}

<공통 규칙>
{common_profile}
</공통 규칙>

<대상 모델 프로필 — 이 규칙이 공통 규칙보다 우선한다>
{model_profile}
</대상 모델 프로필>

<RAW>
{raw_prompt}
</RAW>

재작성 규칙:
- RAW에 없는 사실(파일명, 스택, 에러 내용)을 지어내지 마라. 모르는 것은 조사 지시로 바꾸거나 [가정: ...]으로 표시하라.
- RAW에 없는 세부 사항(구체적 항목, 기준 수치, 기술 선택, 방법론 이름)을 추가할 때는 반드시 그 문장에 [가정: 이유]를 붙여라. [가정] 없는 무단 구체화는 실패로 간주된다. 단, 조사 지시("먼저 ~를 파악하라")는 가정이 아니므로 표시가 필요 없다.
  예시 — 나쁨: "OWASP Top 10 기준으로 점검하라" / 좋음: "OWASP Top 10 기준으로 점검하라 [가정: 웹 보안 점검의 표준 기준이므로. 다른 기준이 있으면 알려달라]"
- 출력 언어 = RAW의 언어. RAW가 영어면 rewritten_prompt와 changes를 영어로 써라 (Language rule: write rewritten_prompt and changes in the language of RAW — English in, English out). 이 메타프롬프트가 한국어라는 이유로 한국어로 쓰지 마라.
- 재작성된 프롬프트는 사용자가 그대로 복사해 Claude Code에 붙여넣을 완성문이어야 한다.
- rewritten_prompt는 700자 이내로 작성하라. 길이보다 밀도가 중요하다 — 원문이 단순하면 재작성도 짧아야 한다.

아래 JSON만 출력하라 (다른 텍스트 금지):
{{
  "action": "rewrite 또는 keep",
  "intent": "fix|build|research|debug|refactor|docs|general 중 하나",
  "rewritten_prompt": "재작성된 프롬프트 전문, RAW와 같은 언어로 (keep이면 RAW 그대로)",
  "changes": ["무엇을 왜 바꿨는지 1~3개, 각 한 문장 (keep이면 빈 배열)"]
}}
"""


@dataclass
class RewriteResult:
    intent: str
    rewritten_prompt: str
    changes: list[str]
    target_model: str
    raw_prompt: str
    action: str = "rewrite"  # "keep" = RAW already clear, left untouched


def resolve_profile(target_model: str) -> str:
    key = target_model.strip().lower()
    if key not in MODEL_ALIASES:
        valid = sorted(set(MODEL_ALIASES.values()))
        raise ValueError(f"unknown target model {target_model!r}; valid: {valid}")
    return MODEL_ALIASES[key]


def load_profile(stem: str) -> str:
    return (PROFILES_DIR / f"{stem}.md").read_text(encoding="utf-8")


# Lean condensed (no intent block): for the hook path whose 28s cap leaves no
# latency headroom — intent-routed meta pushed 2/6 A/B calls past 28s while the
# lean meta stayed under (LOOP_LOG R22).
CONDENSED_LEAN_TEMPLATE = """\
당신은 프롬프트 재작성기다. RAW를 Claude {target_model}에 맞게 재작성하라.
RAW가 이미 대상·목표·결과물이 구체적이면 action="keep", rewritten_prompt=RAW 그대로 — 명확한 요청을 부풀리지 마라. 길이가 아니라 완결성으로 판정: 단일 함수·스크립트·쿼리처럼 대상 동작이 완결 지정된 요청은 짧아도 keep. 모호할 때만 action="rewrite".
{target_model} 규칙: {condensed_profile}
공통: RAW에 없는 사실을 지어내지 말 것 — 모르면 조사 지시로 바꾸고, 추가 세부에는 [가정: 이유] 필수. 출력 언어 = RAW의 언어 (RAW가 영어면 rewritten_prompt·changes도 영어로 — English in, English out; 이 지시문이 한국어라는 이유로 한국어로 쓰지 말 것). rewritten_prompt는 700자 이내.
<RAW>
{raw_prompt}
</RAW>
JSON만 출력: {{"action": "rewrite|keep", "intent": "fix|build|research|debug|refactor|docs|general", "rewritten_prompt": "...", "changes": ["1~3개, 각 한 문장"]}}
"""

CONDENSED_TEMPLATE = """\
당신은 프롬프트 재작성기다. RAW를 Claude {target_model}에 맞게 재작성하라.
0단계: RAW가 이미 대상·목표·결과물이 구체적이면 action="keep", rewritten_prompt=RAW 그대로 — 명확한 요청을 부풀리지 마라. 길이가 아니라 완결성으로 판정: 단일 함수·스크립트·쿼리처럼 대상 동작이 완결 지정된 요청은 짧아도 keep. 모호할 때만 action="rewrite".
재작성 시 intent를 분류하고 해당 유형 규칙을 적용하라:
{intent_rules}
{target_model} 규칙: {condensed_profile}
공통: RAW에 없는 사실을 지어내지 말 것 — 모르면 조사 지시로 바꾸고, 추가 세부에는 [가정: 이유] 필수. 출력 언어 = RAW의 언어 (RAW가 영어면 rewritten_prompt·changes도 영어로 — English in, English out; 이 지시문이 한국어라는 이유로 한국어로 쓰지 말 것). rewritten_prompt는 700자 이내.
<RAW>
{raw_prompt}
</RAW>
JSON만 출력: {{"action": "rewrite|keep", "intent": "fix|build|research|debug|refactor|docs|general", "rewritten_prompt": "...", "changes": ["1~3개, 각 한 문장"]}}
"""


def build_meta_prompt(
    raw_prompt: str, target_model: str, concise: bool = False, intent_routing: bool = True
) -> str:
    stem = resolve_profile(target_model)
    if concise:
        # Latency-critical paths (hook): small meta measured max 21.9s vs
        # full meta max 58.3s in the same window (LOOP_LOG R7).
        condensed = (PROFILES_DIR / "condensed" / f"{stem}.md").read_text(encoding="utf-8").strip()
        if not intent_routing:
            return CONDENSED_LEAN_TEMPLATE.format(
                target_model=stem, condensed_profile=condensed, raw_prompt=raw_prompt.strip()
            )
        return CONDENSED_TEMPLATE.format(
            target_model=stem, condensed_profile=condensed,
            intent_rules=INTENT_RULES, raw_prompt=raw_prompt.strip()
        )
    return META_PROMPT_TEMPLATE.format(
        target_model=stem,
        common_profile=load_profile("_common"),
        model_profile=load_profile(stem),
        intent_rules=INTENT_RULES,
        raw_prompt=raw_prompt.strip(),
    )


def call_claude(prompt: str, model: str, timeout: int = 180) -> str:
    # --strict-mcp-config + empty config: skip loading the user's MCP servers.
    # The rewriter needs no tools; this cut measured latency 32.0s -> 25.5s.
    try:
        proc = subprocess.run(
            ["claude", "-p", "--model", model,
             "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}'],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        raise ClaudeCLINotFoundError(
            "`claude` CLI를 찾을 수 없습니다. Claude Code를 설치하고 로그인하세요: "
            "https://claude.com/claude-code"
        ) from None
    if proc.returncode != 0:
        raise RuntimeError(f"claude -p failed (rc={proc.returncode}): {proc.stderr[:500]}")
    return proc.stdout.strip()


def api_enabled() -> bool:
    """Opt-in direct API path: both env vars must be set.

    Off by default so subscription users are never surprise-billed; the
    default path stays `claude -p` (login only, no key)."""
    return bool(os.environ.get("PROMPT_TAILOR_USE_API")) and bool(os.environ.get("ANTHROPIC_API_KEY"))


def call_api(prompt: str, model: str, timeout: int = 180) -> str:
    """Direct Messages API call — skips the `claude -p` startup overhead
    (~29.5k input tokens, ~99% of it the CLI's own system prompt)."""
    try:
        import anthropic
    except ImportError:
        raise RuntimeError(
            "PROMPT_TAILOR_USE_API=1이지만 anthropic SDK가 없습니다. "
            "설치: pip install 'prompt-tailor[api]'"
        ) from None
    client = anthropic.Anthropic()
    try:
        resp = client.with_options(timeout=float(timeout)).messages.create(
            model=model,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIError as e:
        raise RuntimeError(f"API rewrite failed: {type(e).__name__}: {e}") from None
    return "".join(b.text for b in resp.content if b.type == "text").strip()


def parse_json_output(text: str) -> dict:
    """Extract the first JSON object from model output, tolerating code fences."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON object in output: {text[:200]}")
    return json.loads(candidate[start : end + 1])


def rewrite(
    raw_prompt: str,
    target_model: str,
    rewriter_model: str = DEFAULT_REWRITER_MODEL,
    retries: int = 2,
    timeout: int = 180,
    concise: bool = False,
    intent_routing: bool = True,
) -> RewriteResult:
    meta = build_meta_prompt(raw_prompt, target_model, concise=concise, intent_routing=intent_routing)
    caller = call_api if api_enabled() else call_claude
    last_err: Exception | None = None
    for _ in range(retries + 1):
        try:
            output = caller(meta, rewriter_model, timeout=timeout)
            data = parse_json_output(output)
            break
        except (ValueError, json.JSONDecodeError, RuntimeError, subprocess.TimeoutExpired) as e:
            last_err = e
    else:
        raise RuntimeError(f"rewrite failed after {retries + 1} attempts: {last_err}")
    action = str(data.get("action", "rewrite")).strip().lower()
    if action not in ("rewrite", "keep"):
        action = "rewrite"
    return RewriteResult(
        intent=str(data.get("intent", "general")),
        # on "keep" the raw prompt is authoritative regardless of model output
        rewritten_prompt=raw_prompt if action == "keep" else str(data["rewritten_prompt"]),
        changes=[str(c) for c in data.get("changes", [])] if action == "rewrite" else [],
        target_model=resolve_profile(target_model),
        raw_prompt=raw_prompt,
        action=action,
    )
