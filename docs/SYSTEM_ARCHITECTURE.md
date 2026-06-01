# ValueForge 시스템 아키텍처 구조도

> **전체 시스템 흐름 및 컴포넌트 상세 분석**

---

## 📊 1. 전체 시스템 구조 (High-Level View)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         VALUEFORGE 전체 시스템 아키텍처                        │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐          ┌──────────────────────────────┐       ┌─────────────────┐
│  데이터 소스      │          │   분석 파이프라인 서버         │       │  클라우드 스토리지  │
│  (외부 API)      │          │   (에페머럴 환경)             │       │  (Cloudflare R2) │
└──────────────────┘          └──────────────────────────────┘       └─────────────────┘
       │                               │                                    ▲
       │                               │                                    │
       ▼                               ▼                                    │
   ┌─────────────┐             ┌──────────────┐          DB 업로드        │
   │  pykrx      │             │  Collectors  │  ─────────────────────────┤
   │  (KRX API)  │────────────►│  ├─ krx      │  ◄──────────────────────┐  │
   │             │             │  ├─ dart     │                        │  │
   └─────────────┘             │  ├─ yfinance │                        │  │
                               │  └─ ratios   │                    DB 다운로드
   ┌─────────────┐             └──────────────┘                        │  │
   │  DART API   │                     │                               │  │
   │ (재무 데이터) │────────────┐       │                               │  │
   └─────────────┘             │       ▼                               │  │
                               │  ┌──────────────┐                     │  │
   ┌─────────────┐             │  │  SQLite DB   │                     │  │
   │ yfinance    │────────────┐│  │  (임시)      │──────────────┐      │  │
   │ (폴백 가격)  │  (선택)     ││  └──────────────┘              │      │  │
   └─────────────┘             │         │                        │      │  │
                               │         ▼                        │      │  │
                               │  ┌──────────────┐                │      │  │
                               │  │ Screening    │                │      │  │
                               │  │ Pipeline     │                │      │  │
                               │  ├─ Stage 1     │                │      │  │
                               │  ├─ Stage 2     │                │      │  │
                               │  ├─ Stage 3     │                │      │  │
                               │  ├─ Stage 4     │                │      │  │
                               │  └──────────────┘                │      │  │
                               │         │                        │      │  │
                               │         ▼                        │      │  │
                               │  ┌──────────────┐                │      │  │
                               │  │   R2Upload   │                │      │  │
                               │  │  (boto3)     │────────────────┼──────┘  │
                               │  └──────────────┘                │         │
                               │                                  ├─────────┘
                               │                    (한 번에 모두 업로드)
                               │
                               │ 스케줄 (GitHub Actions / Hetzner VPS)
                               │
                               │ 월-금 (KRX 거래일만)
                               │ 08:00 UTC = 17:00 KST
                               │
                               └─ 60-90분 소요
                                  └─ 전 종목 수집 (30-60분)
                                  └─ 스크리닝 (5분)
                                  └─ R2 업로드 (2분)
```

---

## 🔄 2. 데이터 흐름 (Data Flow)

### 2.1 쓰기 경로: 파이프라인 → R2 → 대시보드

```
[스케줄러 트리거]
    ↓
