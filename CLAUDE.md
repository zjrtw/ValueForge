# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 요약

ValueForge — 한국 주식 가치 스크리너 (KOSPI·KOSDAQ).  
상세 문서: [docs/](docs/) 디렉토리 참조. 개발 워크플로우: [docs/CLAUDE.md](docs/CLAUDE.md).

## 빠른 명령어

```bash
# 환경 설정
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# 파이프라인 실행 (테스트용 소규모)
MAX_TICKERS=50 python -m src.pipeline.runner

# 대시보드 로컬 실행
streamlit run src/ui/app.py

# 테스트 / 린트
pytest tests/ -v
ruff check src/ && mypy src/ --ignore-missing-imports
```

## 핵심 제약사항

- 모든 SQLite 접근은 `src/db/repository.py` 경유 (직접 SQL 금지)
- Streamlit Cloud에서 무거운 연산 절대 금지 — 사전 연산 데이터만 렌더링
- 스코어링 가중치·필터 임계값은 `config/screening_params.yaml`에서 관리 (코드 하드코딩 금지)
- 테스트에서 실제 API 호출 금지 — `pytest-mock` + `moto` 사용

## 작업 관리 규칙

- `docs/TASKS.md`의 작업 항목을 완료하면 해당 행의 제일 왼쪽 `Done` 체크박스를 `☐`에서 `☑`로 변경한다.

---

# 커뮤니케이션 규칙

* 사용자와의 모든 소통은 **한국어**로 한다.
* 생성하는 모든 문서 파일은 **한국어**로 작성한다.
  * PRD, 태스크, 아키텍처, 기술 명세, 마크다운 파일 포함

# 출력 규칙

* 요청 처리 중 장황한 진행 메시지를 출력하지 않는다.
* 중간 출력, 스트리밍 로그, 불필요한 설명, 단계별 생성 메시지를 피한다.
* 토큰 소비를 줄이기 위해 출력을 최소화한다.
* 가능하면 항상 조용히 처리한다.

# 최종 응답 규칙

* 각 작업 완료 후 **간결한 한국어 요약**만 제공한다:
  * 완료된 내용
  * 생성·수정된 파일
  * 핵심 구현 결과
* 요약은 짧고 간결하게 유지한다.
* 명시적으로 요청받지 않는 한 중복 설명을 피한다.
