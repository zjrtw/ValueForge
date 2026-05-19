# AGENTS.md

이 파일은 Codex가 이 저장소에서 작업할 때 따를 지침입니다.

## 응답 규칙

- 모든 사용자 응답은 한국어로 작성한다.
- 친절하고 초보자가 이해하기 쉬운 표현을 사용한다.
- 사용자가 명시적으로 요청한 범위만 답한다.
- 불필요한 중간 로그나 장황한 설명은 출력하지 않는다.
- 설치, 설정, 문제 해결, 디버깅에서 오류 확인이 필요한 경우에는 한 번에 정확히 한 단계만 안내하고 사용자의 결과를 기다린다.
- 사용자가 "프롬프트 작성"을 요청하면 답변은 코드 블록 안에 작성한다.

## 프로젝트 개요

ValueForge는 한국 주식 가치 스크리너입니다. KOSPI, KOSDAQ 종목을 대상으로 pykrx, DART OpenAPI, SQLite, Cloudflare R2, Streamlit을 사용합니다.

주요 문서는 `docs/` 아래에 있습니다.

- `docs/PRD.md`: 제품 요구사항
- `docs/ARCHITECTURE.md`: 아키텍처
- `docs/DATABASE.md`: SQLite 스키마
- `docs/SCREENING.md`: 스크리닝 알고리즘
- `docs/STORAGE.md`: Cloudflare R2 저장소 설계
- `docs/STREAMLIT.md`: Streamlit 대시보드 설계
- `docs/DEPLOYMENT.md`: 배포 전략
- `docs/TASKS.md`: 구현 작업 목록

## 개발 명령어

```bash
python -m venv .venv
pip install -r requirements-dev.txt
MAX_TICKERS=50 python -m src.pipeline.runner
streamlit run src/ui/app.py
pytest tests/ -v
ruff check src/
mypy src/ --ignore-missing-imports
```

Windows PowerShell에서는 가상환경 활성화에 다음 명령을 사용한다.

```powershell
.\.venv\Scripts\Activate.ps1
```

## 코드 작성 규칙

- 기존 파일 구조와 스타일을 우선 따른다.
- 문서 파일은 UTF-8로 읽고 쓴다. 특히 `docs/TASKS.md`는 BOM 없는 UTF-8이므로 PowerShell에서 기본 인코딩으로 읽으면 깨져 보일 수 있다.
- Python 3.11 이상을 기준으로 작성한다.
- 설정값, 필터 기준, 가중치, 임계값은 가능한 한 `config/screening_params.yaml`에서 관리한다.
- SQLite 접근은 `src/db/repository.py`를 경유하도록 구현한다.
- Streamlit UI에서는 무거운 계산을 직접 수행하지 않고 사전 계산된 데이터를 조회한다.
- 테스트에서는 실제 외부 API를 호출하지 않는다. `pytest-mock`, `moto` 같은 목 도구를 사용한다.

## 작업 관리 규칙

- 작업을 완료하면 `docs/TASKS.md`에서 해당 항목의 `Done` 체크박스를 `[x]`로 변경한다.
- 관련 작업이 불명확하면 임의로 체크하지 않는다.
- 사용자가 요청하지 않은 리팩터링이나 문서 대량 수정은 피한다.

## 검증 기준

변경 범위에 따라 가능한 검증을 수행한다.

- 일반 코드 변경: `pytest tests/ -v`
- 수집기 변경: `pytest tests/test_collectors/ -v`
- DB 변경: `pytest tests/test_db/ -v`
- 스크리닝 변경: `pytest tests/test_screening/ -v`
- 점수 계산 변경: `pytest tests/test_scoring/ -v`
- 정적 검사: `ruff check src/`, `mypy src/ --ignore-missing-imports`

검증을 실행하지 못한 경우에는 최종 답변에 실행하지 못한 이유를 짧게 적는다.