[GitHub Actions 러너 / Hetzner VPS]
    ├─ Python 환경 초기화
    ├─ 의존성 설치
    └─ 파이프라인 실행
        ↓
    [데이터 수집 단계]
    ├─ pykrx: 전 종목 가격 데이터 (30-60분)
    │   └─ KRX API → DataFrame → SQLite
    ├─ DART: 재무 데이터 (15-30분)
    │   └─ REST API → JSON → 정규화 → SQLite
    └─ yfinance: 폴백 (필요 시)
        └─ pykrx 실패 종목만 수집
        ↓
    [스크리닝 파이프라인]
    ├─ Stage 1: 빠른 필터 (< 1분)
    │   └─ 명백한 비가치 종목 제거
    │   └─ 약 400-700개 → 약 400-700개
    ├─ Stage 2: 심화 스코어링 (< 2분)
    │   └─ 5개 점수 차원 (value, quality, safety, growth, momentum)
    │   └─ 각각 정규화 (percentile_rank_score)
    │   └─ 약 400-700개 → 약 400-700개
    ├─ Stage 3: 가치 함정 감지 (< 1분)
    │   └─ CRITICAL/HIGH 플래그 검사
    │   └─ 점수 패널티 또는 제외
    │   └─ 약 400-700개 → 약 300-600개
    └─ Stage 4: 최종 랭킹 (< 1분)
        └─ 복합 점수 기준 정렬
        └─ Top 50-100개 선정
        ↓
    [SQLite 저장]
    ├─ CREATE TABLE IF NOT EXISTS (스키마)
    ├─ UPSERT: stocks, prices, fundamentals
    ├─ INSERT: scores, risk_flags, rankings
    ├─ VACUUM + ANALYZE
    └─ /tmp/valueforge_YYYYMMDD.db (~ 10-50 MB)
        ↓
    [R2 업로드 (boto3)]
    ├─ Step 1: history/YYYY-MM-DD.db 업로드
    │         └─ 7일 이전 파일 자동 삭제
    ├─ Step 2: latest.db 덮어쓰기 (가장 중요)
    │         └─ 파이프라인 100% 완료 후에만 실행
    └─ Step 3: latest_metadata.json 업데이트
              └─ 실행 요약 (상태, 시간, Top 5)
        ↓
    [로컬 임시 파일 삭제]
        ↓
    [파이프라인 완료]
```

### 2.2 읽기 경로: R2 → Streamlit → 사용자

```
[사용자 웹 브라우저]
    ↓
[streamlit.app URL 접속]
    ↓
[Streamlit Cloud 세션 시작]
    ├─ @st.cache_resource(ttl=1800) 체크
    │   └─ 30분 캐시 TTL
    │   └─ 만료되었는가?
    │       ├─ YES → 새로 다운로드
    │       └─ NO → 캐시된 DB 사용
    └─ 캐시 캐시 만료 시:
        ├─ R2에서 latest_metadata.json 조회 (1KB)
        ├─ run_date 확인
        │   └─ 기존 DB와 동일 → 다운로드 스킵
        │   └─ 다르면 → latest.db 다운로드 (10-50MB)
        └─ /tmp/valueforge.db로 저장
        ↓
[Streamlit 대시보드 렌더링]
    ├─ SQLite 연결 (읽기 전용 URI: ?mode=ro)
    ├─ Ranking 탭
    │   ├─ rankings 테이블 조회
    │   ├─ 필터링 (sector, score range)
    │   └─ 상위 50-100개 종목 표시
    ├─ Detail 탭
    │   ├─ 선택 종목 상세 정보 조회
    │   ├─ scores, prices, fundamentals 조인
    │   ├─ 레이더 차트 (5개 점수 차원)
    │   └─ 위험 플래그 표시
    └─ About 탭
        └─ 시스템 정보, 데이터 신선도 표시
        ↓
    [HTML/JS로 렌더링]
        ↓
    [사용자 화면]
```

---

## 🏗️ 3. 컴포넌트 상세 구조

### 3.1 데이터 수집 계층 (Collectors)

```
src/collectors/
├── krx_tickers.py      ─── 종목 코드 리스트 (모든 KOSPI/KOSDAQ)
│   └─ pykrx.stock.get_market_ticker_list()
│   └─ → {"종목코드", "종목명", "시장구분"}
│
├── krx_prices.py       ─── 가격 데이터 (OHLCV)
│   └─ pykrx.stock.get_market_ohlcv()
│   └─ → {"open", "high", "low", "close", "volume"}
│   └─ 재시도 로직 (3회, 지수 백오프)
│
├── market_ratios.py    ─── 시장 지표 (PBR, PER 등)
│   └─ pykrx.stock.get_market_fundamental()
│   └─ → {"PER", "PBR", "배당수익률", "매출액증가율"}
│
├── dart_financials.py  ─── 재무 데이터 (DART OpenAPI)
│   ├─ DART 공시 조회 (분기별, 연간)
│   ├─ 재무제표 파싱 (재무상태표, 손익계산서)
│   └─ → {"매출액", "영업이익", "순이익", "자본금", ...}
│   └─ 레이트 리밋: 일 10,000건 (매우 느슨함)
│
└── yfinance_fallback.py ─── 폴백 수집 (선택)
    └─ pykrx 실패 종목에 한정
    └─ → {"close", "volume"} (기본 데이터만)
