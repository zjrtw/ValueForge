# 데이터베이스 설계

> **ValueForge** | SQLite 스키마, 인덱스, 쿼리 전략

## 목차

1. [전체 스키마](#1-전체-스키마)
2. [인덱스](#2-인덱스)
3. [주요 쿼리 패턴](#3-주요-쿼리-패턴)
4. [데이터 보존 전략](#4-데이터-보존-전략)
5. [최적화 노트](#5-최적화-노트)

---

## 1. 전체 스키마

```sql
-- ============================================================
-- VALUEFORGE SQLite SCHEMA v1.0
-- ============================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA cache_size = -64000;  -- 64MB 캐시

-- ============================================================
-- 기준 테이블
-- ============================================================

CREATE TABLE IF NOT EXISTS stocks (
    stock_code          TEXT PRIMARY KEY,           -- 예: '005930'
    stock_name          TEXT NOT NULL,              -- 예: '삼성전자'
    stock_name_en       TEXT,
    market              TEXT NOT NULL               -- 'KOSPI' 또는 'KOSDAQ'
                        CHECK (market IN ('KOSPI', 'KOSDAQ')),
    sector              TEXT,                       -- KRX 섹터 분류
    industry            TEXT,                       -- KRX 업종 분류
    listing_date        DATE,
    shares_outstanding  INTEGER,
    is_active           INTEGER NOT NULL DEFAULT 1, -- 0 = 상장폐지·거래정지
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now'))
);

-- ============================================================
-- 주가 데이터 (파이프라인 실행 시 일별 스냅샷)
-- ============================================================

CREATE TABLE IF NOT EXISTS prices (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code          TEXT NOT NULL,
    date                TEXT NOT NULL,              -- 'YYYY-MM-DD'
    open                REAL,
    high                REAL,
    low                 REAL,
    close               REAL NOT NULL,
    volume              INTEGER,
    market_cap          REAL,                       -- KRW 십억
    per                 REAL,
    pbr                 REAL,
    dividend_yield      REAL,                       -- 백분율
    FOREIGN KEY (stock_code) REFERENCES stocks(stock_code),
    UNIQUE (stock_code, date)
);

-- ============================================================
-- 재무 데이터 (연간, 최대 3개년)
-- ============================================================

CREATE TABLE IF NOT EXISTS fundamentals (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code          TEXT NOT NULL,
    fiscal_year         INTEGER NOT NULL,           -- 예: 2024
    fiscal_quarter      INTEGER,                    -- NULL=연간, 1-4=분기

    -- 손익계산서 (KRW 십억)
    revenue             REAL,
    gross_profit        REAL,
    operating_profit    REAL,
    ebitda              REAL,
    net_profit          REAL,

    -- 재무상태표 (KRW 십억)
    total_assets        REAL,
    current_assets      REAL,
    cash_and_equiv      REAL,
    total_liabilities   REAL,
    current_liabilities REAL,
    total_equity        REAL,
    total_debt          REAL,                       -- 이자부 부채

    -- 현금흐름표 (KRW 십억)
    operating_cf        REAL,
    capex               REAL,
    free_cash_flow      REAL,                       -- operating_cf - capex

    -- 주당 데이터
    eps                 REAL,
    bps                 REAL,
    dps                 REAL,

    -- 파생 비율 (스코어링 속도 향상을 위해 사전 산출)
    roe                 REAL,
    roa                 REAL,
    gross_margin        REAL,
    operating_margin    REAL,
    net_margin          REAL,
    debt_to_equity      REAL,
    current_ratio       REAL,
    interest_coverage   REAL,

    data_source         TEXT DEFAULT 'dart',
    collected_at        TEXT DEFAULT (datetime('now')),

    FOREIGN KEY (stock_code) REFERENCES stocks(stock_code),
    UNIQUE (stock_code, fiscal_year, fiscal_quarter)
);

-- ============================================================
-- 스크리닝 점수 (파이프라인 실행 단위)
-- ============================================================

CREATE TABLE IF NOT EXISTS scores (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code          TEXT NOT NULL,
    run_date            TEXT NOT NULL,              -- 'YYYY-MM-DD'

    -- Stage 1 결과
    stage1_pass         INTEGER NOT NULL DEFAULT 0,

    -- Stage 2 차원별 점수 (0-100 정규화)
    value_score         REAL,
    quality_score       REAL,
    safety_score        REAL,
    growth_score        REAL,
    momentum_score      REAL,

    -- Stage 2 복합 점수 (가중 합산)
    composite_score     REAL,

    -- Stage 3 함정 감지
    is_value_trap       INTEGER NOT NULL DEFAULT 0,
    trap_flag_count     INTEGER DEFAULT 0,

    -- Stage 4 랭킹
    final_rank          INTEGER,                    -- 필터 제외 시 NULL

    FOREIGN KEY (stock_code) REFERENCES stocks(stock_code),
    UNIQUE (stock_code, run_date)
);

-- ============================================================
-- 가치 함정 플래그 (상세 리스크 신호)
-- ============================================================

CREATE TABLE IF NOT EXISTS risk_flags (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code          TEXT NOT NULL,
    run_date            TEXT NOT NULL,
    flag_type           TEXT NOT NULL,
    -- 플래그 유형:
    --   NEGATIVE_ROE, EXCESSIVE_DEBT, PERSISTENT_LOSS,
    --   REVENUE_DECLINE, NEGATIVE_FCF, CASH_BURN,
    --   AUDIT_ISSUE, EQUITY_EROSION, DECLINING_MARGINS,
    --   LOW_INTEREST_COVERAGE, HOLDING_COMPANY, HIGH_CAPEX
    flag_description    TEXT,
    severity            TEXT NOT NULL
                        CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    metric_value        REAL,                       -- 실제 지표값
    threshold_value     REAL,                       -- 기준 임계값
    FOREIGN KEY (stock_code) REFERENCES stocks(stock_code)
);

-- ============================================================
-- 최종 랭킹 (대시보드 쿼리 최적화를 위한 비정규화)
-- ============================================================

CREATE TABLE IF NOT EXISTS rankings (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date            TEXT NOT NULL,
    rank                INTEGER NOT NULL,
    stock_code          TEXT NOT NULL,
    stock_name          TEXT NOT NULL,
    market              TEXT NOT NULL,
    sector              TEXT,

    -- 점수 요약
    composite_score     REAL NOT NULL,
    value_score         REAL,
    quality_score       REAL,
    safety_score        REAL,
    growth_score        REAL,
    momentum_score      REAL,

    -- 주요 지표 (조인 없이 표시용)
    market_cap_b        REAL,                       -- KRW 십억
    per                 REAL,
    pbr                 REAL,
    roe                 REAL,
    dividend_yield      REAL,
    debt_to_equity      REAL,

    -- 리스크 요약
    risk_flag_count     INTEGER DEFAULT 0,
    highest_severity    TEXT,

    FOREIGN KEY (stock_code) REFERENCES stocks(stock_code),
    UNIQUE (run_date, stock_code)
);

-- ============================================================
-- 파이프라인 실행 메타데이터
-- ============================================================

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date            TEXT NOT NULL UNIQUE,
    started_at          TEXT,
    completed_at        TEXT,
    duration_seconds    INTEGER,
    status              TEXT NOT NULL
                        CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED', 'PARTIAL')),

    -- 수집 통계
    stocks_collected    INTEGER DEFAULT 0,
    stocks_with_data    INTEGER DEFAULT 0,
    collection_errors   INTEGER DEFAULT 0,

    -- 스크리닝 통계
    stage1_pass_count   INTEGER DEFAULT 0,
    stage2_score_count  INTEGER DEFAULT 0,
    stage3_trap_count   INTEGER DEFAULT 0,
    final_candidates    INTEGER DEFAULT 0,

    -- 시스템 정보
    pipeline_version    TEXT,
    error_message       TEXT,
    warnings            TEXT                        -- JSON 배열
);
```

---

## 2. 인덱스

```sql
-- 기본 조회 패턴
CREATE INDEX IF NOT EXISTS idx_prices_code_date
    ON prices (stock_code, date DESC);

CREATE INDEX IF NOT EXISTS idx_fundamentals_code_year
    ON fundamentals (stock_code, fiscal_year DESC);

CREATE INDEX IF NOT EXISTS idx_scores_run_date
    ON scores (run_date, composite_score DESC);

CREATE INDEX IF NOT EXISTS idx_rankings_run_date_rank
    ON rankings (run_date DESC, rank ASC);

CREATE INDEX IF NOT EXISTS idx_risk_flags_code_date
    ON risk_flags (stock_code, run_date);

-- 대시보드 필터 패턴
CREATE INDEX IF NOT EXISTS idx_rankings_market
    ON rankings (market, run_date DESC);

CREATE INDEX IF NOT EXISTS idx_rankings_sector
    ON rankings (sector, run_date DESC);

CREATE INDEX IF NOT EXISTS idx_stocks_market
    ON stocks (market, is_active);
```

---

## 3. 주요 쿼리 패턴

### 대시보드 메인 랭킹 쿼리

```sql
SELECT
    r.*,
    s.listing_date,
    s.shares_outstanding
FROM rankings r
JOIN stocks s ON r.stock_code = s.stock_code
WHERE r.run_date = (
    SELECT MAX(run_date) FROM pipeline_runs WHERE status = 'SUCCESS'
)
  AND r.rank <= 100
ORDER BY r.rank ASC;
```

### 종목 상세 쿼리

```sql
-- 점수 + 플래그
SELECT sc.*, GROUP_CONCAT(rf.flag_type || ':' || rf.severity) AS flags
FROM scores sc
LEFT JOIN risk_flags rf
    ON sc.stock_code = rf.stock_code AND sc.run_date = rf.run_date
WHERE sc.stock_code = ? AND sc.run_date = ?
GROUP BY sc.id;

-- 재무 히스토리
SELECT * FROM fundamentals
WHERE stock_code = ?
ORDER BY fiscal_year DESC, fiscal_quarter DESC
LIMIT 12;
```

### 필터 쿼리 (동적 파라미터화)

```sql
SELECT * FROM rankings
WHERE run_date = ?
  AND market IN (?, ?)
  AND composite_score >= ?
  AND per BETWEEN ? AND ?
  AND risk_flag_count <= ?
ORDER BY composite_score DESC;
```

### 마지막 성공 실행 날짜

```sql
SELECT MAX(run_date) FROM pipeline_runs WHERE status = 'SUCCESS';
```

---

## 4. 데이터 보존 전략

| 데이터 | 보존 정책 |
|---|---|
| R2 `latest.db` | 매 실행 시 덮어쓰기 (항상 최신) |
| R2 `history/*.db` | 7일 롤링 보존, 자동 삭제 |
| `prices` 테이블 | 최근 12개월 일별 데이터 (모멘텀 계산에 필요) |
| `fundamentals` 테이블 | 종목당 최근 3개년 연간 데이터 유지 |
| `rankings` / `scores` | 현재 실행 데이터만 유지 |
| `pipeline_runs` | 전체 실행 이력 영구 보존 (소용량, 감사 목적) |
| `risk_flags` | 현재 실행 데이터만 유지 |

---

## 5. 최적화 노트

| 기법 | 설명 |
|---|---|
| `WAL 모드` | 쓰기 중 동시 읽기 허용 (파이프라인 쓰기 중 Streamlit 읽기 가능성 대비) |
| `cache_size = -64000` | SQLite 페이지 캐시 64MB, I/O 감소 |
| `VACUUM` | 파이프라인 완료 후 실행, 불필요한 공간 회수 및 파일 크기 최소화 |
| `ANALYZE` | 벌크 INSERT 후 실행, 쿼리 플래너 통계 최신화 |
| **`rankings` 비정규화** | 대시보드 페이지 로드 시 조인 제거, 가장 중요한 최적화 |
| `UNIQUE` 제약 | `upsert` (INSERT OR REPLACE) 패턴으로 재실행 시 중복 방지 |
