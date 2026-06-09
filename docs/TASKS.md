# 파이어맵 테스트

> **ValueForge** | 마일스톤 기반 구현 계획 (MVP 우선, 반복 개발 최적화)

## 작업 규칙

작업이 완료되면 해당 항목의 제일 왼쪽 `Done` 체크박스를 `[x]`로 변경한다.

## 목차

- [파이어맵 테스트](#파이어맵-테스트)
  - [작업 규칙](#작업-규칙)
  - [목차](#목차)
  - [전체 일정 요약](#전체-일정-요약)
  - [Milestone 0: 프로젝트 초기화(1일차)](#milestone-0-프로젝트-초기화1일차)
  - [Milestone 1: 데이터 수집 (2-4일차)](#milestone-1-데이터-수집-2-4일차)
  - [Milestone 2: 데이터베이스 레이어 (4-5일차)](#milestone-2-데이터베이스-레이어-4-5일차)
  - [Milestone 3: 스크리닝 파이프라인 (6-9일차)](#milestone-3-스크리닝-파이프라인-6-9일차)
  - [Milestone 4: 파이프라인 오케스트레이션 \& R2 (10-11일차)](#milestone-4-파이프라인-오케스트레이션--r2-10-11일차)
  - [Milestone 5: Streamlit 대시보드 (12-15일차)](#milestone-5-streamlit-대시보드-12-15일차)
  - [Milestone 6: 자동화 \& 배포 (16-17일차)](#milestone-6-자동화--배포-16-17일차)
  - [Milestone 7: KRX 인증 방식 전환 (pykrx → 공식 Open API)](#milestone-7-krx-인증-방식-전환-pykrx--공식-open-api)
  - [Milestone 7-1: V1.1 투자 판단 신뢰도 향상](#milestone-71-v11-투자-판단-신뢰도-향상완료)
  - [Milestone 8: 대시보드 UX 개선 (초보자 친화)](#milestone-8-대시보드-ux-개선-초보자-친화)
  - [구현 우선순위 원칙](#구현-우선순위-원칙)
  - [관련 문서](#관련-문서)

---

## 전체 일정 요약

| 마일스톤 | 기간 | 예상 시간 | 누적 시간 | 상태 |
|---|---|---|---|---|
| M0: 프로젝트 초기화 | 1일차 | 4.5h | 4.5h | ✅ 완료 |
| M1: 데이터 수집 | 2-4일차 | 25h | 29.5h | ✅ 완료 |
| M2: 데이터베이스 레이어 | 4-5일차 | 19h | 48.5h | ✅ 완료 |
| M3: 스크리닝 파이프라인 | 6-9일차 | 32h | 80.5h | ✅ 완료 |
| M4: 파이프라인 오케스트레이션 & R2 | 10-11일차 | 20h | 100.5h | ✅ 완료 |
| M5: Streamlit 대시보드 | 12-15일차 | 23h | 123.5h | ✅ 완료 |
| M6: 자동화 & 배포 | 16-17일차 | 11h | 134.5h | ✅ 완료 |
| M7: KRX 인증 방식 전환 | 18-20일차 | 15h | 149.5h | 진행중 |
| **M7-1: V1.1 투자 판단 신뢰도 향상** | 추가 | 18.5h | 168h | **✅ 완료** |
| M8: 대시보드 UX 개선 (초보자 친화) | 21-22일차 | 12h | 180h | 예정 |

**총 MVP 예상 시간: 약 134.5시간 (1인 개발자 기준 3-4주)**  
**M7 포함 총 시간: 약 149.5시간**  
**M7-1 포함 총 시간: 약 168시간 (V1.1 완성)**  
**M8 포함 총 시간: 약 180시간 (완전 완성)**
| 마일스톤                           | 기간      | 예상 시간 | 누적 시간 |
| ---------------------------------- | --------- | --------- | --------- |
| M0: 프로젝트 초기화                | 1일차     | 4.5h      | 4.5h      |
| M1: 데이터 수집                    | 2-4일차   | 25h       | 29.5h     |
| M2: 데이터베이스 레이어            | 4-5일차   | 19h       | 48.5h     |
| M3: 스크리닝 파이프라인            | 6-9일차   | 32h       | 80.5h     |
| M4: 파이프라인 오케스트레이션 & R2 | 10-11일차 | 20h       | 100.5h    |
| M5: Streamlit 대시보드             | 12-15일차 | 23h       | 123.5h    |
| M6: 자동화 & 배포                  | 16-17일차 | 11h       | 134.5h    |
| M7: KRX 인증 방식 전환             | 18-20일차 | 15h       | 149.5h    |
| M8: V2 AI 정성 분석 파이프라인     | 21-24일차 | 20h       | 169.5h    |

**총 MVP 예상 시간: 약 134시간 (1인 개발자 기준 3-4주, 하루 5-6시간)**  
**M7 포함 총 시간: 약 149.5시간**  
**M8 포함 총 시간: 약 169.5시간**

---

## Milestone 0: 프로젝트 초기화(1일차)

| Done | ID   | 테스트           | 설명                                                                                  | 난이도 | 시간 |
| ---- | ---- | ---------------- | ------------------------------------------------------------------------------------- | ------ | ---- |
| ☑    | M0-1 | 저장소 초기화    | 폴더 구조 생성, `pyproject.toml`, `.gitignore`, `requirements.txt` 작성               | 쉬움   | 1h   |
| ☑    | M0-2 | DART API 키 발급 | opendart.fss.or.kr 등록, API 연결 테스트                                              | 쉬움   | 30m  |
| ☑    | M0-3 | R2 버킷 설정     | Cloudflare R2 버킷 생성, API 토큰 2개 발급 (읽기+쓰기 / 읽기 전용), boto3 연결 테스트 | 쉬움   | 1h   |
| ☑    | M0-4 | 로깅 구현        | `structlog` 기반 JSON 포맷 로거 (`src/utils/logger.py`)                               | 쉬움   | 1h   |
| ☑    | M0-5 | 설정 클래스 구현 | `pydantic-settings` 기반 `Settings` 클래스, env var + `.env` 파일 읽기                | 쉬움   | 1h   |

**체크포인트**: `python -c "from src.utils.config import settings; print(settings.R2_BUCKET_NAME)"` 정상 출력.

---

## Milestone 1: 데이터 수집 (2-4일차)

| Done | ID   | 테스트                  | 설명                                                                      | 의존성      | 난이도 | 시간 | 배정   | 이유                                               |
| ---- | ---- | ----------------------- | ------------------------------------------------------------------------- | ----------- | ------ | ---- | ------ | -------------------------------------------------- |
| ☑    | M1-1 | KRX 종목 코드 수집      | `pykrx.stock.get_market_ticker_list()`로 KOSPI·KOSDAQ 전체 종목 코드 수집 | M0          | 쉬움   | 2h   | Claude | 프로젝트 구조·설정(settings, get_logger) 연동 필요 |
| ☑    | M1-2 | KRX 주가 데이터 수집    | 종목별 종가, 거래대금, 시가총액, PER, PBR, 배당수익률 수집                | M1-1        | 보통   | 4h   | Codex  | M1-1 완성 후 독립적인 반복 수집 로직               |
| ☑    | M1-3 | DART 재무 데이터 수집   | `open-dart-reader`로 손익계산서·재무상태표·현금흐름표 (3개년)             | M0          | 보통   | 6h   | Codex  | M1-2와 병렬 가능, 단순 API 호출 패턴               |
| ☑    | M1-4 | 20일 평균 거래대금 산출 | 30일 OHLCV 조회 후 평균 거래대금 계산                                     | M1-1        | 쉬움   | 2h   | Codex  | M1-2에 붙는 순수 계산 로직                         |
| ☑    | M1-5 | 1년 주가 이력 수집      | 모멘텀 계산용 252일 OHLCV 수집                                            | M1-1        | 쉬움   | 2h   | Codex  | M1-2와 거의 동일한 패턴                            |
| ☑    | M1-6 | yfinance 백업 수집기    | pykrx 데이터 누락 시 yfinance 대체 수집                                   | M1-2        | 보통   | 3h   | Codex  | M1-2 구조 파악 후 대체 구현                        |
| ☑    | M1-7 | 레이트 리밋 처리        | pykrx 호출 간 지연, DART 일 10,000건 한도 준수                            | M1-2, M1-3  | 쉬움   | 2h   | Claude | M1-2·M1-3 통합 후 전체 흐름 이해 필요              |
| ☑    | M1-8 | 수집기 단위 테스트      | 모킹된 API 응답으로 테스트 (실제 API 호출 불가)                           | M1-1 ~ M1-6 | 보통   | 4h   | Claude | pytest-mock + 프로젝트 테스트 컨벤션 준수 필요     |

**체크포인트**: `MAX_TICKERS=50 python -m src.pipeline.runner --date today` 후 SQLite에 50개 종목 데이터 확인.

---

## Milestone 2: 데이터베이스 레이어 (4-5일차)

| Done | ID   | 테스트              | 설명                                                           | 의존성      | 난이도 | 시간 |
| ---- | ---- | ------------------- | -------------------------------------------------------------- | ----------- | ------ | ---- |
| ☑    | M2-1 | 스키마 구현         | `src/db/schema.py`: 전체 CREATE TABLE + 인덱스                 | M0          | 쉬움   | 2h   |
| ☑    | M2-2 | 쓰기 메서드 구현    | `upsert_stocks`, `upsert_prices`, `upsert_fundamentals`        | M2-1        | 보통   | 4h   |
| ☑    | M2-3 | 읽기 메서드 구현    | `get_screening_dataset()` 및 Stage 1 입력용 병합 뷰 반환       | M2-2        | 보통   | 3h   |
| ☑    | M2-4 | 실행 기록 메서드    | `record_run_start`, `record_run_success`, `record_run_failure` | M2-1        | 쉬움   | 2h   |
| ☑    | M2-5 | 점수·순위 쓰기      | `upsert_scores`, `upsert_rankings`, `upsert_risk_flags`        | M2-2        | 보통   | 3h   |
| ☑    | M2-6 | 스키마 마이그레이션 | 버전 추적, 순방향 마이그레이션 지원                            | M2-1        | 보통   | 2h   |
| ☑    | M2-7 | DB 레이어 테스트    | 인메모리 SQLite(`":memory:"`)로 Repository 테스트              | M2-1 ~ M2-5 | 보통   | 3h   |

**체크포인트**: `pytest tests/test_db/ -v` 전체 통과.

---

## Milestone 3: 스크리닝 파이프라인 (6-9일차)

| Done | ID    | 테스트               | 설명                                                         | 의존성       | 난이도 | 시간 |
| ---- | ----- | -------------------- | ------------------------------------------------------------ | ------------ | ------ | ---- |
| ☑    | M3-1  | 정규화 유틸리티      | `percentile_rank_score()` 함수 (`src/scoring/normalizer.py`) | M0           | 쉬움   | 1h   |
| ☑    | M3-2  | Stage 1 필터         | 시가총액, 거래대금, PER, PBR, 상장 기간 필터                 | M2-3         | 쉬움   | 2h   |
| ☑    | M3-3  | 가치 스코어러        | PER, PBR, EV/EBITDA, 배당수익률 스코어링                     | M3-1         | 쉬움   | 3h   |
| ☑    | M3-4  | 퀄리티 스코어러      | ROE, ROA, 영업이익률, ROE 3년 안정성                         | M3-1         | 보통   | 3h   |
| ☑    | M3-5  | 안전성 스코어러      | 부채비율, 유동비율, 이자보상배율                             | M3-1         | 쉬움   | 2h   |
| ☑    | M3-6  | 성장성 스코어러      | 매출·영업이익·EPS·FCF YoY 성장률                             | M3-1         | 보통   | 3h   |
| ☑    | M3-7  | 모멘텀 스코어러      | 6개월·3개월·1개월 시장 대비 수익률                           | M1-5         | 보통   | 3h   |
| ☑    | M3-8  | Stage 2 스코어링     | 5개 스코어러 복합 점수 산출                                  | M3-3 ~ M3-7  | 쉬움   | 2h   |
| ☑    | M3-9  | Stage 3 함정 감지기  | 모든 플래그 유형 구현, 자동 탈락 규칙                        | M2-3         | 보통   | 5h   |
| ☑    | M3-10 | Stage 4 랭커         | 리스크 페널티 적용, 최종 정렬                                | M3-8, M3-9   | 쉬움   | 2h   |
| ☑    | M3-11 | 스크리닝 단위 테스트 | 합성 데이터로 각 Stage 테스트                                | M3-2 ~ M3-10 | 보통   | 6h   |

**체크포인트**: `pytest tests/test_screening/ -v` 전체 통과. Stage 1에서 전체 종목의 20-30%가 통과하는지 확인.

---

## Milestone 4: 파이프라인 오케스트레이션 & R2 (10-11일차)

| Done | ID   | 테스트                     | 설명                                                    | 의존성      | 난이도 | 시간 |
| ---- | ---- | -------------------------- | ------------------------------------------------------- | ----------- | ------ | ---- |
| ☑    | M4-1 | R2 클라이언트 팩토리       | `src/storage/r2_client.py`: boto3 클라이언트 생성       | M0          | 쉬움   | 1h   |
| ☑    | M4-2 | 업로드 구현                | `upload_latest`, `upload_backup`, `cleanup_old_backups` | M4-1        | 보통   | 3h   |
| ☑    | M4-3 | 다운로더 구현              | `download_latest_db`, `get_metadata`                    | M4-1        | 쉬움   | 2h   |
| ☑    | M4-4 | 메타데이터 작성기          | `latest_metadata.json` 생성 및 R2 업로드                | M4-2        | 쉬움   | 1h   |
| ☑    | M4-5 | 파이프라인 러너            | `src/pipeline/runner.py`: 전체 단계 오케스트레이션      | M1~M3, M4-2 | 보통   | 4h   |
| ☑    | M4-6 | 일시적 오류 처리           | `with_retry` 데코레이터, 개별 종목 graceful skip        | M4-5        | 보통   | 3h   |
| ☑    | M4-7 | 한국장 캘린더 체크         | `is_trading_day()`, 휴장일 자동 skip                    | M0          | 쉬움   | 2h   |
| ☑    | M4-8 | 실데이터 End-to-End 테스트 | 실제 데이터로 전체 파이프라인 로컬 실행                 | M4-5        | 어려움 | 4h   |

**체크포인트**: 실제 데이터로 파이프라인 실행 후 R2에 `latest.db`, `latest_metadata.json`, `history/YYYY-MM-DD.db` 3개 파일 생성 확인.

---

## Milestone 5: Streamlit 대시보드 (12-15일차)

| Done | ID   | 테스트               | 설명                                               | 의존성      | 난이도 | 시간 |
| ---- | ---- | -------------------- | -------------------------------------------------- | ----------- | ------ | ---- |
| ☑    | M5-1 | 데이터 로더          | R2 다운로드 + `cache_resource` + SQLite 쿼리 함수  | M4-3        | 보통   | 3h   |
| ☑    | M5-2 | 랭킹 페이지          | 메인 테이블, 사이드바 필터, 점수 지표              | M5-1        | 보통   | 6h   |
| ☑    | M5-3 | 종목 상세 페이지     | 점수 레이더, 리스크 플래그, 재무 테이블, 주가 차트 | M5-1        | 보통   | 6h   |
| ☑    | M5-4 | About 페이지         | 방법론 설명, 데이터 소스 안내                      | 없음        | 쉬움   | 2h   |
| ☑    | M5-5 | 레이더 차트 컴포넌트 | Plotly 극좌표 재사용 컴포넌트                      | M5-2        | 쉬움   | 2h   |
| ☑    | M5-6 | CSV 내보내기         | UTF-8 BOM 다운로드 버튼 (Excel 한글 호환)          | M5-2        | 쉬움   | 1h   |
| ☑    | M5-7 | 데이터 최신성 배너   | `run_date` 표시, 2일 이상 오래된 경우 경고         | M5-1        | 쉬움   | 1h   |
| ☑    | M5-8 | Streamlit Cloud 배포 | GitHub 연동, Streamlit Cloud 앱 생성, Secrets 입력 | M5-1 ~ M5-7 | 쉬움   | 2h   |

**체크포인트**: Streamlit Cloud URL에서 랭킹 페이지와 종목 상세 페이지가 정상 동작하는지 확인.

---

## Milestone 6: 자동화 & 배포 (16-17일차)

| Done | ID   | 테스트                    | 설명                                    | 의존성 | 난이도 | 시간 |
| ---- | ---- | ------------------------- | --------------------------------------- | ------ | ------ | ---- |
| ☑    | M6-1 | GitHub Actions 워크플로우 | `daily_pipeline.yml` + `test.yml`       | M4-5   | 쉬움   | 2h   |
| ☑    | M6-2 | Dockerfile 작성           | 파이프라인 러너 컨테이너화              | M4-5   | 쉬움   | 2h   |
| ☑    | M6-3 | docker-compose 작성       | 로컬 개발용 compose 파일                | M6-2   | 쉬움   | 1h   |
| ☑    | M6-4 | Hetzner VPS 설정 (선택)   | CX11 인스턴스 생성, cron 설정, SSH 키   | M6-2   | 보통   | 3h   |
| ☑    | M6-5 | 환경 변수 문서화          | `.env.example` 완성, README 설정 가이드 | M4-5   | 쉬움   | 1h   |
| ☑    | M6-6 | README 작성               | 설정 가이드, 아키텍처 개요, 문서 링크   | 전체   | 쉬움   | 2h   |

**체크포인트**: GitHub Actions에서 워크플로우 수동 트리거(`workflow_dispatch`) 후 R2에 파일 업로드 확인.

### Milestone 6-1: GitHub Actions 성능 최적화

| Done | ID     | 설명                                | 예상 효과                                           | 난이도 | 시간 |
| ---- | ------ | ----------------------------------- | --------------------------------------------------- | ------ | ---- |
| ☑    | M6-1-1 | test.yml 병렬 실행 활성화           | pytest, mypy, ruff를 동시 실행 → ~35-40% 단축       | 쉬움   | 30m  |
| ☑    | M6-1-2 | daily_pipeline.yml Python 캐시 추가 | pip 캐시 활성화 → 의존성 설치 50-70% 단축           | 쉬움   | 20m  |
| ☑    | M6-1-3 | 파이프라인 API 호출 동시성 강화     | pykrx·opendartreader 멀티스레딩/비동기 적용         | 보통   | 2h   |
| ☐    | M6-1-4 | DART 배치 처리 최적화               | 종목별 개별 호출 → 배치 API 활용으로 통신 횟수 감축 | 보통   | 1.5h |

**체크포인트**: test.yml < 5분, daily_pipeline.yml < 60분으로 단축 확인.

### Milestone 6-2: DART & DB 재사용 성능 최적화

| Done | ID     | 설명                | 예상 효과                                                               | 난이도 | 시간 |
| ---- | ------ | ------------------- | ----------------------------------------------------------------------- | ------ | ---- |
| ☑    | M6-2-1 | DART 병렬 수 설정화 | max_workers: 2 → 4~8 (설정) → DART 수집 180초 → 105초 (42% 단축)        | 쉬움   | 30m  |
| ☑    | M6-2-2 | DB 재사용 구조 개선 | PRESERVE_DB 옵션 추가 → 월간 quota 97% 절약, 당일 재실행 캐시 100% 활용 | 보통   | 2h   |

**체크포인트**: DART 수집 < 2분, 월간 quota < 10,000회 유지 확인.

### Milestone 6-3: 수집 & 스크리닝 로직 벡터화

| Done | ID     | 설명                        | 예상 효과                                                                                                                | 난이도 | 시간 |
| ---- | ------ | --------------------------- | ------------------------------------------------------------------------------------------------------------------------ | ------ | ---- |
| ☐    | M6-3-1 | KRX 기본정보 중복 호출 제거 | `fetch_ticker_list()`에 `listing_date` 정보 포함 → `fetch_stock_listing_info()` 제거 → KRX API 호출 2회 → 1회 (50% 단축) | 보통   | 1h   |
| ☑    | M6-3-2 | PER/PBR 계산 벡터화         | `market_ratios.py`의 `iterrows()` 제거 → pandas 컬럼 연산으로 변경 → 3-5배 속도 개선                                     | 쉬움   | 30m  |
| ☐    | M6-3-3 | risk_flags 생성 벡터화      | `stage3_trap_detector.py`의 `apply(axis=1)` 부분 최적화 → 완전 벡터 연산 또는 numba 가능                                 | 보통   | 1h   |

**체크포인트**: 전체 파이프라인 실행 시간 20% 단축 확인, 특히 데이터 변환 단계 5초 이내 유지.

#### M6-3-1: KRX 기본정보 중복 호출 제거

**문제점:**

```python
# src/pipeline/runner.py 현재 흐름
tickers = fetch_ticker_list(query_date)  # KRX API: stk_isu_base_info, ksq_isu_base_info
listing_info = fetch_stock_listing_info(query_date)  # 동일 API 재호출
```

- `fetch_ticker_list()`이 이미 `ISU_SRT_CD`, `ISU_ABBRV`, `LIST_DD`, `LIST_SHRS` 등 상장정보 반환
- `fetch_stock_listing_info()`가 동일한 API(`stk_isu_base_info`, `ksq_isu_base_info`) 재호출
- **결과**: 중복 API 호출 (2회 → 1회로 통합 가능)

**해결책:**

1. `krx_tickers.py`의 `fetch_ticker_list()` 반환 DataFrame에 `listing_date`, `shares_outstanding` 컬럼 추가
2. `runner.py`에서 `fetch_stock_listing_info()` 호출 제거
3. `fundamentals` 테이블 upsert 시 `tickers` DataFrame 직접 사용

**구현 예시:**

```python
# src/collectors/krx_tickers.py
def fetch_ticker_list(base_date: str | None = None) -> pd.DataFrame:
    # ...
    # 기존: stock_code, stock_name, market
    # 변경: stock_code, stock_name, market, listing_date, shares_outstanding
    # (LIST_DD, LIST_SHRS를 API에서 직접 추출)
    return result[["stock_code", "stock_name", "market", "listing_date", "shares_outstanding"]]

# src/pipeline/runner.py
tickers = fetch_ticker_list(run_date)  # listing_date 포함됨
# 제거: listing_info = fetch_stock_listing_info(run_date)
```

**예상 효과:**

- KRX API 호출 2회 → 1회 (50% 감소)
- 파이프라인 전체 실행 시간 ~10초 단축

---

#### M6-3-2: PER/PBR 계산 로직 벡터화

**문제점:**

```python
# src/collectors/market_ratios.py 현재 구현
def calculate_market_ratios(prices_df, fundamentals_df):
    results = []
    for idx, row in prices_df.iterrows():  # 종목별 루프 (느림)
        stock_code = row["stock_code"]
        close = row["close"]

        fundamentals = fundamentals_df[fundamentals_df["stock_code"] == stock_code].iloc[0]
        eps = fundamentals["eps"]

        per = close / eps if eps else None  # 스칼라 계산
        results.append({"stock_code": stock_code, "per": per, ...})

    return pd.DataFrame(results)
```

- `iterrows()`로 한 줄씩 순회 → O(n) 느림
- 각 `prices` 행마다 `fundamentals` 필터링 → O(n²) 복잡도

**해결책:**

```python
# 벡터화된 구현
def calculate_market_ratios(prices_df, fundamentals_df):
    # merge로 한 번에 정렬
    merged = prices_df.merge(
        fundamentals_df[["stock_code", "eps", "bps", "dps"]],
        on="stock_code",
        how="left"
    )

    # 벡터 연산 (numpy 기반, 매우 빠름)
    merged["per"] = merged["close"] / merged["eps"]
    merged["pbr"] = merged["close"] / merged["bps"]
    merged["dividend_yield"] = (merged["dps"] / merged["close"] * 100)

    # NaN 처리
    merged["per"] = merged["per"].where(merged["eps"].notna(), None)
    merged["pbr"] = merged["pbr"].where(merged["bps"].notna(), None)

    return merged[["stock_code", "per", "pbr", "dividend_yield"]]
```

**예상 효과:**

- 벡터화로 3-5배 속도 개선 (2,600 종목 기준: 800ms → 160ms)
- 코드 가독성 향상

---

#### M6-3-3: Stage 3 risk_flags 벡터화

**문제점:**

```python
# src/screening/stage3_trap_detector.py 현재 구현
def is_value_trap(row):
    flags = []
    if row["roe"] < 0: flags.append("NEGATIVE_ROE")
    if row["debt_to_equity"] > 3.0: flags.append("HIGH_DEBT")
    # ... (10+ 조건 반복)
    return " | ".join(flags) if flags else None

# 느린 apply 호출
trap_df["risk_flags"] = df.apply(is_value_trap, axis=1)
```

- `apply(axis=1)`은 행 기준 루프 → Python 인터프리터 오버헤드
- 각 행마다 함수 호출 → 콜 스택 비용 존재

**해결책:**

옵션 A (완전 벡터화):

```python
def detect_risk_flags_vectorized(df):
    """완전 벡터 연산으로 플래그 생성"""
    flags = []

    # 각 조건을 Boolean 벡터로 생성
    neg_roe = df["roe"] < 0
    high_debt = df["debt_to_equity"] > 3.0
    low_icr = df["interest_coverage"] < 1.5
    # ... (더 많은 조건)

    # 조건별 플래그 텍스트 배열 생성
    result = []
    for i in range(len(df)):
        row_flags = []
        if neg_roe.iloc[i]: row_flags.append("NEGATIVE_ROE")
        if high_debt.iloc[i]: row_flags.append("HIGH_DEBT")
        if low_icr.iloc[i]: row_flags.append("LOW_ICR")
        result.append(" | ".join(row_flags) if row_flags else None)

    return pd.Series(result, index=df.index)

trap_df["risk_flags"] = detect_risk_flags_vectorized(df)
```

옵션 B (Numba 가속화, 더 빠름):

```python
import numba as nb
import numpy as np

@nb.jit(nopython=True)
def _compute_flags_numba(roe, debt, icr):
    """Numba로 JIT 컴파일된 플래그 계산"""
    n = len(roe)
    flags = np.zeros(n, dtype=object)

    for i in range(n):
        flag_list = []
        if roe[i] < 0: flag_list.append("NEGATIVE_ROE")
        if debt[i] > 3.0: flag_list.append("HIGH_DEBT")
        if icr[i] < 1.5: flag_list.append("LOW_ICR")

        if flag_list:
            flags[i] = " | ".join(flag_list)
        else:
            flags[i] = None

    return flags
```

**예상 효과:**

- 벡터화로 2-3배 속도 개선 (2,600 종목 기준: 400ms → 150ms)
- Numba 사용 시 10배 이상 가능 (하지만 설정 복잡도 증가)

---

## Milestone 6-4: DART 배치 처리 최적화 (향후 개선)

> 현재 M6-1-1~M6-1-3으로 충분한 성능 개선이 이뤄졌으므로, 추가 최적화는 투입 대비 효과 검증 후 진행.

### 배경

- **현재 구조**: 종목별 × 연도별 개별 API 호출 → `dart.finstate(code, fiscal_year)`
- **호출 횟수**: ~2,000 종목 × 3년 = ~6,000회/일
- **제약**: opendartreader 라이브러리가 배치 호출 미지원 (DART API 자체 한계)

### 가능한 최적화 방안 (우선순위)

| 방안                    | 설명                                                                          | 기술                       | 예상 효과              | 난이도 | 비고                                            |
| ----------------------- | ----------------------------------------------------------------------------- | -------------------------- | ---------------------- | ------ | ----------------------------------------------- |
| **A. 공시 목록 필터링** | DART 공시 목록을 먼저 조회 → 실제 공시된 것만 `finstate()` 호출               | `opendartreader.filings()` | 10-20%                 | 보통   | 네트워크 왕복 1회 증가, 하지만 불필요 호출 감소 |
| **B. 응답 캐싱**        | 같은 (code, fiscal_year)의 응답을 로컬 캐시/DB 저장 → 재실행 시 API 호출 제거 | SQLite 캐시 테이블 추가    | 20-30% (재실행 시에만) | 쉬움   | 초회 실행엔 효과 없음, 반복 실행 시 의미 있음   |
| **C. 응답 처리 최적화** | DataFrame 파싱/정규화 최적화 (메모리 효율, 벡터화)                            | pandas 최적화              | 5-10%                  | 어려움 | 이미 M6-1-3의 병렬화로 많이 개선됨              |
| **D. 요청 순서 최적화** | 최신 연도부터 역순 요청 + 조기 종료 조건 추가                                 | 로직 수정                  | 0-5%                   | 쉬움   | 미미한 효과                                     |

### 권장 로드맵

1. **즉시 (현재)**: M6-1-1~M6-1-3 완료 (병렬화 → 3-4배 단축)
2. **1차 검증**: daily_pipeline.yml 실제 실행 → 소요 시간 측정
3. **조건부 진행**:
   - 소요시간 > 40분: **방안 A** (공시 목록 필터링) 먼저 적용
   - 소요시간 < 40분: **방안 B** (캐싱) 적용 후 무시
   - 소요시간 < 20분: 모든 최적화 완료, 유지보수 모드

### 구현 스케치 (방안 A: 공시 목록 필터링)

```python
# src/collectors/dart_financials.py 개선안 (향후)

def fetch_financial_statements(...):
    dart = _create_dart_client()
    codes = [...]

    # 1단계: 공시 목록 조회 (1회)
    filings = dart.filings(start_date, end_date)  # 모든 공시 회사 목록
    filed_codes = set(filings['stock_code'].unique())

    # 2단계: 필요한 것만 호출
    code_year_pairs = [
        (code, year)
        for code in codes
        for year in fiscal_years
        if code in filed_codes  # 필터링 추가
    ]

    # 3단계: 병렬 처리 (M6-1-3과 동일)
    rows = list(parallel_map(_fetch_and_normalize, code_year_pairs, max_workers=2))
```

### 구현 스케치 (방안 B: 응답 캐싱)

```python
# src/db/repository.py에 캐시 메서드 추가 (향후)

class Repository:
    def get_cached_financial_statement(self, code: str, fiscal_year: int) -> dict | None:
        """캐시에서 재무 데이터 조회"""
        # financials 테이블에서 조회

    def cache_financial_statement(self, data: dict) -> None:
        """재무 데이터 캐시에 저장"""
        # financials 테이블에 저장
```

---

## Milestone 7: KRX 인증 방식 전환 (pykrx → 공식 Open API)

> **배경**: KRX가 `data.krx.co.kr` 직접 접근에 로그인을 요구하면서 비공식 스크래핑 기반의 `pykrx`가 불안정해졌다.  
> 공식 Open API(`openapi.krx.co.kr`)는 `AUTH_KEY` 헤더 인증 방식으로 동일한 데이터를 안정적으로 제공한다.  
> 수집 전략도 **종목별 기간 조회 → 날짜별 전체 시장 스냅샷** 방식으로 전환하여 API 호출 수를 줄인다.

### API 매핑 요약

| 현재 pykrx 함수                        | 대체 엔드포인트                                              | Base URL                                  |
| -------------------------------------- | ------------------------------------------------------------ | ----------------------------------------- |
| `get_market_ticker_list()` + 상장 정보 | `/stk_isu_base_info`, `/ksq_isu_base_info`                   | `https://data-dbg.krx.co.kr/svc/apis/sto` |
| `get_market_ohlcv_by_ticker()`         | `/stk_bydd_trd`, `/ksq_bydd_trd`                             | 동일                                      |
| `get_market_cap_by_ticker()`           | `/stk_bydd_trd` (`MKTCAP` 필드 포함)                         | 동일                                      |
| `get_market_fundamental_by_ticker()`   | `/stk_bydd_trd` (`PER`, `PBR` 포함 확인, `DIV_YD` 검증 필요) | 동일                                      |
| `get_market_ohlcv(start, end, ticker)` | 날짜별 `/stk_bydd_trd` 반복 호출 후 피벗                     | 동일                                      |

### 1년 이력 수집 전략 변경

```
현재 (pykrx):  종목별 1회 기간 조회  →  2,000 종목 × 1회  =  2,000 API 호출
변경 (Open API): 날짜별 전체 시장 조회 →  252 거래일 × 1회  =    252 API 호출  (↓87%)
```

| Done | ID    | 작업                          | 설명                                                                                                                                                                                                              | 의존성      | 난이도 | 시간 |
| ---- | ----- | ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- | ------ | ---- |
| ☑    | M7-1  | KRX Open API 클라이언트 구현  | `src/collectors/krx_client.py` 신설. `AUTH_KEY` 헤더 주입, JSON 응답 파싱, rate limiting, 재시도 래퍼                                                                                                             | M0          | 쉬움   | 1h   |
| ☑    | M7-2  | 배당수익률 포함 여부 검증     | `/stk_bydd_trd` 실제 호출로 `DIV_YD`(또는 동등 필드) 존재 확인. 미포함 시 별도 API 엔드포인트 식별                                                                                                                | M7-1        | 쉬움   | 30m  |
| ☑    | M7-3  | 종목 수집기 마이그레이션      | `krx_tickers.py`: pykrx 제거 → `/stk_isu_base_info` + `/ksq_isu_base_info`. `LIST_DD`(상장일), `LIST_SHRS`(상장주식수) 매핑                                                                                       | M7-1        | 보통   | 2h   |
| ☐    | M7-4  | 일별 가격 수집기 마이그레이션 | `krx_prices.py`: `/stk_bydd_trd`, `/ksq_bydd_trd`. `TDD_CLSPRC`→close, `ACC_TRDVAL`→trading_value, `MKTCAP`, `PER`, `PBR`, 배당수익률(M7-2 결과 반영) 컬럼 매핑                                                   | M7-1, M7-2  | 보통   | 3h   |
| ☐    | M7-5  | 1년 이력 수집 재설계          | `fetch_price_history_1y()`, `fetch_avg_trading_value_20d()` 재구현. 날짜별 전체 시장 조회 후 피벗. 기존 `parallel_map(ticker별)` → `sequential(날짜별)` 전환                                                      | M7-4        | 보통   | 2h   |
| ☐    | M7-6  | 설정 및 의존성 업데이트       | `settings.py`에 `KRX_AUTH_KEY` 추가, `.env.example` 반영, `docs/ENV_VARS.md` 업데이트, `requirements.txt`에서 `pykrx` 제거                                                                                        | M7-3, M7-4  | 쉬움   | 30m  |
| ☐    | M7-7  | 수집기 테스트 업데이트        | `tests/test_collectors/` mock 전략 변경: `pykrx.stock.*` → `requests.get` 응답 모킹(`responses` 라이브러리 또는 `unittest.mock`). 기존 테스트 케이스 유지                                                         | M7-3 ~ M7-5 | 보통   | 2h   |
| ☐    | M7-8  | DART BPS/DPS 계정명 추가      | `dart_financials.py`의 `_ACCOUNT_MAP`에 누락 항목 추가: `"bps": ("주당순자산가치", "1주당 순자산")`, `"dps": ("주당배당금", "현금배당금(보통주)")`. `fundamentals` 테이블 컬럼은 이미 존재하므로 수집 로직만 보완 | M0          | 쉬움   | 1h   |
| ☐    | M7-9  | 시장 배수 계산기 구현         | `src/collectors/market_ratios.py` 신설. `prices.close` + `fundamentals.eps/bps/dps` → `per/pbr/dividend_yield` 계산 후 `prices` 테이블 갱신. 파이프라인 runner에 DART·KRX 수집 완료 후 단계로 추가                | M7-4, M7-8  | 보통   | 2h   |
| ☐    | M7-10 | 시장 배수 계산 테스트         | 합성 데이터(prices + fundamentals)로 `market_ratios.py` 단위 테스트. 엣지 케이스: eps=0, bps=None, dps 누락 시 None 처리 검증                                                                                     | M7-9        | 쉬움   | 1h   |

### M7-2 검증 결과 요약

> **KRX Open API `stk_bydd_trd` 응답 필드 (실측)**

| 필드            | 설명                  | 비고                            |
| --------------- | --------------------- | ------------------------------- |
| `BAS_DD`        | 기준일자              |                                 |
| `ISU_CD`        | 종목코드              |                                 |
| `ISU_NM`        | 종목명                |                                 |
| `MKT_NM`        | 시장명 (KOSPI/KOSDAQ) |                                 |
| `SECT_TP_NM`    | 섹터명                |                                 |
| `TDD_CLSPRC`    | 종가                  |                                 |
| `TDD_OPNPRC`    | 시가                  |                                 |
| `TDD_HGPRC`     | 고가                  |                                 |
| `TDD_LWPRC`     | 저가                  |                                 |
| `ACC_TRDVOL`    | 거래량                |                                 |
| `ACC_TRDVAL`    | 거래대금              |                                 |
| `MKTCAP`        | 시가총액              |                                 |
| `LIST_SHRS`     | 상장주식수            | `stk_isu_base_info`와 중복 제공 |
| `CMPPREVDD_PRC` | 전일대비              |                                 |
| `FLUC_RT`       | 등락률                |                                 |
| ~~PER~~         |                       | **미제공**                      |
| ~~PBR~~         |                       | **미제공**                      |
| ~~배당수익률~~  |                       | **미제공**                      |

> **`stk_isu_base_info` 응답 필드** (`basDd` 파라미터 필수)

| 필드                   | 설명                |
| ---------------------- | ------------------- |
| `ISU_SRT_CD`           | 단축코드 (6자리)    |
| `ISU_NM` / `ISU_ABBRV` | 종목명 / 약칭       |
| `LIST_DD`              | 상장일 (YYYY/MM/DD) |
| `LIST_SHRS`            | 상장주식수          |
| `MKT_TP_NM`            | 시장구분            |
| `PARVAL`               | 액면가              |

> **결론**: PER/PBR/배당수익률은 KRX Open API 미제공. DART `eps`/`bps`/`dps` + KRX `close`로 자체 계산 (M7-8~M7-10).

**체크포인트**: `MAX_TICKERS=50 python -m src.pipeline.runner --date today` 후 pykrx 관련 import 없이 50개 종목 데이터 정상 수집 확인.

---

## Milestone 7-1: V1.1 투자 판단 신뢰도 향상(완료)

> 사용자가 "투자할만한지 판단 안 서는" 상황을 해결하기 위해 현금흐름, 지배구조, 공시 정보, AI 분석 추가.

| Done | ID | 테스트 | 설명 | 의존성 | 난이도 | 시간 |
|---|---|---|---|---|---|---|
| ☑ | M7-1-1 | 현금흐름 품질 필터 | Stage 3에 `LOW_FCF_QUALITY` 플래그 추가 (FCF/순이익 < 0.3) | M3-9 | 쉬움 | 1h |
| ☑ | M7-1-2 | PEG 비율 필터 | Stage 3에 `HIGH_PEG_RATIO` 플래그 추가 (PER/성장률 > 2.0) | M3-9 | 쉬움 | 1h |
| ☑ | M7-1-3 | 배당금 추세 필터 | Stage 3에 `DIVIDEND_CUT` 플래그 추가 (2년 연속 감소) | M3-9 | 쉬움 | 1h |
| ☑ | M7-1-4 | 공시 정보 수집기 | `dart_corporate_info.py`: 공시 일정, 지연 정보 수집 | M0 | 보통 | 2h |
| ☑ | M7-1-5 | 공시 지연 필터 | Stage 3에 `DISCLOSURE_DELAY` 플래그 추가 (>60일) | M7-1-4 | 쉬움 | 1h |
| ☑ | M7-1-6 | 지배구조 정보 수집 | `dart_corporate_info.py`: 주요주주, 기관 보유율 수집 | M0 | 보통 | 1.5h |
| ☑ | M7-1-7 | 지배구조 필터 | Stage 3에 `HIGH_MAJOR_SHAREHOLDER`, `LOW_INSTITUTIONAL_OWNERSHIP` 플래그 추가 | M7-1-6 | 쉬움 | 1h |
| ☑ | M7-1-8 | 점수 추세 지표 | `rankings` 테이블에 `score_change_20d`, `score_volatility` 컬럼 추가 | M4-5 | 보통 | 2h |
| ☑ | M7-1-9 | Gemini AI 분석기 | `ai_analyst.py`: Gemini API 기반 종합 분석 생성 | M0 | 보통 | 3h |
| ☑ | M7-1-10 | 공시 뉴스 수집기 | `dart_news.py`: 최근 30일 공시 요약 생성 | M0 | 쉬움 | 1h |
| ☑ | M7-1-11 | AI 분석 저장 & 조회 | `ai_analysis` 테이블 추가, Repository 메서드 구현 | M7-1-9 | 쉬움 | 1.5h |
| ☑ | M7-1-12 | 파이프라인 통합 | runner.py에서 상위 20개 종목의 AI 분석 자동 생성 | M7-1-1 ~ M7-1-11 | 보통 | 2h |

**체크포인트**: 파이프라인 실행 후 ai_analysis 테이블에 분석 결과 저장 확인, `"시장 평가"`, `"강점"`, `"위험"`, `"투자 의견"` 섹션 포함 확인.

---

## Milestone 8: 대시보드 UX 개선 (초보자 친화)
---

## Milestone 8: V2 AI 정성 분석 파이프라인

> **배경**: 정량 스코어(Stage 1~4)만으로는 시장 트렌드·뉴스·거시경제 동향을 반영하기 어렵다. Google Gemini API Free Tier(Gemini 1.5 Flash: 1,500 req/일 무료)를 활용하여 추가 비용 없이 LLM 기반 정성 분석을 Stage 5로 추가한다.  
> 상세 설계: [PRD 섹션 16](PRD.md#16-v2-ai-정성-분석-파이프라인)

### 의존성 요약

```
M8 전체 → M7 완료 (파이프라인 안정화 후 진행)
M8-3 → M8-1, M8-2
M8-5 → M8-3, M8-4
M8-6 → M8-3
M8-7 → M8-5, M8-6
M8-8 → M8-5 (Streamlit 컴포넌트 테스트)
```

| Done | ID   | 작업                         | 설명                                                                                                                                                                                                                                                                                             | 의존성     | 난이도 | 시간 |
| ---- | ---- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------- | ------ | ---- |
| ☑    | M8-1 | 뉴스 수집기 구현             | `src/collectors/news_collector.py`: 네이버 금융 RSS(`https://finance.naver.com/item/news.nhn?code=XXXXXX`)에서 종목별 최근 뉴스 헤드라인 5~10건 수집. 파싱 실패 시 빈 리스트 반환(graceful fallback).                                                                                            | M0         | 보통   | 3h   |
| ☑    | M8-2 | Gemini API 클라이언트 구현   | `src/collectors/gemini_client.py`: `google-generativeai` SDK 래퍼. `AI_API_KEY` env var 주입, 모델 선택(기본: `gemini-1.5-flash`), 요청 간 `time.sleep(4)` rate limit, exponential backoff 재시도(최대 3회).                                                                                     | M0         | 보통   | 2h   |
| ☑    | M8-3 | Stage 5 AI 분석기 구현       | `src/screening/stage5_ai_analysis.py`: Stage 4 순위 데이터 입력 → 상위 N개 종목 선택(기본 30, `config/screening_params.yaml` 설정) → 뉴스 수집 → 프롬프트 구성 → Gemini 호출 → `ai_insights` 테이블 저장. `AI_API_KEY` 미설정 시 자동 건너뜀.                                                    | M8-1, M8-2 | 보통   | 4h   |
| ☑    | M8-4 | DB 스키마 확장               | `src/db/schema.py`에 `ai_insights` 테이블 추가(ticker, run_date, guide_text, sentiment, generated_at, model_used). `src/db/repository.py`에 `upsert_ai_insights()`, `get_ai_insight()` 메서드 추가. 마이그레이션 버전 +1.                                                                        | M2         | 보통   | 2h   |
| ☑    | M8-5 | 파이프라인 러너 연동         | `src/pipeline/runner.py`에 Stage 5 호출 추가. Stage 4 완료 후 `AI_API_KEY` 유무 체크 후 조건부 실행. Stage 5 실패가 전체 파이프라인을 중단하지 않도록 try/except 처리.                                                                                                                           | M8-3, M8-4 | 쉬움   | 1h   |
| ☑    | M8-6 | 설정 파일 업데이트           | `config/screening_params.yaml`에 `ai_analysis` 섹션 추가: `enabled: true`, `top_n: 30`, `model: gemini-1.5-flash`, `rate_limit_sleep: 4`. `settings.py`에 `AI_API_KEY` 필드 추가(Optional). `.env.example` 및 `docs/ENV_VARS.md` 업데이트. `requirements.txt`에 `google-generativeai>=0.8` 추가. | M8-2       | 쉬움   | 1h   |
| ☑    | M8-7 | 수집기 단위 테스트           | `tests/test_collectors/test_news_collector.py`: RSS 파싱 성공·실패 케이스 모킹. `tests/test_collectors/test_gemini_client.py`: `google.generativeai` 모킹으로 API 키 없이 테스트. Rate limit 동작 확인.                                                                                          | M8-1, M8-2 | 보통   | 3h   |
| ☑    | M8-8 | Stage 5 통합 테스트          | `tests/test_screening/test_stage5_ai.py`: 합성 Stage 4 데이터 + 모킹된 Gemini 응답으로 `ai_insights` 테이블 저장 검증. `AI_API_KEY` 미설정 시 건너뜀 동작 검증.                                                                                                                                  | M8-3, M8-4 | 보통   | 2h   |
| ☑    | M8-9 | Streamlit AI 가이드 컴포넌트 | `src/ui/pages/stock_detail.py`에 AI 가이드 섹션 추가. `ai_insights` 데이터 있으면 가이드 박스 표시, 없으면 섹션 숨김. 생성 시각 + 7일 경과 시 경고 표시.                                                                                                                                         | M8-4, M5   | 보통   | 2h   |

**체크포인트**: `AI_API_KEY=<key> MAX_TICKERS=10 python -m src.pipeline.runner --date today` 실행 후 `ai_insights` 테이블에 상위 종목 가이드 저장 확인. `AI_API_KEY` 미설정 시 Stage 5 건너뜀 로그 확인.

---

## Milestone 9: 대시보드 UX 개선 (초보자 친화)

> 초보자 투자자가 데이터를 쉽게 이해하고 투자 판단에 실질적으로 도움이 되도록 대시보드 개선.

| Done | ID   | 테스트                   | 설명                                                                                                                                                      | 의존성     | 난이도 | 시간 |
| ---- | ---- | ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------ | ---- |
| ☐    | M9-1 | 마우스 오버 툴팁 강화    | Streamlit `st.popover()` + HTML 말풍선으로 지표 설명 확장. `metric_guides.py` 상세 설명 추가 (각 지표당 2-3문장)                                          | M5-1       | 쉬움   | 2h   |
| ☐    | M9-2 | 종목별 추천 이유 섹션    | 상세 페이지(`detail.py`)에 "📊 이 종목의 매력" 섹션 추가. 점수 상위 요인 3-5개를 일반인 언어로 설명. 예) "PER이 업종 평균보다 30% 낮고 배당수익률이 높음" | M5-3, M8-3 | 보통   | 3h   |
| ☐    | M9-3 | 업종 비교 분석           | 상세 페이지에 "🏭 업종 비교" 섹션 추가. 선택 종목 vs. 같은 업종 평균 비교 차트 (5개 점수별)                                                               | M5-1       | 보통   | 3h   |
| ☐    | M9-4 | 경험 레벨별 필터 UI      | 랭킹 페이지 사이드바에 "👤 투자 경험 레벨" 선택 옵션 추가 (초보자/중급자/전문가). 각 레벨별 추천 점수·위험도 기준 자동 조정                               | M5-2       | 보통   | 2h   |
| ☐    | M9-5 | 위험 신호 상세 설명 강화 | 상세 페이지 위험 플래그 테이블에 "상세 설명" 컬럼 추가. 각 플래그가 실제로 무엇을 의미하고 어떤 영향을 주는지 예시와 함께 설명                            | M5-3       | 보통   | 2h   |

**체크포인트**: 대시보드에서 마우스 오버 시 지표 설명이 나타나고, 상세 페이지에서 "이 종목의 매력", "업종 비교", 위험 신호 상세 설명이 모두 표시되는지 확인.

---

## 구현 우선순위 원칙

1. **데이터 없이는 아무것도 없다**: M1(수집) → M2(DB) 순서 필수
2. **E2E 먼저, 최적화는 나중에**: M4-8 End-to-End 테스트를 조기에 실행
3. **실제 데이터로 검증**: 합성 데이터 테스트 후 반드시 실제 시장 데이터로 파이프라인 검증
4. **설정 파일로 추출**: 스코어링 가중치·필터 임계값은 `config/screening_params.yaml`에서 관리, 코드 수정 없이 조정 가능

## 관련 문서

- 스크리닝 알고리즘: [SCREENING.md](SCREENING.md)
- 데이터베이스 스키마: [DATABASE.md](DATABASE.md)
- 배포 상세: [DEPLOYMENT.md](DEPLOYMENT.md)
