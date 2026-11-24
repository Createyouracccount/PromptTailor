---
description: 직전 /prompt-tailor:pm 결과가 별로였을 때 실패 사례를 로컬에 기록 (개선 루프 재료)
argument-hint: [무엇이 틀렸는지 — 생략 가능]
allowed-tools: Bash(python3:*)
---

사용자 코멘트: "$ARGUMENTS"

## 기록 도구

!`python3 __PROMPT_TAILOR_ROOT__/scripts/record_case.py --where`

## 지시

1. 이 대화에서 가장 최근의 `/prompt-tailor:pm` (또는 `/pm`) 호출을 찾아라. 없으면 "기록할 /pm 호출이 없습니다" 한 줄만 보여주고 멈춰라.
2. 아래 필드로 JSON 객체 하나를 만들어라. 대화에 근거가 없는 내용은 지어내지 말고 비워 두거나 "미상"으로 써라.
   - `raw`: 그 /pm 호출의 원문 그대로
   - `context`: 그 원문을 올바르게 해석하는 데 필요한 직전 대화의 요지 1~3문장 (비밀번호·토큰·키·개인정보는 빼고 일반화해서)
   - `interpretation`: 당시 /pm이 출력한 **해석**/**보강** 요지
   - `problem`: 무엇이 틀렸는지 — 사용자 코멘트를 우선하고, 없으면 대화에서 사용자가 정정·불만을 표시한 내용
   - `expected`: 원래 했어야 할 해석과 행동 한두 문장
   - `category`: 위 허용값 중 가장 맞는 하나
3. 위 "기록 명령"의 heredoc 형식 그대로 Bash로 실행해 기록하라 (JSON을 명령 인자로 넘기지 마라).
4. 결과를 한 줄로 보고하라: 기록된 유형과 누적 건수. 그 외 작업은 하지 마라.
