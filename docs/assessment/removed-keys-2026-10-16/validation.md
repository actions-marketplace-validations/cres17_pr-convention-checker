# 삭제 키 검사 구현·로컬 검증 (2026-10-16)

엔진·CLI·CI 출력·MCP·데스크톱의 두 단계 구현을 모두 완료했다. 사용 안내는 [삭제된 환경 변수 키 확인](../../removed-environment-keys.md)을 따른다.

- 기본 삭제 키 검사, 키 단위 예외, 전체 끄기 및 정책 약화 비교.
- 설정·배포 패턴 5종과 이름만 발견·전체 검색 부족을 `advisories`로 출력.
- 경고만 있으면 warn / review. 독립적인 실패는 유지.
- CLI·MCP·데스크톱의 같은 경고 문구, JSON·Markdown·HTML 출력.
- 관측을 입력 스냅샷·해시에 포함하고 evidence bundle 재실행 확인.
- 데스크톱의 확인창·취소·저장·재검사·정책 변경 충돌 방지.

| 검증 | 확인 결과 |
|---|---|
| Python 전체 회귀 | 2,141 통과, 6 생략 |
| React | 129 통과 (12개 파일) |
| TypeScript·화면 빌드 | 성공 |
| Ruff E9/F | 통과 |
| README·사용 안내·CLAUDE.md 문서 검사 | 경고 0 |
| 별도 폴더의 wheel 설치본 | 실제 `site-packages`에서 실행 |
| 설치본 동작 대조 | 구성 사용·이름만 발견·실제 코드 사용·사용 없음·키 예외·전체 끄기, CLI 종료 코드 확인 |
| 설치본 표면 대조 | CLI·MCP·데스크톱의 advisory 본문 동일 |
| 설치본 화면 리소스 | 빌드한 UI와 새 설정 문구 포함 |
| 실제 Qt 화면 | warn 및 두 설정 버튼 표시, [화면 캡처](desktop-warning.png) |
| 확인창 동작 | Qt 브리지 검사에서 기본 취소·취소 시 무변경·승인 시 저장·재검사 확인 |
| 신뢰 정책 약화 | 검사 끄기·키 예외 모두 review / 병합 근거 none |

세부 결과: [설치본 통제](installed-controls.json), [Qt 화면 확인](desktop-qa.json).

변경 전에는 재사용하던 개발 환경에서 2,069개가 통과하고 별도 프로세스 분석 4개가 실패했다. 전용 검증 환경에서 의존 경로를 올바르게 제공하자 해당 실패가 해소됐다. 이는 환경 수정이며 기능의 품질 향상 수치로 계산하지 않았다.

이 검증은 작성한 통제 사례와 기존 회귀 검사다. 실제 PR 정확도, 독립 holdout 성능, 운영 효과를 측정하지 않았다. 원격 CI, Windows 실행 파일, macOS 배포용 설치 파일 및 새 릴리스 발행은 실행하지 않았다. 기존 전체 실행 자원 제한을 초과하면 기존 중단 규칙을 따르며, 삭제 키 검색 자체의 한도 초과는 경고다.

재현 시 Python 개발·데스크톱 의존성을 준비한 뒤 저장소에서 `python -m pytest -q`, `ruff check drift_gate/ --select=E9,F`, `desktop-ui`에서 `npm test` 및 `npm run build`를 실행한다. 패키지 경계는 wheel을 별도 환경에 설치하고 저장소 밖에서 `python -I -m drift_gate check --base HEAD --json`으로 확인한다.
