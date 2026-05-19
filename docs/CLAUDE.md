# Claude 개발 워크플로우 가이드

> Claude Code가 이 저장소에서 작업할 때 참조하는 프로젝트별 가이드

## 핵심 아키텍처 패턴

### Repository 패턴 준수

모든 SQLite 읽기/쓰기는 반드시 `src/db/repository.py`를 경유한다. 파이프라인·스코어링·스크리닝 코드에서 SQL을 직접 작성하지 않는다.

```python
# ✅ 올바른 방법
repo = DatabaseRepository(db_path)
repo.upsert_prices(prices_df, run_date)

# ❌ 잘못된 방법 — pipeline/runner.py에서 직접 SQL 작성 금지
conn.execute("INSERT INTO prices ...")
```

### 설정 하드코딩 금지

스코어링 가중치, 필터 임계값 등 조정 가능한 파라미터는 `config/screening_params.yaml`에서 관리한다.

```python
# ✅ 올바른 방법
from src.utils.config import screening_params
WEIGHTS = screening_params.stage2_weights

# ❌ 잘못된 방법
WEIGHTS = {'value': 0.30, 'quality': 0.25, ...}  # 코드 내 하드코딩 금지
```

### 정규화 일관성

모든 점수 산출은 `src/scoring/normalizer.py`의 `percentile_rank_score()`를 사용한다. 절대 기준 정규화(min-max 등)를 임의로 추가하지 않는다.

### Streamlit에서 연산 금지

Streamlit 페이지(`src/ui/`)에서 점수 계산, 데이터 필터링, pandas 변환 등 무거운 연산을 수행하지 않는다. 대시보드는 사전 연산된 데이터를 조회·렌더링만 한다.

---

## 파일별 역할 요약

| 파일 | 역할 |
|---|---|
| `src/pipeline/runner.py` | 메인 오케스트레이터. 모든 단계를 순서대로 호출. |
| `src/db/repository.py` | 유일한 DB 접근 레이어. |
| `src/screening/stage*.py` | 각 스크리닝 단계. 입력/출력이 DataFrame. |
| `src/scoring/*.py` | 개별 점수 차원. 독립적으로 테스트 가능. |
| `src/storage/uploader.py` | R2 업로드 로직. 업로드 순서 엄수 필요. |
| `src/ui/data_loader.py` | Streamlit 데이터 캐싱 레이어. |
| `config/screening_params.yaml` | 모든 조정 가능 파라미터. |

---

## 테스트 작성 원칙

- 수집기 테스트: 실제 API 호출 금지 → `pytest-mock`으로 모킹
- Repository 테스트: 인메모리 SQLite (`":memory:"`) 사용
- R2 업로드·다운로드 테스트: `moto[s3]`로 AWS S3 API 모킹
- 스크리닝 테스트: `tests/conftest.py`의 합성 DataFrame 픽스처 사용

---

## 자주 쓰는 명령어

```bash
# 소규모 테스트 실행 (50개 종목만)
MAX_TICKERS=50 python -m src.pipeline.runner --date 2025-01-15

# 특정 모듈 테스트
pytest tests/test_screening/ -v
pytest -k "test_stage3"

# 린트 + 타입 체크
ruff check src/ && mypy src/ --ignore-missing-imports

# Streamlit 로컬 실행
streamlit run src/ui/app.py
```

---

## 가치 함정 자동 실격 규칙 (변경 시 주의)

`src/screening/stage3_trap_detector.py`의 `is_value_trap()` 함수는 다음 규칙을 사용한다:

- **CRITICAL 플래그 1개 이상** → 완전 제외
- **HIGH 플래그 2개 이상** → 완전 제외
- 그 외: 플래그 수에 따른 점수 패널티 (MEDIUM -2점, HIGH -5점)

이 규칙 변경 시 `tests/test_screening/test_stage3_traps.py`의 자동 실격 테스트 케이스를 함께 업데이트해야 한다.

---

## 한국 시장 특수 사항

- 장 시간: 09:00-15:30 KST (UTC+9)
- pykrx 종목 코드: 6자리 숫자 문자열 (예: `'005930'`)
- DART 재무 데이터: 분기 공시 지연이 있으므로 `fiscal_year`를 기준으로 가장 최근 연간 데이터 우선 사용
- 지주회사(`지주회사` 업종)는 LOW 리스크 플래그 자동 부여

---

## 관련 문서

- 전체 아키텍처: [ARCHITECTURE.md](ARCHITECTURE.md)
- 스크리닝 알고리즘: [SCREENING.md](SCREENING.md)
- 데이터베이스 스키마: [DATABASE.md](DATABASE.md)
- R2 스토리지: [STORAGE.md](STORAGE.md)
- 구현 태스크: [TASKS.md](TASKS.md)