```

**수집 순서**:
1. 종목 리스트 조회 (2-3초)
2. 가격 + 지표 병렬 수집 (30-60분)
   - 동시성 제어: ThreadPoolExecutor(max_workers=5)
   - 요청 분산: rate_limiter.py (1초 간격)
3. DART 재무 데이터 수집 (15-30분)
   - 비동기 수집 (asyncio)
   - 정규화 및 스케일링

### 3.2 스크리닝 파이프라인 (Screening)

```
src/screening/
├── stage1_filter.py      ─── 빠른 필터 (< 1분)
│   ├─ 조건: 최소 거래량, 최소 주가, 상장 기간 등
│   ├─ 입력: 약 2,600개 종목
│   └─ 출력: 약 400-700개 종목
│
├── stage2_scorer.py      ─── 5개 점수 차원 계산 (< 2분)
│   ├─ Value Score
│   │  └─ PER, PBR, PSR, PCR 정규화
│   │  └─ percentile_rank_score() 사용
│   ├─ Quality Score
│   │  └─ ROE, 부채비율, 이자보상배수 정규화
│   ├─ Safety Score
│   │  └─ 자본금, 거래량, 변동성
│   ├─ Growth Score
│   │  └─ 매출액 증가율, 순이익 증가율
│   └─ Momentum Score
│      └─ 최근 3개월 수익률
│   └─ 입출력: 약 400-700개 종목
│
├── stage3_trap_detector.py ─── 가치 함정 감지 (< 1분)
│   ├─ 규칙 기반 플래그 적용
│   │  ├─ CRITICAL: 완전 제외 (1개 이상)
│   │  ├─ HIGH: 제외 (2개 이상) 또는 점수 -5
│   │  └─ MEDIUM: 점수 -2
│   ├─ 예시 플래그
│   │  ├─ 최근 3개월 마이너스 수익률
│   │  ├─ 높은 부채비율 (> 500%)
│   │  ├─ 매출액 급락
│   │  └─ 지주회사 (LOW 리스크 부여)
│   └─ 입출력: 약 300-600개 종목
│
└── stage4_ranker.py      ─── 최종 랭킹 (< 1분)
    ├─ 가중 점수 계산 (config/screening_params.yaml)
    │  ├─ composite_score = 
    │  │  value*30% + quality*25% + safety*20% + 
    │  │  growth*15% + momentum*10%
    ├─ 내림차순 정렬
    └─ Top 50-100개 선정
```

**핵심 함수**: `percentile_rank_score(values, value)` in `src/scoring/normalizer.py`
- 0-100 범위의 백분위 점수
- 이상값(outlier) 처리: [0.05, 0.95] 백분위 내로 캡핑
- 모든 점수 차원에서 일관되게 사용

### 3.3 점수 계산 계층 (Scoring)

```
src/scoring/
├── normalizer.py        ─── 정규화 (모든 점수 계산에 사용)
│   └─ percentile_rank_score(values: Series, value: float) → [0, 100]
│
├── value_scorer.py      ─── 가치 점수
│   └─ 입력: PER, PBR, PSR, PCR
│   └─ 출력: [0, 100]
│
├── quality_scorer.py    ─── 품질 점수
│   └─ 입력: ROE, 부채비율, 이자보상배수, ...
│   └─ 출력: [0, 100]
│
├── safety_scorer.py     ─── 안전 점수
│   └─ 입력: 자본금, 거래량, 변동성
│   └─ 출력: [0, 100]
│
├── growth_scorer.py     ─── 성장 점수
│   └─ 입력: 매출액/순이익 증가율
│   └─ 출력: [0, 100]
│
└── momentum_scorer.py   ─── 모멘텀 점수
    └─ 입력: 최근 3개월 수익률
    └─ 출력: [0, 100]
