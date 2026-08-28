# PromptTailor

> 프롬프트 작성이 어려운 Claude Code 사용자를 위한 도구. 대충 쓴 요청을 **현재 선택된 모델에 가장 어울리는 형태로** 재작성합니다.

[English README](README.md)

![PromptTailor 데모: 모호한 요청은 재작성되고, 이미 명확한 요청은 그대로 통과](docs/demo.gif)

*실제 호출 — 약 20초의 대기만 잘라냈습니다. `vhs docs/demo.tape`로 재생성.*

## 왜 필요한가

Claude Fable 5 / Opus 5 / Sonnet 5 / Haiku는 잘 반응하는 프롬프트 스타일이 서로 다릅니다 — Fable은 단계 나열 없이 목표·제약을 산문으로, Opus는 검증 지시를 넣으면 과잉 검증, Haiku는 작은 번호 단계를 선호합니다. PromptTailor는 이 차이를 [모델 프로필](prompt_tailor/profiles/) 데이터로 관리하고, 현재 모델을 자동 감지해 맞춤 재작성합니다. 작업 유형(fix/build/research/refactor/docs)별 라우팅도 적용됩니다.

입력 언어는 유지됩니다: 한국어 입력 → 한국어 출력.

## 설치

**Claude Code 플러그인 (권장):**

```
/plugin marketplace add Createyouracccount/PromptTailor
/plugin install prompt-tailor@prompt-tailor
```

**CLI / MCP 서버:**

```bash
pip install prompt-tailor    # prompt-tailor, prompt-tailor-mcp 명령 설치
```

요구사항: Python 3.10+, `claude` CLI 설치·로그인 (별도 API 키 불필요). macOS/Linux 실사용 검증됨. Windows는 오프라인 테스트가 CI(py3.10/3.12)에서 통과하나, `claude` CLI를 포함한 E2E 경로는 미검증.

## 사용법

```bash
prompt-tailor "대충 쓴 요청" --model fable-5          # 재작성 결과 출력
prompt-tailor "요청" --model haiku-4-5 --json        # JSON 출력
prompt-tailor "요청" --concise                       # 축약 메타프롬프트 (빠름)
```

**Claude Code 안에서** — `/pm 대충 쓴 요청`: 현재 모델에 맞게 재작성 후 변경 요약 한 줄을 보여주고 수행. `/pm`이 "Unknown command"로 나오면(VSCode 확장 등 일부 클라이언트는 플러그인 명령을 네임스페이스로 등록) `/prompt-tailor:pm`으로 호출. auto 모드에서 프롬프트에 위험해 보이는 단어가 있으면 분류기가 백엔드를 오탐 차단할 수 있음 — `claude-code/install.sh`가 안내하는 permissions.allow 규칙을 추가하면 해결(백엔드는 텍스트 재작성만 수행).

**훅 자동 모드 (옵트인)** — 모든 프롬프트를 자동 재작성. `bash claude-code/install.sh`가 출력하는 settings 스니펫 참조. `#raw` 태그로 건별 우회, 6토큰 미만·800자 초과는 자동 무개입, 28초 내 미완료 시 원문 그대로 통과(fail-open).

**직접 API 경로 (옵트인)** — 기본은 `claude -p` 경유(로그인만 필요, 구독 쿼터 소모). `ANTHROPIC_API_KEY`가 있다면 CLI 기동 오버헤드를 우회할 수 있습니다: `pip install 'prompt-tailor[api]'` 후 `PROMPT_TAILOR_USE_API=1`. 두 조건이 모두 설정될 때만 켜지므로 의도치 않은 과금은 없습니다. 이 경로의 지연은 아직 미실측이라 속도 주장은 하지 않습니다. CLI 플래그 실험은 개선 없음으로 판명(중앙값 ~15s 유지 — [runs/MEASUREMENT_LOG.md](runs/MEASUREMENT_LOG.md)).

**Cursor 등 MCP 클라이언트** — 내장 stdio MCP 서버가 `refine_prompt(raw, target_model, concise)`와 `usage_stats`(로컬 기록 요약, LLM 호출 없음) 도구 제공:

```jsonc
// ~/.cursor/mcp.json
{ "mcpServers": { "prompt-tailor": { "command": "prompt-tailor-mcp" } } }
```

```toml
# Codex CLI — ~/.codex/config.toml
[mcp_servers.prompt-tailor]
command = "prompt-tailor-mcp"
```

> **GUI 앱은 셸 PATH를 못 볼 수 있습니다.** command not found가 나오면 `which prompt-tailor-mcp`가 알려주는 절대 경로를 `command`에 쓰거나, `python3` + `args: ["-m", "prompt_tailor.mcp_server"]`를 사용하세요.

재작성 자체는 항상 `claude` CLI를 통해 실행되므로, 어떤 클라이언트에서 쓰든 그 기기에 claude CLI 설치·로그인이 필요합니다. 재작성 대상은 Claude 모델이며, 타 모델 프로필은 제공(검증)하지 않습니다.

## 같은 입력, 모델별 변환 차이 (실제 출력)

입력: `로그인 버그 고쳐줘`

| 대상 `fable-5` | 대상 `haiku-4-5` |
|---|---|
| 산문형: 증상 파악을 먼저 지시하고 "원인을 찾아 가장 단순하게 수정, 테스트·수동 검증으로 완료 확인". 단계 나열 없음 | **1단계** 버그 파악(에러? 위치?) → **2단계** 수정([가정] 태그) → **3단계** 정상/오류 자격증명 테스트 → 결과물: 수정 코드 + 커밋 메시지 한 줄 |

