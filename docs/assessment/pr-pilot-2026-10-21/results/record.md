# PR 파일럿 v3 — 실행 결과

실행: 2026-10-25 · 엔진 `ecbf9f4`([engine-pin.md](../engine-pin.md)) · protocol `pr-pilot-2026-10-21-v3`

label과 엔진 커밋은 실행 전에 커밋했다(`e3b799f`). 엔진은 이 결과를 보고 고치지 않았다.

## 산출물

| 파일 | SHA-256 |
|---|---|
| [results.json](results.json) (`holdout run`) | `ecff757a14b5d78854b2d2621b64d97c387a98271582944706d8040b8360c728` |
| [labels.json](labels.json) (`holdout adjudicate`, 검토 3개) | `269f3b513b38599e744aba424f18fa2b70a09e7a60de9d6e372a9ca50da0f03b` |
| [metrics.json](metrics.json) (`holdout score`) | `0e280a1489c37737e26deb4fa907a386cbbcb4402740152422ff4e6f4070f4e3` |

## 원시 건수 (사람 label 기준)

표본: 저장소 3개, PR 30개, 규칙 단위 40개. 사람 검토자 1명.

### 규칙 단위 40개

| 엔진 판정 \ 사람 label | not-applicable | satisfied | violated | undecidable |
|---|---|---|---|---|
| not-applicable | 36 | 0 | 0 | 0 |
| undetermined(판단 보류) | 4 | 0 | 0 | 0 |
| 그 밖의 판정 | 0 | 0 | 0 | 0 |

- 엔진이 확정 판정을 낸 36개는 모두 사람 label과 같았다(확정 판정 오류 0/36).
- 사람 label에 violated가 없어 위반 정밀도·재현율은 분모가 0이다. **미탐은 측정하지 못했다.**
- `verified_coverage` 0/40은 확정 판정 중 내용 검증까지 마친 것이 없다는 뜻이다. not-applicable은 검증 완료로 세지 않는다.

### PR 단위 30개

| 엔진 gate \ 사람 label | pass | warn | fail |
|---|---|---|---|
| pass | 25 | 1 | 0 |
| warn | 3 | 1 | 0 |
| fail | 0 | 0 | 0 |

- 오차단(`false_block`, 사람 pass·warn인 PR을 fail로 막음): 0/30 (Wilson 95% 0–0.114)
- 미차단(`missed_block`): 사람 fail이 0건이라 분모 0, 측정 불가
- 보류(엔진 warn): 4/30. 그중 사람도 warn인 것 1건, 사람 pass인 것 3건
- 엔진 pass·사람 warn: 1건

## 사례별 불일치 원인

| PR | 엔진 | 사람 | 엔진 근거(규칙 판정의 evidence) | 원인 분류 |
|---|---|---|---|---|
| langflow#14234 | warn | pass | `api-route-content`: "only literal router prefixes are supported", typed trigger unknown | 지원 범위 밖 → 보류. router prefix가 리터럴이 아니어서 경로 변화가 없다는 것도 확정하지 못함 |
| litellm#41583 | warn | pass | `env-sample-content`: "No static new environment keys could be established", typed trigger unknown | 감시 경로(`litellm/proxy/**`)의 큰 파일 변경에서 새 키 부재를 정적으로 증명하지 못해 보류 |
| litellm#40807 | warn | pass | `env-sample-content`: 위와 같음(감시 경로 파일 4개) | 같음 |
| langflow#14244 | warn | warn | `api-route-content`: "unresolved function decorators are unsupported" | gate는 같지만 **이유가 다르다.** 엔진은 decorator 해석 불가로 보류했고, 사람은 `agentic_experience` 기본값 변경의 문서 안내를 의심했다 |
| litellm#41462 | pass | warn | 두 규칙 모두 감시 경로 밖 → not-applicable | 규칙 범위 밖. 사람의 근거(기존 키 `LITELLM_OTEL_BAGGAGE_METADATA_KEYS`의 사용 범위 확장, 사용자 문서 확인 불가)는 현재 정책·엔진이 다루는 변경이 아니다 |

warn 4건은 모두 엔진의 판단 보류(undetermined)에서 나왔다. 확정 위반(violated)으로 warn·fail이 된 사례는 없다.

## llm-proxy 검토

- Opus(`opus-5-5`)와 Codex의 일치도: Cohen's κ 0.9157(70개 항목). 서로 다른 3개는 모두 PR 단위(Codex warn, Opus pass)로 미해결로 남겼다.
- llm-proxy 지표는 사람 검토를 대신하지 않는다. 결정은 사람 label 기준으로 적는다.

## 해석의 한계

- 30개 PR, 3개 저장소, 사람 1명이다. Wilson 구간이 넓고 다른 저장소로 일반화하지 않는다.
- 사람 label에 violated·fail이 없어 이 파일럿은 **오탐과 보류 비율만** 보여 준다. 위반을 잡는 능력은 이 자료로 말할 수 없다.
- 2개 항목은 사람이 label 전에 Opus 의견을 열람했다(두 항목 모두 not-applicable로 엔진 판정과 같음).
- 이 사례로 엔진을 고친 경우 회귀 테스트로만 옮기고, 같은 사례로 정확도를 다시 주장하지 않는다.
