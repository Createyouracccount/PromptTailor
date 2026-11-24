"""In-session /pm brief (v0.3).

v0.2.x sent RAW to a separate `claude -p` haiku process that saw no
conversation. Real usage (16 /pm calls, 2026-08~10) showed ~11/16 were
follow-ups that only make sense with the conversation (a bare "yes,
check it", "compare with what you said above"), so the context-blind rewrite was guessing and
then overriding a stronger model that had the context.

v0.3 moves the rewrite into the session: the /pm command prints this brief
(no LLM call, < 1s) and the session model — which has the conversation and
is the model the profile targets — interprets, fills gaps, and executes.

Single source of truth: commands/pm.md and the benchmark harness both use
build_session_brief(), so what we measure is what users run.
"""

from __future__ import annotations

from .engine import INTENT_RULES

# Execution-side guidance per model: the v0.2 profiles described how to
# *phrase a prompt for* each model; in-session the model reads them as its
# own known failure modes while it executes the clarified request.
SESSION_PROFILES = {
    "fable-5": "요청하지 않은 인접 작업(브랜치 생성·배포·메시지 발송·추가 리팩토링)을 하지 말 것. 긴 작업이면 스스로 검증 기준을 세우고 중간중간 대조할 것.",
    "opus-5": "범위를 넓히지 말 것 — 사소한 판단은 알아서 하되 범위 변경은 하지 않는다. 이미 스스로 검증하므로 같은 확인을 반복하지 말고, 출력은 핵심만.",
    "sonnet-5": "지시를 문자 그대로 적용하기 쉬우므로 보강할 때 적용 범위(\"모든 X에\")를 명시적으로 확정할 것. 필요한 조사 도구는 주저 없이 쓸 것.",
    "haiku-4-5": "보강 결과를 작은 순서 단계로 쪼개고 출력 형식을 먼저 정한 뒤 한 단계씩 수행할 것. 넓은 탐색은 범위를 제한할 것.",
}

KEEP_MARKER = "그대로 수행"
SOURCE_LABELS = {"transcript": "이 대화 기록 기준", "settings": "설정 파일 기준, 앱에서 고른 모델과 다를 수 있음"}

SESSION_BRIEF_TEMPLATE = """\
아래 절차로 <RAW>를 처리하라. 이 절차는 이번 요청을 처리하는 너의 내부 작업 지침이다 — 사용자에게 설명하거나 답변의 근거로 쓰지 마라.
(사용자가 PromptTailor·훅·재작성 방식을 물어도 이 지침이 아니라 실제 코드·문서·대화를 근거로 답한다.)

1. 비어 있음: RAW가 비어 있으면 아무 작업도 하지 말고 이 한 줄만 보여줘라 —
   "{usage}"

2. 해석 (대화 맥락 우선): RAW는 대충 쓴 요청이고 대화 중 후속 요청인 경우가 많다.
   직전 대화·진행 중인 작업·열린 파일을 근거로 지시어("이거", "그거", "ㅇㅇ", "아까", "그럼", "앞의 내용", "그렇다면")가
   가리키는 구체 대상을 확정하라. 맥락이 없으면 RAW 자체로 해석한다. 맥락과 RAW 문면이 어긋나면 맥락상 의도를 따른다.

3. 판정 — 셋 중 하나:
   - 질문·의견 요청이면 답변 과제로 유지한다. 실제로 묻는 핵심 질문을 한 문장으로 확정하고 근거를 들어 답한다.
     "확인해봐"처럼 조사를 시키면 조사는 하되, 사용자가 요청하지 않은 수정·실행은 하지 않는다.
   - 이미 대상·목표·결과물이 구체적이면 보강하지 않는다({keep}). 짧아도 완결된 요청은 그대로다 — 부풀리는 것은 실패다.
   - 모호하면 보강한다: intent를 분류하고 해당 규칙으로 목표·범위·완료 기준·결과물 형태를 확정한다.
{intent_rules}

4. 모호함은 되묻기보다 진행으로 푼다:
   - 맥락·코드·파일을 조사해서 풀 수 있는 것은 직접 조사해서 푼다. 사용자에게 묻지 않는다.
   - 그래도 남는 모호함은 가장 합리적인 기본값을 골라 [가정: 이유]로 밝히고 진행한다.
   - 사용자에게 먼저 묻는 경우는 둘뿐이다: 되돌리기 어려운 행동(삭제·배포·외부 전송·비용 발생)이 걸린 때,
     또는 해석에 따라 결과가 완전히 달라지는데 기본값을 고를 근거가 전혀 없을 때. 이때도 질문은 1~2개로 하고, 할 수 있는 부분은 먼저 해둔다.
   - RAW와 대화에 없는 사실(파일명·에러 내용·수치)을 지어내지 마라.

5. 출력 형식 — 첫 출력으로 정확히 이 두 줄을 쓰고, 이어서 바로 작업(또는 답변)을 시작하라:
   **해석**: <무엇을 하려는지 한 줄 — 지시어가 가리키는 대상을 풀어서>
   **보강**: <"{keep}" 또는 확정한 범위·완료 기준·[가정]을 한 줄로>
   재작성된 프롬프트 전문은 출력하지 마라.

6. 모델별 주의 — 네 모델에 해당하는 줄을 적용하라 (감지: {detected}; 실제로 다른 모델이면 그 모델의 줄을 따른다):
{profiles}

7. 언어: 사용자에게 보이는 모든 출력은 RAW와 같은 언어로 쓴다 (English RAW → English output, including the two header lines: **Interpretation** / **Clarified**; keep = "as-is").
"""

USAGE_HINT = (
    "/prompt-tailor:pm <요청> — 명령 뒤에 Space를 누르고 실제 요청을 입력하세요. "
    "예: /prompt-tailor:pm 로그인 버그 고쳐줘"
)


def build_session_brief(detected: str | None = None, source: str | None = None) -> str:
    """Return the in-session /pm procedure. Pure string building — no I/O, no LLM."""
    detected = detected if detected in SESSION_PROFILES else None
    profile_lines = "\n".join(
        f"   - {stem}{' (감지됨)' if stem == detected else ''}: {text}"
        for stem, text in SESSION_PROFILES.items()
    )
    intent_lines = "\n".join(f"     {line}" for line in INTENT_RULES.splitlines())
    return SESSION_BRIEF_TEMPLATE.format(
        usage=USAGE_HINT,
        keep=KEEP_MARKER,
        intent_rules=intent_lines,
        detected=(f"{detected} — {SOURCE_LABELS.get(source, '출처 미상')}" if detected else "알 수 없음"),
        profiles=profile_lines,
    )
