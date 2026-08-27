# LOOP_LOG.md — 개선 루프 원장

라운드/세션마다 최상단에 1개 항목 추가 (최신이 위). 형식: 날짜·라운드 / 완료 / 실측 증거 / 발견 문제 / 다음 인수 지점.
이 파일이 세션 간 인수인계의 단일 원장이다. 판정 기준은 GATES.md(동결), 단계 이력은 LOG.md.

---

## 2026-08-28 · R38 (다중 클라이언트 지원 라운드 — MCP usage_stats·PATH 함정 문서화, v0.2.2)

- **배경(사용자)**: "Cursor·Codex 등 여러 곳에서 pm이 동작해야" — 발굴: ① GUI 앱(Cursor 등)은 셸 PATH 미상속으로 `prompt-tailor-mcp` 못 찾을 수 있음(README 무안내) ② MCP 클라이언트에서 사용 기록 확인 수단 없음 ③ 주기 점검용 기간 필터 없음
- **MCP `usage_stats` 도구**: refine_prompt 옆에 추가 — 로컬 usage.jsonl 요약을 LLM 호출 없이 반환. **실 stdio 왕복 E2E 실측**: 이 기기 실기록 4건(cli 2·pm 2, fable/opus 각 2) 정상 반환
- **`stats --last N`**: 최근 N일만 집계(ts 사전순 비교). 테스트로 2020년 이벤트 필터링 확인
- **README 영/한**: Codex CLI(config.toml) 등록 예시, GUI PATH 함정(절대 경로 or `python3 -m prompt_tailor.mcp_server`), 경계 명시(재작성은 항상 claude CLI 경유·타 모델 프로필 미제공). Hermes류 유사 도구 존재는 대화로 인정 — 차별점은 모델별 맞춤+명확도 게이트+증거 공개로 좁게 유지
- **실측**: 오프라인 테스트 44/44 OK. v0.2.2 (패키지 코드 변경이라 PyPI 재배포 필요)
- **다음 인수 지점**: Cursor 실기기에서 refine_prompt/usage_stats 호출 → usage.jsonl `source: mcp` 확인(사용자), pm 실사용 기록 축적

## 2026-08-20 · R37 (실사용 발견 2건 — 빈 프롬프트 usage 안내, 맥락 규칙 첫 실증)

- **실사용(VSCode, 사용자)**: 자동완성에서 `/prompt-tailor:pm`을 Enter로 선택하면 인자 없이 즉시 제출 → `{"error": "빈 프롬프트"}` 2회. 수정: 백엔드가 usage 한 줄 포함 반환 + pm.md 지시 5번 보강(원문도 비면 usage만 안내). 올바른 사용법(명령 뒤 Space → 요청 입력)은 대화로 안내
- **맥락 규칙(R36 지시 6번) 첫 실전 적용**: "이거 바로 이렇게 날아가는데?"가 맥락 없이 "증상 설명 요청"으로 재작성됨 → 실행 모델이 맥락(직전 빈 프롬프트 에러)을 우선해 실제 질문에 답함 — 규칙이 의도대로 동작
- **부수 확인**: 모델 감지 opus-5(사용자 VSCode 세션 실측), 사용자 설치본은 여전히 0.1.0(action 필드 부재로 확인) — 플러그인 업데이트 안내 반복
- **다음 인수 지점**: 사용자 플러그인 0.2.1 업데이트 후 /pm 실사용 기록 축적 확인

## 2026-08-17 · R36 (마무리 라운드 — 사용 기록·stats·피드백 경로, v0.2.1)

