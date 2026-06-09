import sqlite3

SCHEMA_VERSION = 3
MIGRATIONS: dict[int, str] = {
    2: """
CREATE TABLE IF NOT EXISTS ai_insights (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker          TEXT NOT NULL,
    run_date        TEXT NOT NULL,
    guide_text      TEXT,
    sentiment       TEXT CHECK (sentiment IN ('긍정', '중립', '부정')),
    generated_at    TEXT,
    model_used      TEXT,
    FOREIGN KEY (ticker) REFERENCES stocks(stock_code),
    UNIQUE (ticker, run_date)
);
CREATE INDEX IF NOT EXISTS idx_ai_insights_run_date
    ON ai_insights (run_date DESC, ticker);
""",
    3: """
ALTER TABLE prices ADD COLUMN trading_value REAL;
""",
}

PRAGMA_SQL = """
PRAGMA foreign_keys = ON;
PRAGMA cache_size = -64000;
"""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS stocks (
    stock_code          TEXT PRIMARY KEY,
    stock_name          TEXT NOT NULL,
    stock_name_en       TEXT,
    market              TEXT NOT NULL
                        CHECK (market IN ('KOSPI', 'KOSDAQ')),
    sector              TEXT,
    industry            TEXT,
    listing_date        DATE,
    shares_outstanding  INTEGER,
    is_active           INTEGER NOT NULL DEFAULT 1,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS prices (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code          TEXT NOT NULL,
    date                TEXT NOT NULL,
    open                REAL,
    high                REAL,
    low                 REAL,
    close               REAL NOT NULL,
    volume              INTEGER,
    trading_value       REAL,
    market_cap          REAL,
    per                 REAL,
    pbr                 REAL,
    dividend_yield      REAL,
    FOREIGN KEY (stock_code) REFERENCES stocks(stock_code),
    UNIQUE (stock_code, date)
);

CREATE TABLE IF NOT EXISTS fundamentals (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code          TEXT NOT NULL,
    fiscal_year         INTEGER NOT NULL,
    fiscal_quarter      INTEGER NOT NULL DEFAULT 0,
    revenue             REAL,
    gross_profit        REAL,
    operating_profit    REAL,
    ebitda              REAL,
    net_profit          REAL,
    total_assets        REAL,
    current_assets      REAL,
    cash_and_equiv      REAL,
    total_liabilities   REAL,
    current_liabilities REAL,
    total_equity        REAL,
    total_debt          REAL,
    operating_cf        REAL,
    capex               REAL,
    free_cash_flow      REAL,
    eps                 REAL,
    bps                 REAL,
    dps                 REAL,
    roe                 REAL,
    roa                 REAL,
    gross_margin        REAL,
    operating_margin    REAL,
    net_margin          REAL,
    debt_to_equity      REAL,
    current_ratio       REAL,
    interest_coverage   REAL,
    data_source         TEXT DEFAULT 'dart',
    collected_at        TEXT DEFAULT (datetime('now', '+9 hours')),
    FOREIGN KEY (stock_code) REFERENCES stocks(stock_code),
    UNIQUE (stock_code, fiscal_year, fiscal_quarter)
);

CREATE TABLE IF NOT EXISTS scores (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code          TEXT NOT NULL,
    run_date            TEXT NOT NULL,
    stage1_pass         INTEGER NOT NULL DEFAULT 0,
    value_score         REAL,
    quality_score       REAL,
    safety_score        REAL,
    growth_score        REAL,
    momentum_score      REAL,
    composite_score     REAL,
    is_value_trap       INTEGER NOT NULL DEFAULT 0,
    trap_flag_count     INTEGER DEFAULT 0,
    final_rank          INTEGER,
    FOREIGN KEY (stock_code) REFERENCES stocks(stock_code),
    UNIQUE (stock_code, run_date)
);

CREATE TABLE IF NOT EXISTS risk_flags (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code          TEXT NOT NULL,
    run_date            TEXT NOT NULL,
    flag_type           TEXT NOT NULL,
    flag_description    TEXT,
    severity            TEXT NOT NULL
                        CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    metric_value        REAL,
    threshold_value     REAL,
    FOREIGN KEY (stock_code) REFERENCES stocks(stock_code)
);

CREATE TABLE IF NOT EXISTS rankings (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date            TEXT NOT NULL,
    rank                INTEGER NOT NULL,
    stock_code          TEXT NOT NULL,
    stock_name          TEXT NOT NULL,
    market              TEXT NOT NULL,
    sector              TEXT,
    composite_score     REAL NOT NULL,
    value_score         REAL,
    quality_score       REAL,
    safety_score        REAL,
    growth_score        REAL,
    momentum_score      REAL,
    market_cap_b        REAL,
    per                 REAL,
    pbr                 REAL,
    roe                 REAL,
    dividend_yield      REAL,
    debt_to_equity      REAL,
    risk_flag_count     INTEGER DEFAULT 0,
    highest_severity    TEXT,
    FOREIGN KEY (stock_code) REFERENCES stocks(stock_code),
    UNIQUE (run_date, stock_code)
);

CREATE TABLE IF NOT EXISTS ai_insights (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker          TEXT NOT NULL,
    run_date        TEXT NOT NULL,
    guide_text      TEXT,
    sentiment       TEXT CHECK (sentiment IN ('긍정', '중립', '부정')),
    generated_at    TEXT,
    model_used      TEXT,
    FOREIGN KEY (ticker) REFERENCES stocks(stock_code),
    UNIQUE (ticker, run_date)
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date            TEXT NOT NULL UNIQUE,
    started_at          TEXT,
    completed_at        TEXT,
    duration_seconds    INTEGER,
    status              TEXT NOT NULL
                        CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED', 'PARTIAL')),
    stocks_collected    INTEGER DEFAULT 0,
    stocks_with_data    INTEGER DEFAULT 0,
    collection_errors   INTEGER DEFAULT 0,
    stage1_pass_count   INTEGER DEFAULT 0,
    stage2_score_count  INTEGER DEFAULT 0,
    stage3_trap_count   INTEGER DEFAULT 0,
    final_candidates    INTEGER DEFAULT 0,
    pipeline_version    TEXT,
    error_message       TEXT,
    warnings            TEXT
);
"""

INDEX_SQL = """
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

CREATE INDEX IF NOT EXISTS idx_rankings_market
    ON rankings (market, run_date DESC);

CREATE INDEX IF NOT EXISTS idx_rankings_sector
    ON rankings (sector, run_date DESC);

CREATE INDEX IF NOT EXISTS idx_stocks_market
    ON stocks (market, is_active);

CREATE INDEX IF NOT EXISTS idx_ai_insights_run_date
    ON ai_insights (run_date DESC, ticker);
"""

MIGRATION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version             INTEGER PRIMARY KEY,
    applied_at          TEXT DEFAULT (datetime('now'))
);
"""


def initialize_schema(conn: sqlite3.Connection) -> None:
    """SQLite 연결에 ValueForge v1 스키마와 인덱스를 적용한다."""
    conn.executescript(PRAGMA_SQL)
    conn.executescript(SCHEMA_SQL)
    conn.executescript(INDEX_SQL)
    _ensure_migration_table(conn)
    _record_schema_version(conn, SCHEMA_VERSION)
    _set_user_version(conn, SCHEMA_VERSION)
    conn.commit()


def migrate_schema(conn: sqlite3.Connection, target_version: int = SCHEMA_VERSION) -> None:
    """현재 SQLite DB를 target_version까지 순방향으로 마이그레이션한다."""
    conn.executescript(PRAGMA_SQL)
    _ensure_migration_table(conn)

    current_version = get_schema_version(conn)
    if current_version > target_version:
        raise RuntimeError(
            f"database schema version {current_version} is newer than target {target_version}"
        )

    if current_version == 0:
        initialize_schema(conn)
        current_version = SCHEMA_VERSION

    while current_version < target_version:
        next_version = current_version + 1
        migration_sql = MIGRATIONS.get(next_version)
        if migration_sql is None:
            raise RuntimeError(f"missing migration for schema version {next_version}")

        conn.executescript(migration_sql)
        _record_schema_version(conn, next_version)
        _set_user_version(conn, next_version)
        current_version = next_version

    conn.commit()


def get_schema_version(conn: sqlite3.Connection) -> int:
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def _ensure_migration_table(conn: sqlite3.Connection) -> None:
    conn.executescript(MIGRATION_TABLE_SQL)


def _record_schema_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations (version) VALUES (?)",
        (version,),
    )


def _set_user_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(f"PRAGMA user_version = {int(version)}")
