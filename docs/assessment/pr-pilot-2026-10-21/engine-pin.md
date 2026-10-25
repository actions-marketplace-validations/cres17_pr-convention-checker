# PR 파일럿 v3 — 엔진 고정 기록

작성: 2026-10-25 · `holdout run` 실행 전에 커밋한다([protocol-v3](protocol-v3.md) 4번).

## 고정한 엔진

| 항목 | 값 |
|---|---|
| 엔진 커밋 | `ecbf9f4e2c0e0b5a215e1a45154894425997d7a1` (`main`) |
| 엔진 source_sha256 (`producer_identity`) | `8ca61b2c5c41cd711dc59798f4fdc30687872ca8c7359727466260941fb72e33` |
| 설치 방법 | 해당 커밋의 별도 worktree를 Python 3.11.17 가상환경에 일반 설치(editable 아님), `python -I`로 실행 |
| 의존 패키지 | PyYAML 6.0.3, tree-sitter 0.26.0, tree-sitter-language-pack 1.20.0, zstandard 0.25.0 |

이 커밋 이후의 엔진 변경은 이 파일럿 결과에 쓰지 않는다. 파일럿 사례로 엔진을 고치지 않는다.

## 실행 전 입력 재생성과 대조

사례 파일은 저장소에 넣지 않으므로 같은 조건으로 다시 만들어 [manifest-v3](manifest-v3.md)와 대조했다.

- 세 저장소를 대상 브랜치만 `--shallow-since=2026-01-01`로 2026-10-25에 복제했다
  (복제 시점 head: open-webui `af6c382d3a88`, langflow `aeb10d96bb2e`, litellm `dddbaa803d6e`).
  표본 PR은 2026-10-15 이전 커밋이라 head가 달라도 같은 사례가 나온다.
- 위 엔진으로 `collect.py cases` → `holdout split`(seed 20261021, fraction 0.999) → `freeze`(protocol `pr-pilot-2026-10-21-v3`) → `packet`을 실행했다.

| 파일 | 재생성 SHA-256 | manifest-v3와 일치 |
|---|---|---|
| candidates.json | `ea5b9a2e1b9e62f4e9acdfe1f2a042c284151cbb1ba8a669359a01e0142aeeea` | 일치 |
| holdout.json | `f80e227a29db22129eec38c1359cc56ca6542ede1c23f3c5db1101e88a0a27ac` | 일치 |
| frozen.json | `0cbc5311198da481736866b3e442d31e8c6876ab08d34a4b330f15d499f9143a` | 일치 |
| packet.json | `a86ca41b993b522b4f3504017d43430d6462210ecc9a0c5ef8a3e8d20fc111f9` | 일치 |

## 실행 전에 고정한 label

| 파일 | 검토자 | 종류 | 항목 | SHA-256 |
|---|---|---|---|---|
| [labels/labels-junseok.jsonl](labels/labels-junseok.jsonl) | junseok | human | 70 | `9688c613c7375d4a36466d54d8e1ee9226ae3da85f845568ddfbbd0813e2cac7` |
| [labels/labels-opus-5-5.jsonl](labels/labels-opus-5-5.jsonl) | opus-5-5 | llm-proxy | 70 | `d449ff51d6c7fcd1e74f99834150016fac9374818936ab34755c599c93f15416` |
| [labels/labels-codex.jsonl](labels/labels-codex.jsonl) | codex | llm-proxy | 70 | `054103fd1f94c15d645f79fc1e17361f4b6d14fa7ce4b9ec701538e4f156c628` |

사람 label에 대해 알려진 사항:

- 사람 검토자 1명이다. 사람 label끼리의 일치도는 낼 수 없다.
- 두 항목(`open-webui/open-webui#30080::env-sample-content`, `open-webui/open-webui#27359::env-sample-content`)은
  본인 label을 고르기 전에 Opus 의견을 열람했다(`peeked_opus: true`). 두 항목 모두 label은 Opus와 같은 not-applicable이다.
- 근거(`rationale`)는 warn 2건과 Codex와 판단이 다른 1건(`BerriAI/litellm#40807::pr-action`)에만 적었다.
- violated·fail label이 0건이라 미탐(`confirmed_violation_recall`, `missed_block`)은 측정할 수 없다.

Codex label은 label 도구에 직접 입력된 의견을 도구의 내보내기 형식(`reviewer_id: codex`, `llm-proxy`)으로 옮긴 것이다.
llm-proxy label은 독립 사람 검토를 대신하지 않는다.