```

### 3.4 데이터베이스 계층 (Database)

```
src/db/
├── schema.py            ─── SQLite 스키마 정의
│   ├─ CREATE TABLE stocks
│   │  └─ {stock_code, stock_name, sector, market, ...}
│   ├─ CREATE TABLE prices
│   │  └─ {stock_code, run_date, open, high, low, close, volume}
│   ├─ CREATE TABLE fundamentals
│   │  └─ {stock_code, fiscal_year, per, pbr, roe, debt_ratio, ...}
│   ├─ CREATE TABLE scores
│   │  └─ {stock_code, run_date, value_score, quality_score, ...}
│   ├─ CREATE TABLE risk_flags
│   │  └─ {stock_code, run_date, flag_type, severity, ...}
│   ├─ CREATE TABLE rankings
│   │  └─ {rank, stock_code, run_date, composite_score, ...}
│   └─ CREATE TABLE pipeline_runs
│      └─ {run_date, completed_at, status, ...}
│
└── repository.py        ─── DB 접근 계층 (유일한 SQL 인터페이스)
    ├─ DatabaseRepository
    ├─ upsert_stocks(df, run_date)
    ├─ upsert_prices(df, run_date)
    ├─ upsert_fundamentals(df, run_date)
    ├─ insert_scores(df, run_date)
    ├─ insert_risk_flags(df, run_date)
    ├─ insert_rankings(df, run_date)
    └─ query_*(filters) → DataFrame
