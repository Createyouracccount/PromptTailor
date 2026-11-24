---
description: 대충 쓴 요청을 대화 맥락으로 해석·보강해 현재 모델에 맞게 바로 수행 (세션 내 재작성)
argument-hint: <대충 쓴 요청>
allowed-tools: Bash(python3:*)
---

<RAW>
$ARGUMENTS
</RAW>

## 처리 절차

!`python3 __PROMPT_TAILOR_ROOT__/scripts/pm_command.py`