- **배경(사용자 질문)**: "사람들이 사용하면 기록이 남는가? 자가개선이 가능한가?" — 정직한 답: 기록은 로컬뿐이며 플러그인 캐시 로그는 업데이트 시 소실, 자동 자가개선은 없음. 데이터 유입 경로가 미완성 → 이번 라운드로 루프를 닫음
- **사용 기록(prompt_tailor/usage.py)**: 4개 경로(hook//pm/CLI/MCP) 전부가 이벤트 1건(action·source·target·latency·prompt 길이 — **원문 텍스트 절대 미포함**)을 `~/.claude/prompt-tailor/usage.jsonl`에 기록. 플러그인 캐시 밖이라 업데이트에도 보존. 기록 실패는 무시(fail-open 유지, 훅은 지연 임포트). 전송 없음 — 텔레메트리 아님
- **stats 명령**: `prompt-tailor stats`(keep/rewrite 비율·지연 중앙값/평균·skip 사유·경로별), `--json`, `--share`(이슈 제보용 숫자-전용 마크다운). 스모크 실측: 4건 샘플에서 keep 비율 33%·중앙값 출력 확인
- **피드백 경로**: .github/ISSUE_TEMPLATE/bad-rewrite.yml — 실패 유형(게이트 오탐/미탐·범위 왜곡·세부 날조·intent 오분류) + 원문/산출/기대 + 선택적 stats --share. 제보 → 벤치마크·골든셋 반영이 개선 루프의 유입구
- **/pm 맥락 규칙(실사용 발견)**: 2026-08-17 실사용에서 후속 질문("이제 남은 과업은?")이 전체 포트폴리오 조사로 범위 부풀려짐 — 백엔드가 대화 맥락 없이 인자만 보는 구조 한계. pm.md 지시 6번 추가: 재작성이 맥락과 어긋나면 맥락상 원문 의도 우선 + 한 줄 고지. 같은 날 VSCode에서 `/pm` 미인식 → `/prompt-tailor:pm` 네임스페이스 형태 README 안내
- **실측**: 오프라인 테스트 42/42 OK(usage 6건 신규: 왕복·프롬프트 텍스트 부재·요약 산술·torn write 허용·share 형식·CLI 경로)
- **다음 인수 지점**: 실사용 stats 축적 후 keep 비율·오판 사례로 벤치마크 확장, 게이트 반복 안정성 측정, Cursor 실기기 검증(사용자), 홍보 여부(사용자)

## 2026-08-16 · R35 (명확도 게이트 구현 + 공개 벤치마크 — 정확도 98%)

- **데이터셋 조사**: HuggingFace·논문 검색 — 우리 용도(재작성/유지 게이트 라벨)의 기성 셋 부재. 관련 연구(Curiosity by Design·CAPA·UnderSpecBench·SWE-chat)는 BENCHMARK.md에 인용. 결론: 자체 구축
- **게이트 구현**: 3개 메타 템플릿에 0단계 판정 추가 — 이미 대상·목표·결과물이 구체적이면 `action: "keep"`(원문 그대로), 모호할 때만 rewrite. 엔진이 keep 시 raw를 권위로 사용(모델 출력 무시), 훅은 keep이면 주입 자체를 생략(+527토큰 오버헤드 회피). /pm·MCP 출력에 action 노출
- **벤치마크 구축**: bench/gate_set.jsonl — 40건 균형(모호 20 = 골든셋, 명확 20 = 파일럿 3건 + 저자 작성 17건), bench/run_gate_bench.py(재현 가능, 원문 보존)
- **실측**: **정확도 39/40 = 98%, 모호 재현율 20/20, 명확 재현율 19/20.** 유일 오판 c02(CSV 스크립트)는 언어·형식 미지정 경계 사례로 문서화. 파일럿 패배 3건 중 2건(퀵정렬·이메일)은 이제 keep 정확 판정. 훅 E2E: 명확 프롬프트 9.4s keep(무주입)·모호 14.4s rewrite — 게이트 추가에도 28s 예산 내
- **문서화**: BENCHMARK.md 신설(데이터셋 출처·실행법·결과·한계·관련 연구·방법론 원칙), README 영/한에 게이트 결과 반영, 메타 길이 불변식 상향(lean<700·routed<1100, 사유 주석)
- **버전**: 0.2.0 (게이트는 동작 변경이므로 마이너 범프) — 릴리스로 PyPI 자동 배포
- **다음 인수 지점**: keep 클래스 데이터를 실사용 로그(옵트인)로 확장, 게이트 반복 실행 안정성(경계 사례 흔들림) 측정, Phase 4 실사용 데이터

## 2026-08-15 · R32~R34 (사용자 문제 제기: 실측 없는 주장 — 비용 실측 + 결과 파일럿, 부정적 결과 공개)

- **문제 제기(사용자)**: 토큰 사용량 실측 없음, 장기 사용 시 이득 보장 근거 없음, README에 변환 예시·숫자 부족 — "말만 번지르르"
- **R32 (비용 실측, `claude -p --output-format json` usage 기반, n=2)**: 재작성 1회 ≈$0.03 API 환산·출력 ~1.8k 토큰·18~33s. 입력 ~29.5k 토큰의 ~99%는 claude -p 자체 시스템 프롬프트(캐시 8k 생성+21.6k 읽기) — 우리 메타 몫은 수백 토큰. 훅 주입 = 본 대화 +527 입력 토큰(프로브 토큰 델타로 실측, 히스토리 잔류). runs/cost_measurement.json
- **R33 (README)**: 실측 비용 표, 모델별 변환 차이 실예시(g01 fable vs haiku), "보장하지 않는 것" 섹션 신설 (영/한)
- **R34 (작업 결과 A/B 파일럿, n=3, 자기완결 codegen, headless, 위치·생성순서 분리, 심판 원문 보존)**: **원문 3승 : 재작성 0승 — 부정적 결과.** 실패 모드: ① 이미 명확한 요청에 범위 부풀림(퀵정렬→이모지·표·최적화판 과잉) ② 조사 지시가 headless 실행 정지 유발(CSV→권한 질문만) ③ 검증 요구에 실행기가 가짜 테스트 결과 날조(이메일). eval/ab_task_outcome_results.json
- **해석(정직)**: 골든셋 20/20과 모순 아님 — **적용 경계 발견**: 이득은 모호한 요청에 국한, 이미 명확·자기완결 요청엔 해악 가능. 단 파일럿 한계: n=3, headless(실제 대화형 환경과 다름), 과제 3건 중 2건은 애초 골든셋 기준으론 "명확한" 요청
- **다음 인수 지점(로드맵 1순위)**: "이미 명확하면 무개입" 게이트 — 재작성기가 명확도 판정을 내려 원문 유지 옵션 반환하도록 메타 확장 + 골든셋(모호)·파일럿형(명확) 혼합 셋으로 게이트 정확도 실측. Phase 4 실사용 데이터 병행

## 2026-08-15 · R31 (PyPI 배포 완료 — Trusted Publishing)

- **완료**: 사용자가 pending publisher 등록(prompt-tailor / Createyouracccount/PromptTailor / publish.yml / env pypi) → publish.yml(OIDC, 토큰 없음) 추가 → workflow_dispatch 트리거 → **publish run success**(attestation 포함)
- **실측**: pypi.org/pypi/prompt-tailor/json → `prompt-tailor 0.1.0` LIVE. 깨끗한 venv에서 `pip install prompt-tailor` → `prompt-tailor --version` 0.1.0 — **실제 PyPI 설치 검증 완료**
- **README 갱신**: 설치 안내를 clone 방식에서 `pip install prompt-tailor` 한 줄로 교체(영/한)
- **배포 채널 최종 상태**: ① 플러그인 2줄(`/plugin marketplace add Createyouracccount/PromptTailor` → `/plugin install prompt-tailor@prompt-tailor`) ② `pip install prompt-tailor` ③ GitHub Release v0.1.0. 이후 버전업은 pyproject version bump → 릴리스 발행 시 자동 배포
- **다음 인수 지점**: Phase 4 — 실사용 데이터(수락/거부) 수집, Cursor 실기기 검증(사용자), 홍보 여부는 사용자 판단

## 2026-08-15 · R30 (PromptTailor 전면 리브랜딩 — PyPI 이름 차단 대응)

- **배경**: PyPI가 `promptmaker`를 기존 `prompt-maker`와 혼동 유사(구분자 차이)로 차단. 이름 심사(후보 26종 가용성 전수 확인, 유사 변형 포함) → 사용자 승인으로 **prompt-tailor** 확정 — "모델에 맞춰 재단"이라는 차별점을 이름이 직접 전달
- **개명 범위(전면)**: Python 패키지 `promptmaker`→`prompt_tailor`, CLI `prompt-tailor`, MCP `prompt-tailor-mcp`(serverInfo 동일), 환경변수 `PROMPT_TAILOR_ACTIVE`, 플러그인·마켓플레이스 `prompt-tailor`, 훅 컨텍스트 태그 `[PromptTailor]`, installer placeholder `__PROMPT_TAILOR_ROOT__`, README 영/한, GitHub repo `PromptTailor`(구 URL 자동 리다이렉트), 로컬 폴더, 사용자 설정(allow 규칙·설치본 pm.md). `/pm` 커맨드명·`refine_prompt` 도구명은 유지. 역사 기록(원장 과거 항목·실험 결과 JSON)은 위조 방지 위해 미수정
- **실측 재검증**: 오프라인 테스트 37/37 OK / 새 이름 빌드+twine check PASSED / 깨끗한 venv 설치 → `prompt-tailor`·`prompt-tailor-mcp` 동작 / 격리 CLAUDE_CONFIG_DIR에서 플러그인 marketplace add→install 성공 / 개명된 경로에서 훅 E2E 성공(`[PromptTailor]` 태그) / CI green(개명 커밋)
- **릴리스**: v0.1.0 노트를 새 이름으로 갱신(개명 사유 명기)
- **다음 인수 지점**: PyPI pending publisher에 `prompt-tailor` 등록(사용자) → publish.yml 추가 → 자동 배포. 이후 pip 이름은 prompt-tailor

## 2026-08-15 · R27~R29 (배포 라운드: 영문화 + 플러그인화 + CI·릴리스)

- **R27 (README)**: 영어 입력 경로 첫 검증 — "fix the login bug asap..." → 영어 산문 재작성, fable 프로필·조사 지시·범위 경계 정상(이 실측 출력을 README 예시로 사용). README.md 영문 재작성(before/after 예시·검증 근거·정직한 한계 포함), README.ko.md 분리
- **R28 (플러그인)**: `.claude-plugin/plugin.json` + 자체 marketplace.json + `commands/pm.md`(`${CLAUDE_PLUGIN_ROOT}` — 경로 하드코딩 구조적 해소). **실측**: 격리 CLAUDE_CONFIG_DIR에서 marketplace add → install 성공, 인벤토리 스킬 1(pm)·상시 ~13토큰, 플러그인 캐시에서 백엔드 실행 정상(격리 환경 실패 1건은 자식 claude -p가 로그인 없는 격리 설정을 상속한 테스트 아티팩트로 판명). 설치는 이제 2줄: `/plugin marketplace add Createyouracccount/PromptMaker` → `/plugin install promptmaker@promptmaker`
- **R29 (CI·릴리스)**: GitHub Actions(py3.10·3.12, unittest 37건+build+twine check) **green** — Ubuntu 통과로 Linux 호환 실증. v0.1.0 태그 + GitHub Release 발행
- **잔존**: PyPI 업로드(토큰 대기), Cursor 실기기(사용자 확인), legacy claude-code/commands/pm.md와 플러그인 commands/pm.md 이중 관리(플러그인 정착 시 legacy 제거 검토)
- **다음 인수 지점**: 사용자 플러그인 설치 전환 시 기존 ~/.claude/commands/pm.md와 /pm 이름 충돌 주의(수동 설치본 제거 권장). Phase 4 실사용 데이터 수집

## 2026-08-15 · R26 (실사용 발견: auto 모드 분류기 오탐 차단)

- **관측(사용자)**: `/pm docker prune 시작해서...` → "Permission denied by the auto mode classifier". 원인: `!` 확장이 사용자 프롬프트를 명령줄 인자로 포함 → 분류기가 인자 속 "docker prune·정리" 문구를 위험 명령으로 오분류. 실제 실행되는 것은 텍스트 재작성 파이썬 스크립트뿐(구조적 오탐)
- **수정**: ① 사용자 전역 ~/.claude/settings.json permissions.allow에 `Bash(python3 .../pm_command.py:*)` 추가(JSON 유효성 검증) — 허용 규칙은 분류기보다 우선 ② install.sh에 auto 모드 사용자용 안내 추가 ③ README에 트러블슈팅 기재
- **잔존 한계(기록)**: 명령줄 인자에 프롬프트가 노출되는 구조 자체는 유지 — allow 규칙 없이는 auto 모드에서 위험 단어 포함 프롬프트가 차단됨. 근본 해법(플러그인화 시 stdin 전달 등)은 배포 단계 검토
- **다음 인수 지점**: 사용자 재시도로 allow 규칙 효과 확인, 실사용 관측 계속

## 2026-08-15 · R25 (첫 실사용 관측 — /pm 정상 동작 + 준수 결함 2건 수정)

- **첫 실사용 (사용자, 디스크 정리 요청)**: pm_command.log 15:58:57 `ok target=opus-5` — 재작성 실행·주입 확인. 세션 응답에 재작성 지문 확인(삭제 금지 경계, 산출물 분류 형식, 측정→분류 조사 구조 — 원문에 없던 것)
- **관측된 준수 결함**: ① 변경 요약 한 줄 미표시 ② 수행 모델이 한국어 원문에 영어로 응답 (재작성문 자체는 한국어 — 수행 지시문 준수 문제)
- **수정**: pm.md 지시를 번호 목록으로 강화 — 변경 요약을 1번 규칙으로("생략하지 마라"), 응답 언어 규칙 신설(원문 언어로). 재설치 완료, 다음 /pm부터 적용
- **다음 인수 지점**: 실사용 관측 계속 — 다음 /pm 호출에서 두 결함 재발 여부 확인. Phase 4 데이터 수집

## 2026-08-15 · R24 (실사용 전 최종 점검 — 인계 라운드)

- **신규 사용자 경로 전체 재현**: GitHub fresh clone → pip 설치 → 오프라인 테스트 37/37 OK → promptmaker·promptmaker-mcp 엔트리포인트 생성 확인
- **3경로 실동작**: /pm 백엔드(모델 자동 감지 opus-5, intent 라우팅 동작) / 훅 E2E 18.8s 성공·유효 JSON / MCP initialize·tools/list 정상. 설치본 ~/.claude/commands/pm.md 최신 확인
- **발견·수정 1건**: fix/debug 재작성이 원문에 없는 기준 수치("영업일 1~5일")를 [가정] 없이 발명 — INTENT_RULES fix/debug에 "사용자 확인·코드 조사로 파악(기준 수치·기일 지어내지 말 것)" 명시 → 동일 프롬프트 재실행에서 발명 소멸·조사 지시로 대체(단건 확인)
- **판정: 실사용 인계 가능.** 훅 자동 모드는 옵트인 유지(README·install.sh 스니펫 참조)
- **다음 인수 지점**: 사용자 실사용 피드백(수락/거부) 수집 → Phase 4. PyPI 토큰 대기, README 영문화·CI·릴리스 태그는 배포 단계 작업

## 2026-08-14 · R23 (심판 검증: R21·R22 주장 — 성립 3/3, 단 R21 주장 하향 정정)

- **심판 판정 (fresh-context, 반증 프레이밍, 수치 재계산·배선 확인·g19 재현 포함)**: C1(언어 A/B) 성립 / C2(라우팅 차등) 성립 / C3(의견형 보호) 성립
- **심판 부기 → 정직한 정정**: 언어 A/B에 **위치 편향 교락** — 6쌍 중 5쌍에서 먼저 생성된 A 위치가 승리, 배정은 균형(K/E 각 3회)이나 생성 순서와 위치가 완전 교락. n=6에서 "한국어 우세"와 "위치 편향"을 분리 불가. **R21 결론을 "한국어 우세 입증"에서 "영어 우세 근거 없음 → 한국어(현상) 유지"로 하향 정정** — 유지 결정 자체는 유효(영어 전환의 근거가 없으므로)
- **라우팅 A/B는 강건**: v2 승리 4건이 A위치 2회·B위치 2회로 분산 — 위치 편향으로 설명 불가, 결론 유지
- **기타 부기 기록**: 환경 문맥 누출(재작성기가 repo 문맥 흡수 — 평가 일반화 약화, 실사용에선 유익), C2 지연 근거는 eval 경로 간접 실측(hook.log 28s 타임아웃 3건이 방증), v1은 복원 템플릿, 단일 심판·단일 런·무유의성검정
- **방법론 개선 의무(이후 실험)**: 쌍대 실험은 생성 순서와 제시 위치를 독립 교차시킬 것(A/B 위치 무작위화 + 순서 역균형), 골든셋 평가는 repo 밖 중립 cwd에서 실행할 것
- **다음 인수 지점**: Phase 4 실사용 데이터 수집(수락/거부율), language-matched 메타 실험(위 방법론으로), PyPI 토큰 대기

## 2026-08-14 · R22 (라우팅 v2: intent별 가이던스 — 경로별 차등 적용)

- **문제(사용자 지적)**: intent를 분류만 하고 라우팅에 미사용 — 모델 축(4프로필)만 있고 작업 유형 축 없음
- **구현**: INTENT_RULES(fix/debug·build·research·refactor·docs·general 별 1줄 가이던스) — 재작성기가 intent 분류 후 해당 블록 적용. full·condensed 메타 양쪽 주입
- **쌍대 실측 (eval/ab_routing_results.json, 블라인드 심판·원문 보존)**: **v2 4승 / v1 1패 / 1무.** 승리 사유: 증상·재현·완료기준 구체화(g01), 실행 절차 명시(g05), 가정 태깅 개선(g16)
- **패배 분석(g19)**: 의견 요청("어떻게 생각해")을 build로 오분류 → 실행 과제로 변질. 보호 규칙 1줄 추가("의견·질문형은 답변·평가 과제로 유지") → g19 단건 재검증: general 분류·평가 과제 유지 확인
- **지연 트레이드오프 발견 → 경로별 차등**: intent 블록 포함 시 2/6이 28s 초과(v1은 0/6), 훅 청정 재측정에서도 2/3 캡 초과 → **훅(28s 캡)은 경량 메타(intent_routing=False) 유지, /pm·CLI·MCP(60s+ 예산)는 v2 적용.** 차등 적용 후 훅 2/2 성공(21.9s/24.6s — 같은 프롬프트가 라우팅 메타로는 같은 시간대에 타임아웃)
- **테스트**: lean/routed 분기 고정 3건 추가, 37/37 OK
- **한계(정직)**: 실험 n=6·재작성기 haiku 1종·느린 시간대 측정 혼재. intent 오분류 가능성 잔존(g13→fix로 분류됐으나 v2 승리)
- **다음 인수 지점**: 실사용 데이터(Phase 4)로 intent 분류 정확도·수락률 검증, language-matched 메타(영어 원문→영어 메타) 실험

## 2026-08-13 · R21 (메타프롬프트 언어 A/B — 한국어 유지 결정, 근거 확보)

- **문제 제기(사용자)**: 한국어 메타프롬프트/프로필이 최선이라는 근거 없음. 문헌은 혼재(기술 지시문은 영어 동등~우세 경향, 원어는 문화 맥락 과제에서 우세)
- **실험**: 골든셋 6건(다양한 intent), 한/영 condensed 메타 쌍대 비교. 같은 시간대 교차 실행(시간대 편차 통제), 블라인드 심판(A/B 배정 기록 후 해맹), 심판 원문 보존
- **실측 (eval/ab_meta_language_results.json)**: **한국어 4승 / 영어 2승 / 무 0.** 지연 K avg 20.8s vs E avg 27.6s. 언어 보존(한국어 출력) 양쪽 12/12. 영어 메타는 토큰 수도 이점 없음(849자 ≈ 한국어 440자와 유사 토큰)
- **분석**: 승패 사유는 메타 언어 자체보다 무단 가정 추가 여부(fidelity)가 지배 — 실행 간 편차가 언어 효과보다 클 수 있음. 즉 "영어가 낫다" 가설은 우리 데이터에서 기각, 한국어 유지
- **한계·개방 항목**: n=6, 재작성기 haiku 1종, 원문이 전부 한국어. 영어 원문 사용자의 경우 영어 메타가 나을 가능성 미검증 — 원문 언어에 메타 언어를 맞추는 language-matched 라우팅은 향후 과제
- **부수 발견**: claude -p가 cwd 컨텍스트를 재작성에 주입(g18에서 repo 언급) — 훅 실사용에선 사용자 프로젝트 맥락 반영이라 유익, 평가에선 노이즈로 기록
- **다음 인수 지점**: R22 라우팅 v2 — intent 분류를 실제 라우팅에 사용(유형별 가이던스 블록), 쌍대 실측 후 채택

## 2026-08-12 · R19~R20 (사용자 승인 반영: 스킵 기준 완화 + Phase 3 MCP 서버 — 게이트 3/3 PASS)

- **사용자 승인 (4건)**: ① Phase 3 착수 ② 스킵 기준 <10→<6토큰 ③ PyPI 배포 ④ Windows는 "미검증 명시 유지". GATES.md에 개정 이력 2건 기록(동결 규칙 준수 — 사용자 승인으로만 변경)
- **R19 (스킵 기준)**: pm_hook <6토큰 적용. **실측**: "배포 자동화 하고싶어 도와줘"(7토큰) 훅 E2E → 17.2s 재작성 성공(구 기준에선 스킵되던 케이스), 회귀 테스트 추가 28/28 OK
- **R20 (MCP 서버, G3-1~3)**: promptmaker/mcp_server.py — stdio 개행 구분 JSON-RPC 2.0, 의존성 0, initialize/tools/list/tools/call/ping. `promptmaker-mcp` 엔트리포인트(깨끗한 venv 실측). 프로토콜 오프라인 테스트 6건 포함 34/34 OK
- **실측 증거**: runs/mcp_g31_roundtrip.txt(3왕복 원문, tools/call 실호출 포함) / runs/mcp_g32_claude_client.txt(독립 클라이언트 claude -p가 서버 스폰·호출, fable-5 산문 재작성 수신)
- **심판 판정 (fresh-context, 반증 프레이밍, 직접 재실행 포함)**: **G3-1 PASS / G3-2 PASS / G3-3 PASS — Phase 3 게이트 3/3.** 심판이 프로토콜 왕복·독립 클라이언트 호출·테스트 34건을 직접 재실행해 확인
- **심판 부기 → 조치**: ① R19·R20 원장 기록(본 항목) ② README 상태 갱신(같은 커밋) ③ [의무] 향후 MCP 클라이언트 증거는 --output-format stream-json으로 도구 호출 트랜스크립트까지 캡처 ④ [경미·기록만] initialize가 클라이언트 protocolVersion 에코 — 엄밀한 버전 협상 아님
- **다음 인수 지점**: PyPI 배포(승인됨, 자격증명 확인 필요), Cursor 실기기 검증(사용자 확인 항목), Phase 4(사용 데이터 기반 개선)

## 2026-08-12 · R18 (설치 화면 사용자 언어화 + 플랫폼 명시 — 루프 종료 라운드)

- **발굴**: install.sh 출력이 내부 연구 용어(G2-3·심판 3차·LOOP_LOG R7)를 신규 설치자에게 노출, README에 플랫폼·Python 요구사항 불명
- **완료**: 설치 문구를 사용자 언어로 교체(동작 설명 + 15~20초·28초 fail-open), README 요구사항에 Python 3.10+·macOS/Linux 검증·Windows 미검증 명시
- **실측**: install.sh 재실행 출력 확인, 테스트 27/27 OK
- **루프 종료 판정**: R8~R18 총 11라운드로 세션 처리 가능 백로그 소진 — 잔여는 전부 사용자 결정 필요(스킵 기준 재검토=동결 게이트 연관, Phase 3 MCP 게이트 초안 승인, PyPI 배포 여부, Windows 지원 여부). 선순환 체계(발굴→수정→실측→커밋→원장)는 PROMPT.md 재개 블록으로 다음 세션에서 재가동 가능
- **다음 인수 지점**: 사용자 승인 대기 항목 처리 후 Phase 3 착수

## 2026-08-12 · R17 (타임아웃 재시도 버그 수정)

- **발굴(버그)**: rewrite 재시도 except 절에 subprocess.TimeoutExpired 누락 — 타임아웃이 재시도를 우회하고 원시 트레이스백 노출 (훅은 fail-open이라 무사, CLI·/pm 경로 노출). CLI는 최종 RuntimeError도 미포획
- **완료**: except 절에 TimeoutExpired 추가, CLI에 RuntimeError → "재작성 실패: ..." + rc=1
- **실측**: 오프라인 테스트 2건 신설(call_claude 몽키패치) — 타임아웃 1회 후 성공 시 2회 호출·정상 결과 / 소진 시 RuntimeError. 전체 27/27 OK
- **다음 인수 지점**: 세션 처리 가능 백로그 사실상 소진 — 다음 라운드 신규 발굴 없으면 종료 보고(사용자 승인 대기: 스킵 기준, Phase 3 MCP 게이트)

## 2026-08-12 · R16 (/pm 백엔드 응답성 — 축약 메타 + 60s 캡)

- **발굴**: pm_command.py가 전체 메타(R7 실측 avg 41.4s·max 58.3s) + timeout=180·retries=1 — 인라인 대기 경로인데 최악 ~6분 블로킹 가능
- **완료**: `rewrite(..., retries=1, timeout=60, concise=True)`로 전환(훅과 동일한 검증된 경로), `__import__('time')` 인라인 제거
- **실측**: `time python3 scripts/pm_command.py "결제 모듈 리팩토링..."` → 30.9s, 유효 JSON([가정] 표기 포함). 최악 상한 ~2×60s로 확정. 오프라인 테스트 25/25 OK
- **다음 인수 지점**: 사용자 승인 대기 2건(스킵 기준, Phase 3 MCP 게이트) — 세션 처리 가능 백로그 소진 여부 다음 라운드 판정

## 2026-08-12 · R15 (루브릭 v2로 골든셋 전체 재평가 — 혼용 금지 해소)

- **완료**: R13 루브릭(조사 지시 예외)으로 골든셋 20건 전체 재평가 (`eval/run_eval.py --workers 5`, 백그라운드)
- **실측**: total=20 ok=20 errors=0 / verdict better 20-same 0-worse 0 / clarity 5.00·fidelity 4.80·actionability 5.00 / 프로필 차이 5/5. results.json 갱신(before는 git 이력에 보존)
- **정직성 주의**: 재작성도 재실행됐으므로 fidelity 4.10→4.80 전체를 루브릭 효과로 귀속 불가 — 격리 실측은 R13(동일 재작성본 4건 중 3건 4→5)이 근거
- **다음 인수 지점**: 사용자 승인 대기 2건(스킵 기준 재검토, Phase 3 MCP 게이트) 외 세션 처리 가능 백로그 소진 접근 — 다음 라운드는 신규 발굴(코드 품질·이식성) 또는 소진 시 종료 보고

## 2026-08-12 · R14 (오프라인 유닛 테스트 신설 — 회귀 안전망)

- **발굴**: repo에 유닛 테스트 전무 — 루프가 커밋을 계속 쌓는 구조인데 회귀 안전망이 없음
- **완료**: tests/test_offline.py (stdlib unittest, LLM 호출·네트워크 없음) — parse_json_output(펜스·주변 텍스트·실패), resolve_profile 별칭, build_meta_prompt(full/concise 길이 불변식 <700자), normalize_model([1m] 접미사·mythos→fable), 감지 우선순위(transcript>settings, local>project), 훅 스킵 규칙(슬래시·#raw·#rawdata 오탐·단문·장문), estimate_tokens(한/영 제수·단어 하한). pm_hook은 하이픈 경로라 importlib 로드
- **실측**: `python3 -m unittest discover tests` → 25/25 OK (0.003s)
- **다음 인수 지점**: 백로그 — (선택) 신 루브릭 골든셋 전체 재평가, 스킵 기준·Phase 3 게이트는 사용자 승인 대기

## 2026-08-12 · R13 (심판 루브릭에 조사 지시 예외 명문화 — 백로그 해소)

- **발굴**: 엔진 재작성 규칙은 "조사 지시는 가정 아님(표시 불요)"인데 심판 fidelity 루브릭에는 이 예외가 없어 규칙-루브릭 불일치 — 실제로 g01·g05·g11·g19 등이 조사 절차 추가를 이유로 fidelity 4점
- **완료**: JUDGE_PROMPT fidelity 기준에 조사 지시 예외 명문화
- **실측**: 기존 재작성본 4건 재심판(재작성 재실행 없음 — 루브릭 효과만 격리) → g01·g05·g11 fidelity 4→5(사유가 정확히 조사 지시 인정으로 바뀜), g19는 별개 사유(의견 요청→보고서로 범위 팽창)로 4 유지 — 예외 과잉 적용 아님. verdict 4/4 better 유지. 심판 원문 runs/rejudge_r13.json 보존(R7 의무 이행)
- **주의**: results.json의 기존 fidelity 평균(4.10)은 구 루브릭 기준 — 신 루브릭 전체 재평가 전까지 혼용 금지
- **다음 인수 지점**: 백로그 — 스킵 기준(사용자 승인 대기), Phase 3 MCP 초안 승인 대기, (선택) 신 루브릭으로 골든셋 전체 재평가

## 2026-08-12 · R12 (claude CLI 미설치 시 친절한 에러)

- **발굴**: `claude` 바이너리가 PATH에 없으면 FileNotFoundError 원시 트레이스백 노출 — 재시도 루프도 못 잡는 예외라 신규 사용자가 원인(설치·로그인)을 알 수 없음
- **완료**: `ClaudeCLINotFoundError`(비재시도, Exception 직속 — retry except 절 비포획) 신설, call_claude에서 FileNotFoundError 변환, CLI에서 한 줄 안내 + rc=1
- **실측**: `env PATH=/usr/bin:/bin python3 -m promptmaker.cli "..."` → 트레이스백 없이 "오류: `claude` CLI를 찾을 수 없습니다..." + rc=1. 훅 경로는 기존 fail-open이 전 예외 포획이라 영향 없음
- **다음 인수 지점**: 백로그 계속 — 심판 루브릭 조사 지시 예외 명문화, 스킵 기준(사용자 승인 대기), Phase 3 MCP 초안 승인 대기

## 2026-08-12 · R11 (README 온보딩 — clone→pip install 경로)

- **발굴**: README 사용법이 연구 폴더 내부 실행 기준 — GitHub 방문자의 clone→설치→실행 경로 부재
- **완료**: Quick Start(clone + `pip install .` + install.sh) 신설, 사용법을 설치된 `promptmaker` 명령 기준으로 갱신, `--concise` 반영
- **실측**: venv에 재설치 후 `promptmaker --help`로 문서화한 플래그(-m/--json/--concise) 전부 존재 확인
- **다음 인수 지점**: R8~R10 항목의 백로그 계속 (스킵 기준 재검토는 사용자 승인 대기)

## 2026-08-12 · R8~R10 (GitHub 공개 + 배포 품질 라운드)

- **공개 전 정리**: 개인 절대경로 3곳 제거 — pm.md는 `__PROMPTMAKER_ROOT__` placeholder + install.sh sed 치환으로 전환(하드코딩 경로는 이식성 버그이기도 했음). 재설치 실측으로 치환 동작 확인. 크리덴셜 스캔 결과 없음. `.gitignore`에 runs/hook.log·pm_command.log 추가(런타임 로그는 사용자 프롬프트 포함 가능 — 커밋 금지)
- **공개**: https://github.com/Createyouracccount/PromptMaker (public, main). 이후 라운드는 1문제=1커밋으로 푸시
- **R8**: MIT LICENSE 추가 + pyproject license 필드 (공개 repo 라이선스 부재는 타인 사용 불가 문제)
- **R9**: 패키징 버그 수정 — package-data가 `profiles/*.md`만 포함해 pip 설치본에서 concise 모드(훅 경로) 깨짐 → `profiles/condensed/*.md` 추가. **실측**: 깨끗한 venv에 pip 설치 → condensed 4종 포함·`build_meta_prompt(concise=True)` 동작·`promptmaker --version` 엔트리포인트 확인
- **R10**: 백로그 해소 — CLI에 `--concise` 플래그 노출. **실측**: `--concise --json` E2E 정상 출력(intent=fix, 유효 JSON)
- **다음 인수 지점**: 지속 루프 계속 — 남은 백로그: <10토큰 스킵 기준 재검토(게이트 연관— 사용자 승인 필요), 심판 루브릭 조사 지시 예외, README 신규 사용자 온보딩(영문 병기·요구사항), Phase 3 MCP 게이트 초안 승인 대기

## 2026-08-11 · R7 (메타프롬프트 축약으로 G2-3(c) 해소 — Phase 2 전 게이트 PASS)

- **가설**: 미시도 레버였던 입력 크기 축소가 지연 병목일 것 (기존: 출력 상한·플래그는 효과 없음)
- **완료**: CONDENSED_TEMPLATE + `profiles/condensed/*.md` 4종(각 ~250자) 신설, `build_meta_prompt(concise=True)`, 훅은 `retries=0, timeout=28, concise=True` (28s 캡 초과 시 fail-open 무개입)
- **실측 증거**:
  - 축약 메타(316자) 4회: 14.8~21.9s (avg 19.5) vs 전체 메타(2425자) 같은 창 4회: 15.3~58.3s (avg 41.4) — **입력 크기가 병목 맞음**
  - 훅 E2E 6샘플: 성공 5건 14.5~19.2s, 1건 28.0s 캡 fail-open (hook.log `ERROR (28.0s): TimeoutExpired` — 캡 작동 확인)
  - 품질 회귀 검사(축약 메타, 골든셋 4건): **verdict 4/4 better 유지**, clarity·fidelity 동일, actionability는 g01·g05에서 5→4 경미 하락 (심판 지적 반영해 "동등"이 아니라 "verdict 동등·actionability 경미 하락"으로 정정 기록). 축약 4건의 심판 원문 미저장은 실수 — 이후 라운드는 원문 보존 의무
- **심판 3차 판정 (G2-3 한정, 독립 재실행 2회 포함)**: **(a) PASS (b) PASS (c) PASS — G2-3 전체 PASS.** 독립 실측 16.93s/18.39s, JSON 기계 검증 통과. (c)의 fail-open 인정 근거: 완료 주체는 훅 프로세스이며 (b)가 무개입을 유효 동작으로 규정, 기능 경로도 7/8건 <20s로 실증
- **Phase 2 종합: 게이트 5/5 PASS** (G2-1·G2-2·G2-4·G2-5는 2차, G2-3은 3차). 사용자 결정 3안은 (b)에 준하는 결과를 키 없이 달성해 해소 — 훅 자동 모드 정식화
- **다음 인수 지점**: Phase 3 게이트는 GATES.md에 미정의(동결 파일이라 세션이 추가 불가) — 사용자 승인용 초안을 최종 보고에 제시. 잔여 백로그: <10토큰 스킵 기준 재검토(실제 타깃 프롬프트 스킵), 심판 루브릭에 조사 지시 예외 명문화, CLI 경로에도 concise 옵션 노출

## 2026-08-11 · R6 (심판 2차 판정 + 잔존 지적 수정 — Phase 2 종료)

- **심판 2차 판정 (fresh-context, 반증 프레이밍, LLM 재실행 0회)**:
  G2-1 **PASS** / G2-2 **PASS** / G2-3 **FAIL**((c) 30s만 미달, (a)(b) 충족) / G2-4 **PASS**((a) 코드 확인, (b) 지적 5→1~2 감소 검증 — 심판은 g05를 엄격 판독 시 잔존으로 봄) / G2-5 **PASS**. "G2-3(c) 미달 보고의 정직성: 정직(PASS)"
- **심판 잔존 지적 → 즉시 수정**: ① install.sh 스니펫에 "30s 게이트 미달·사용자 결정 대기" 명기 ② pm_hook docstring "<4 words"→"<10 tokens" 정정 ③ `#raw` 뒤 구두점 매칭(`#raw\b`, `#rawdata`는 여전히 비스킵 — 3케이스 재검증 통과)
- **미수정(정보로 기록)**: <10토큰 스킵이 실제 타깃 프롬프트("배포 자동화 하고싶어 도와줘"=7토큰)도 걸러냄 — 게이트 문구에는 부합하나 행동 트레이드오프. 게이트 재검토 대상으로 사용자에게 보고
- **Phase 2 종합**: 게이트 4/5 PASS. **G2-3(c)만 미달** — claude -p 경로의 구조적 지연(기동+API 편차)으로 30s 안정 충족 불가. 기준 완화 없이 사용자 결정 3안 제시: (a) 게이트를 "설정 timeout(60s) 내"로 개정 (b) Phase 3에서 직접 API 호출(ANTHROPIC_API_KEY 필요, 기동 ~11s 제거) (c) 훅 자동 모드를 실험 기능으로 유지하고 /pm을 기본 경로로
- **다음 인수 지점**: 사용자 결정 반영 → Phase 3 (MCP 서버 for Cursor / 직접 API 옵션 / 심판 루브릭에 조사 지시 예외 명문화 / <10토큰 기준 재검토)

## 2026-08-11 · R5 (심판 1차 FAIL 항목 수정)

- **심판 1차 판정**: G2-1 PASS / G2-2 PASS / G2-3 FAIL / G2-4 FAIL / G2-5 PASS(보완 요망). 지적 F-1~F-7 (전문은 세션 보고에 첨부)
- **수정 완료**:
  - F-2 → run_eval.py `_call_judge`: 심판 호출에 재시도 2회 + 필수 필드 검증 (실측된 실패 모드 g19 잘림·g02 필드 누락을 정확히 커버)
  - F-3 → 단문 스킵을 <10토큰 추정으로 변경 (한국어 chars/2, 영어 chars/4, 단어 수 하한)
  - F-7b → `#raw` 정확 토큰 매칭 (`#rawdata` 오탐 해소, 실측 확인)
  - F-7c → 훅 내부 재작성 호출 timeout 40s 캡 (훅 예산 60s 내 fail-open 보장)
  - F-6 → R3/R3.1 원장 기재 (아래 항목)
- **지연 개선 시도 (P1) 실측**:
  - MCP 로딩 차단(`--strict-mcp-config --mcp-config '{}'`): 32.0s → 25.5s 단발 확인 → 엔진 반영
  - `--bare`: 로그인 자격증명까지 스킵되어 사용 불가 (rc=1 "Not logged in")
  - `--disable-slash-commands --disallowedTools "*"`: 역효과 (avg 56.9s) → 폐기
  - 동일 시간대 대조 4회 (현행 구성): 25.1 / 31.7 / 32.9 / 34.7s — avg 31.1, max 34.7
- **판정 (정직하게)**: **G2-3(c) 30s 기준은 claude -p 경로로 충족 불가** (p50≈30s, 시점 편차 ±10s). GATES는 동결이므로 완화하지 않음 → "미달 + 사용자 결정 대기"로 보고. 선택지: (a) 게이트를 "훅 timeout 설정값(60s) 내"로 개정 승인 (b) Phase 3에서 직접 API 호출(키 필요, 기동비 제거) (c) 훅 자동 모드를 실험 기능으로 표기하고 /pm을 기본 경로로
- **다음 인수 지점**: g07·g09 재실행 판독 → 심판 2차

## 2026-08-11 · R3.1 (fidelity [가정] 예시 보강)

- **완료**: 메타프롬프트에 [가정] 규칙 위반/준수 구체 예시 추가 → g05·g13 재실행
- **실측 증거**: g13 지적 해소 ("추가한 가정을 명시적으로 표시해 왜곡 없이") / g05는 조사 지시 추가에 대한 지적 잔존 — 우리 규칙상 조사 지시는 가정 아님(규칙-심판 인식 경계), 문서화로 대응 / subset 지적 2/5(before) → 1/5(after)
- **발견 문제**: 심판이 "조사 지시 추가"도 fidelity 감점 사유로 봄 — 재작성 규칙과 심판 루브릭 간 정의 불일치 (Phase 3에서 루브릭에 조사 지시 예외 명문화 검토)

## 2026-08-11 · R3 (fidelity [가정] 강제 + 프로필 차이 재검증)

- **완료**: 메타프롬프트에 "[가정] 없는 무단 구체화는 실패" 규칙 추가, subset 5건(g05·g12·g13·g18·g19) 재실행 (before 스냅샷: eval/results_phase1_snapshot.json)
- **실측 증거**: 전건 verdict=better 유지 / **프로필 차이 5/5 달성** (Phase 1의 g05 실패가 프로필 규칙 8 추가로 해소 — "A는 단계 나열 없이 목표·제약만, B는 체크리스트·번호 단계") / fidelity 수치는 4.0 불변 (심판이 구체화 존재 시 4점을 상한으로 두는 경향)
- **다음 인수 지점**: R3.1 예시 보강

## 2026-08-11 · R2.1 (재귀 가드 검증 + /pm 증거 + 지연 재측정)

- **완료**: PROMPTMAKER_ACTIVE 환경변수 재귀 가드 (pm_hook.py + pm_command.py), pm_command.py 실행 로깅, 재작성문 700자 상한
- **실측 증거**:
  - 재귀 가드 작동: hook.log `02:04:17 skip (recursion-guard)` → 외부 재작성 정상 완료 (`02:05:03 rewrote`)
  - /pm 재작성 경로 통과: pm_command.log `02:09:24 ok target=fable-5 raw='readme 파일 하나 써줘'` + 응답이 재작성 지침 구조(요구사항 질문 4종) 반영
  - 700자 상한 후 지연: 46.5~49.6s — **개선 없음** (생성 길이가 병목이 아님; 단 동시 평가 부하 중 측정으로 과대 가능)
- **발견 문제**: P1 지속 — 훅 지연 31~50s, timeout 60 내이나 여유 부족. 근본 대책은 claude -p 기동비(10.9s 실측) 제거 = 직접 API 호출 옵션 (Phase 3 백로그)
- **다음 인수 지점**: R3.1 fidelity 재검증 판독 → R4 심판

## 2026-08-11 · R2 (Claude Code 통합: /pm + 훅)

- **완료**: pm_hook.py(UserPromptSubmit, additionalContext 주입, 스킵 4종: 슬래시/#raw/단문/800자 초과, fail-open + runs/hook.log), pm.md(/pm 커맨드, ~/.claude/commands 설치 완료), pm_command.py(백엔드), install.sh
- **실측 증거**:
  - 훅 직접 호출: 유효 JSON 출력, additionalContext 357자, **42.9s 소요**
  - CLI 기동 오버헤드 실측: 사소한 프롬프트도 10.9s (고정비) → 재작성 생성이 ~32s
  - E2E(headless, scratch 프로젝트): 훅 31.3s에 재작성 주입, 응답이 재작성 지침(병목 특정·수치 측정)을 반영함 확인
  - /pm E2E(headless): 빈 디렉토리에서 재작성된 요구사항 질문 구조로 응답 확인
- **발견 문제**:
  - **P1 지연**: 훅 재작성 31~43s — 기본 훅 타임아웃(30s) 초과 위험. 대응: settings 스니펫에 timeout 60 명시. 근본 개선 백로그: claude -p 대신 직접 API 호출(기동 10.9s 제거), 훅용 축약 메타프롬프트
  - **P2 첫 프롬프트 모델 감지 한계**: transcript에 assistant 레코드가 없는 세션 첫 프롬프트에서는 --model 플래그를 감지할 수 없어 settings 기본 모델로 폴백 (2번째 프롬프트부터 정확). 실측으로 확인, 문서화로 대응
  - **P3 훅 재귀 (심각)**: 훅이 띄운 내부 claude -p가 같은 프로젝트 설정을 상속받아 훅을 재트리거. "800자 초과 스킵"이 우연히 막아줌 → PROMPTMAKER_ACTIVE 환경변수 가드 추가로 구조적 차단 (검증 진행 중)
- **다음 인수 지점**: 재귀 가드 검증 → /pm 로깅 증거 확보 → R3 fidelity 재평가 판독

## 2026-08-11 · R1 (모델 자동 감지 실측)

- **완료**: promptmaker/detect.py — 감지 우선순위: 명시 인자 → transcript 마지막 assistant model → 프로젝트 settings → 사용자 settings → 기본값. normalize_model이 "[1m]" 접미사·전체 ID(claude-haiku-4-5-20251001)를 프로필 스템으로 정규화
- **실측 증거** (scratch 프로젝트 + stdin 덤프 훅):
  - 훅 입력 JSON 필드: session_id, transcript_path, cwd, prompt_id, permission_mode, hook_event_name, prompt — **model 필드 없음 확정**
  - transcript JSONL의 assistant 레코드에 message.model="claude-haiku-4-5-20251001" 존재 확인
  - ~/.claude/settings.json에 "model": "claude-fable-5[1m]" 존재 확인
- **다음 인수 지점**: R2 통합 구현

## 2026-08-11 · R0 (루프 인프라 구축)

- **완료**: failbench PROMPT.md v2 방법론 검토 → PromptMaker에 이식. GATES.md(동결 기준) + LOOP_LOG.md(이 파일) + PROMPT.md(재요청 블록) 신설
- **다음 인수 지점**: R1 — 모델 자동 감지 실측 (G2-1)