```

**원칙**: 모든 SQL 쿼리는 repository.py를 경유. 직접 SQL 금지.

### 3.5 스토리지 계층 (Storage)

```
src/storage/
├── r2_client.py         ─── R2 boto3 클라이언트
│   └─ get_r2_client() → boto3 S3 클라이언트 (S3 호환)
│
├── uploader.py          ─── R2 업로드 로직
│   ├─ upload_backup(db_path, run_date)
│   │  └─ history/{YYYY-MM-DD}.db 업로드
│   │  └─ 3회 재시도
│   ├─ upload_latest(db_path)
│   │  └─ latest.db 덮어쓰기 (반드시 backup 후)
│   ├─ update_metadata(run_date, ranked_df)
│   │  └─ latest_metadata.json
│   │  └─ run_date, completed_at, top_candidates[], ...
│   └─ cleanup_old_backups(keep_days=7)
│      └─ 7일 이상된 history/*.db 삭제
│
└── downloader.py        ─── R2 다운로드 로직
    └─ download_latest_db() → Path
       └─ latest.db → /tmp/valueforge_latest.db
```

**R2 버킷 구조**:
```
valueforge-bucket/
├── latest.db                  ← 항상 최신
├── latest_metadata.json       ← 메타데이터
└── history/
    ├── 2025-01-20.db
    ├── 2025-01-19.db
    ├── ...
    └── 2025-01-14.db         ← 7일 보존
```

### 3.6 프론트엔드 계층 (UI / Streamlit)

```
src/ui/
├── app.py                ─── 메인 Streamlit 앱
│   ├─ 페이지 라우팅 (multipage)
│   ├─ 캐시 관리
│   └─ 세션 상태 초기화
│
├── data_loader.py        ─── 데이터 로더 (캐시 레이어)
│   └─ @st.cache_resource(ttl=1800)
│   └─ get_db_connection() → sqlite3.Connection
│      └─ R2에서 latest.db 다운로드
│      └─ 읽기 전용 URI: ?mode=ro
│
├── views/
│   ├── ranking.py        ─── 랭킹 탭
│   │  ├─ 상위 50-100개 종목 테이블
│   │  ├─ 필터: 업종, 점수 범위
│   │  └─ 정렬: 순위, 점수, 이름
│   ├── detail.py         ─── 상세 탭
│   │  ├─ 선택 종목 상세 정보
│   │  ├─ 레이더 차트 (5개 점수)
│   │  ├─ 가격 차트 (간단)
│   │  ├─ 위험 플래그 표시
│   │  └─ 재무 지표 테이블
│   └── about.py          ─── About 탭
│      ├─ 시스템 정보
│      ├─ 데이터 신선도
│      └─ 알고리즘 설명
│
├── components/
│   ├── freshness_banner.py ─── 데이터 최신도 배너
│   │  └─ latest_metadata.json 조회
│   ├── radar_chart.py    ─── 레이더 차트 (Altair)
│   └── ...
│
└── metric_guides.py      ─── 지표 설명 (도움말)
```

**캐싱 전략**:
```python
@st.cache_resource(ttl=1800)  # 30분 TTL
def get_db_connection():
    db_path = download_latest_db()  # R2 다운로드
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    return conn
```

---

## 🔗 4. 외부 의존성 및 API

### 4.1 데이터 소스

| 소스 | 용도 | API/SDK | 비고 |
|---|---|---|---|
| **pykrx** | 종목 코드, 가격, 지표 | `pykrx` 라이브러리 | 스크래핑 기반, 무료, 신뢰도 높음 |
| **DART** | 재무제표 공시 | `opendart` 라이브러리 | 공식 금융감독원, 무료, 등록 필요 |
| **yfinance** | 폴백 (가격) | `yfinance` 라이브러리 | pykrx 실패 시만 사용 |

### 4.2 클라우드 서비스

| 서비스 | 용도 | 가격 | 비고 |
|---|---|---|---|
| **Cloudflare R2** | 데이터베이스 스토리지 | 무료 10GB + 이그레스 무료 | S3 호환 API |
| **GitHub Actions** | 스케줄 및 실행 | 무료 2,000분/월 | 월 90분×22거래일=1,980분 (한계) |
| **Hetzner VPS** | 대체 스케줄러 | $3.29/월 | 권장 (제약 없음) |
| **Streamlit Cloud** | 대시보드 호스팅 | 무료 | 읽기 전용 작업 |

### 4.3 인증 및 시크릿

```
GitHub Actions Secrets (쓰기 권한):
├─ DART_API_KEY
├─ KRX_AUTH_KEY
├─ R2_ACCOUNT_ID
├─ R2_ACCESS_KEY_ID        (읽기+쓰기)
├─ R2_SECRET_ACCESS_KEY
└─ R2_BUCKET_NAME

Streamlit Cloud Secrets (읽기 전용):
├─ R2_ACCOUNT_ID
├─ R2_ACCESS_KEY_ID        (읽기만)
├─ R2_SECRET_ACCESS_KEY
└─ R2_BUCKET_NAME
```

---

## ⏰ 5. 실행 주기 및 스케줄

### 5.1 현재 스케줄 (GitHub Actions)

```
Trigger: Cron "0 8 * * 1-5"
        = UTC 08:00 (매일)
        = KST 17:00 (매일)
        = 장 마감 후 약 1시간 30분

Days: 월~금 (KRX 거래일)
      = 월요일 17:00
      = 화요일 17:00
      = 수요일 17:00
      = 목요일 17:00
      = 금요일 17:00

실행 시간: 60-90분
├─ 수집: 45-75분
├─ 스크리닝: 5분
├─ 업로드: 2분
└─ 버퍼: 8-10분

월 실행 횟수: 22번 (거래일)
월 소요 시간: ~90분×22 = ~33시간
GitHub Actions 비용: ~1,980분/월 (한계)
```

### 5.2 제안된 스케줄 (Hetzner VPS 또는 Claude Schedule)

**사용자 요청**: 화요일~토요일 실행 (월, 일요일 제외)

```
화요일: KST 17:00
        └─ 월요일 마감(또는 금요일) 데이터 수집

수요일: KST 17:00
        └─ 화요일 데이터 수집

목요일: KST 17:00
        └─ 수요일 데이터 수집

금요일: KST 17:00
        └─ 목요일 데이터 수집

토요일: KST 17:00
        └─ 금요일 데이터 수집 (이번 주 마지막)

월요일: 휴지
        └─ 주말 시장 없음

일요일: 휴지
        └─ 주말 시장 없음

설정 (Cron):
"0 8 * * 2-6"
= UTC 08:00, 화(2)~토(6)
= 월(1), 일(0) 제외
```

---

## 🔐 6. 에러 처리 및 복구 메커니즘

### 6.1 재시도 로직

```python
# src/utils/retry.py
def with_retry(max_attempts=3, delay=5.0):
    """지수 백오프 기반 재시도"""
    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as e:
            if attempt == max_attempts - 1:
                raise
            time.sleep(delay * (2 ** attempt))  # 5s, 10s, 20s
```

**적용 대상**:
- pykrx API 호출 (3회, 지수 백오프)
- DART API 호출 (레이트 리밋 시 60초 대기)
- R2 업로드/다운로드 (3회)

### 6.2 Graceful Degradation

| 실패 유형 | 동작 |
|---|---|
| 단일 종목 수집 실패 | 로그 경고, 해당 종목 건너뜀 |
| pykrx 타임아웃 | 3회 재시도, 실패 시 해당 종목 제외 |
| DART 데이터 누락 | 가용 데이터로 점수 계산 (최대한 포함) |
| 전체 수집 50% 미만 | 파이프라인 실패 (latest.db 유지) |
| R2 업로드 실패 | 3회 재시도, 실패 시 GitHub Actions 이메일 알림 |
| 한국 장 휴장일 | `is_trading_day()` 체크 → exit(0) graceful |

### 6.3 데이터 무결성 보호

```
파이프라인 상태 플래그:
├─ "running": 파이프라인 중
├─ "success": 100% 완료, R2 업로드 완료
├─ "partial": 50% 이상 수집 但 업로드 실패
└─ "failed": 50% 미만 수집 또는 스크리닝 실패

R2 업로드 순서 (중요):
1. history/YYYY-MM-DD.db (백업 먼저)
2. latest.db (마지막에 덮어쓰기)
3. latest_metadata.json (상태 업데이트)

latest.db가 부분 결과를 포함하지 않도록 보호
```

---

## 📈 7. 성능 및 확장성

### 7.1 병목 지점

| 단계 | 소요 시간 | 병목 | 개선 가능성 |
|---|---|---|---|
| 종목 수집 | 30-60분 | pykrx API 응답 | 멀티 스레딩 (현재 최대) |
| DART 수집 | 15-30분 | REST API 요청 | 비동기 (asyncio) 사용 중 |
| 스크리닝 | 5분 | 메모리/CPU | 최적화 여지 적음 |
| R2 업로드 | 2분 | 네트워크 I/O | 병렬 업로드 가능 |

### 7.2 현재 확장성

```
종목 수: ~2,600개 (KOSPI + KOSDAQ)
데이터베이스 크기: 10-50 MB
캐시 주기: 30분 (Streamlit)
동시 사용자: 제약 없음 (읽기 전용)
데이터 지연: < 24시간 (다음 거래일 아침)
```

### 7.3 한계 및 제약

- **GitHub Actions 무료 티어**: 월 2,000분 (위험)
- **pykrx 스크래핑 의존성**: 웹 변경 시 깨질 수 있음
- **SQLite 동시 쓰기 불가**: 일 1회 배치만 가능 (현 상황에서 충분)
- **Streamlit Cloud 커스터마이징**: React 수준의 자유도 부족

---

## 🎯 8. 시스템 흐름 요약

```
┌──────────────────────────────────────────────────────────────────┐
│                    VALUEFORGE 데이터 라이프사이클                  │
└──────────────────────────────────────────────────────────────────┘

Day N (월~금, KRX 거래일):
  09:00 - 15:30  │ KRX 장 거래
                 │
  17:00 (KST)    │ 파이프라인 시작 (GitHub Actions)
  17:00-18:30    │ ├─ pykrx: 종목 수집 (30분)
                 │ ├─ DART: 재무 수집 (15분)
                 │ ├─ 스크리닝: 4단계 (5분)
                 │ └─ R2 업로드 (2분)
                 │
  18:30          │ 파이프라인 완료
                 │
  18:30-翌 09:00 │ Streamlit 캐시 30분 → 갱신
                 │
  사용자 접속 시  │ latest.db 읽기 (read-only)
                 │ → Ranking, Detail, About 렌더링

Day N+1 (다음 거래일):
  09:00 - 15:30  │ 새 거래일 시작
  17:00          │ 다음 파이프라인 시작 (반복)
```

---

## 📚 관련 문서

- [ARCHITECTURE.md](ARCHITECTURE.md) — 고수준 아키텍처 (기존)
- [SCREENING.md](SCREENING.md) — 스크리닝 알고리즘 상세
- [DATABASE.md](DATABASE.md) — SQLite 스키마
- [STORAGE.md](STORAGE.md) — R2 스토리지 설계
- [DEPLOYMENT.md](DEPLOYMENT.md) — 배포 전략 (GitHub Actions vs Hetzner VPS)