전문은 [eval/results.json](eval/results.json).

## 실측 비용 (n=2, 2026-08-15)

| 지불하는 것 | 실측값 |
|---|---|
| 재작성 1회 (haiku) | **API 환산 ≈$0.03** · 출력 ~1.8k 토큰 · 벽시계 18–33초. 입력 ~29.5k 토큰이지만 ~99%는 `claude -p` 자체 시스템 프롬프트(캐시: ~8k 생성 + ~21.6k 읽기) — 우리 메타프롬프트 몫은 수백 토큰 |
| 훅 컨텍스트 주입 | 본 대화에 **+527 입력 토큰**(토큰 델타로 실측), 세션 내내 히스토리에 잔류 |
| 구독 사용자 | 건별 과금 없음 — 사용량 쿼터를 소모 |

원본 데이터: [runs/cost_measurement.json](runs/cost_measurement.json).

## 검증 근거 — 부정적 결과 포함

모든 주장은 원장([LOOP_LOG.md](LOOP_LOG.md))에 기록된 실측 실험(블라인드 쌍대 심판) 기반입니다:

- **프롬프트 품질** (모호한 요청 골든셋 20건): 20/20 원문보다 낫다 (clarity 5.0 · fidelity 4.8 · actionability 5.0) — [EVAL.md](EVAL.md)
- 모델 프로필 구조 차이 5/5, intent 라우팅 4승 1패 1무
- **작업 결과 파일럿 (n=3): 원문 3승 : 재작성 0승.** *이미 명확하고 자기완결적인* 코드 생성 작업을 headless로 실행했을 때 재작성이 오히려 해가 됨 — 범위 부풀림, 조사 지시로 실행 정지, 검증 요구에 가짜 테스트 결과 날조 — [eval/ab_task_outcome_results.json](eval/ab_task_outcome_results.json)
- **모호 과제 결과 A/B (n=10, 유효 8): 원문 4 : 재작성 4.** 이 도구가 이득을 주장하는 영역인 *모호한 요청*에서도, headless 단일 턴 실행에서는 결과 수준의 우위가 입증되지 않음. 재작성이 합리적 기본 구현을 이끌면 이겼고, 조사 지시가 되묻기만 유발하면 졌음 — [eval/ab_vague_outcome_results.json](eval/ab_vague_outcome_results.json)

**해석**: 실측된 이득은 **모호하고 불충분한 요청**(골든셋 영역)에 있습니다. 그래서 v0.2.0부터 재작성기가 **명확도 게이트**를 먼저 통과시킵니다: 이미 구체적인 요청은 원문 그대로 반환하고(`action: keep`), 훅은 주입 자체를 건너뜁니다. 균형 40건 벤치마크를 **중립 cwd에서 3회 반복 실측**한 게이트 정확도: **90–95%** — 모호 재현율 59/60(해로운 방향 오판은 거의 없음), 명확 재현율 16–18/20. 이전에 공개했던 98%는 1회 실행 수치로 재현되지 않아 폐기했습니다. 데이터셋·러너·회차별 결과·고질적 경계 사례는 [BENCHMARK.md](BENCHMARK.md)에 기록.

## 사용 기록·개인정보·개선에 참여하는 법

모든 재작성 경로가 이벤트 1건(action, 경로, 대상 모델, 지연, 프롬프트 *길이* — **원문 텍스트는 절대 미포함**)을 사용자 기기의 `~/.claude/prompt-tailor/usage.jsonl`에 기록합니다. **어디로도 전송되지 않습니다** — 텔레메트리 없음, 우리는 여러분의 사용을 볼 수 없습니다.

```bash
prompt-tailor stats           # 내 기록 요약: keep/rewrite 비율, 지연, 에러
prompt-tailor stats --share   # 이슈에 붙여넣기 좋은 숫자-전용 마크다운 블록
```

텔레메트리가 없으므로 개선은 여러분이 공유하기로 선택한 것으로 굴러갑니다: 재작성이 해가 됐다면(범위 왜곡, 게이트 오판, 세부 날조) [bad-rewrite 리포트](../../issues/new?template=bad-rewrite.yml)를 남겨주세요 — 리포트는 모든 변경을 검증하는 공개 [벤치마크](BENCHMARK.md)·골든셋에 반영됩니다.

## 보장하지 않는 것

- **실제 작업 성공률 상승은 입증되지 않았습니다 — 모호한 요청에서도요.** 품질 승리는 심판 기반이고, 결과 데이터는 파일럿(원문 3:0 승)과 모호 과제 A/B(4:4 무승부)뿐입니다. 두 실험 모두 headless 단일 턴이라 좋은 확인 질문을 하는 재작성에 구조적으로 불리합니다 — 대화형 실사용은 다를 수 있으나 미측정입니다.
- 재작성기가 가끔 [가정] 표시 없이 세부를 추가하고(fidelity 4.8), intent를 오분류할 수 있습니다.
- 모든 실험은 소표본·단일 심판·이 repo 환경에서 수행됐습니다.

## 개발

```bash
python3 -m unittest discover tests   # 오프라인 테스트 48건 (LLM 호출 없음)
python3 eval/run_eval.py             # 골든셋 평가
```

프로젝트 문서: [PLAN.md](PLAN.md) · [ARCHITECTURE.md](ARCHITECTURE.md) · [RESEARCH.md](RESEARCH.md) · 판정 기준 [GATES.md](GATES.md)

## 라이선스

[MIT](LICENSE)
