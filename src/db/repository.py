import json
import sqlite3
from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

import pandas as pd

from src.db.schema import initialize_schema

STOCK_COLUMNS = [
    "stock_code",
    "stock_name",
    "stock_name_en",
    "market",
    "sector",
    "industry",
    "listing_date",
    "shares_outstanding",
    "is_active",
]

PRICE_COLUMNS = [
    "stock_code",
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "market_cap",
    "per",
    "pbr",
    "dividend_yield",
]

FUNDAMENTAL_COLUMNS = [
    "stock_code",
    "fiscal_year",
    "fiscal_quarter",
    "revenue",
    "gross_profit",
    "operating_profit",
    "ebitda",
    "net_profit",
    "total_assets",
    "current_assets",
    "cash_and_equiv",
    "total_liabilities",
    "current_liabilities",
    "total_equity",
    "total_debt",
    "operating_cf",
    "capex",
    "free_cash_flow",
    "eps",
    "bps",
    "dps",
    "roe",
    "roa",
    "gross_margin",
    "operating_margin",
    "net_margin",
    "debt_to_equity",
    "current_ratio",
    "interest_coverage",
    "data_source",
]

SCORE_COLUMNS = [
    "stock_code",
    "run_date",
    "stage1_pass",
    "value_score",
    "quality_score",
    "safety_score",
    "growth_score",
    "momentum_score",
    "composite_score",
    "is_value_trap",
    "trap_flag_count",
    "final_rank",
]

RANKING_COLUMNS = [
    "run_date",
    "rank",
    "stock_code",
    "stock_name",
    "market",
    "sector",
    "composite_score",
    "value_score",
    "quality_score",
    "safety_score",
    "growth_score",
    "momentum_score",
    "market_cap_b",
    "per",
    "pbr",
    "roe",
    "dividend_yield",
    "debt_to_equity",
    "risk_flag_count",
    "highest_severity",
]

RISK_FLAG_COLUMNS = [
    "stock_code",
    "run_date",
    "flag_type",
    "flag_description",
    "severity",
    "metric_value",
    "threshold_value",
]

AI_INSIGHT_COLUMNS = [
    "ticker",
    "run_date",
    "guide_text",
    "sentiment",
    "generated_at",
    "model_used",
]


class Repository:
    """ValueForge SQLite 쓰기 저장소."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        initialize_schema(self.conn)

    def upsert_stocks(self, rows: pd.DataFrame | Iterable[Mapping[str, Any]]) -> int:
        records = _records(rows, STOCK_COLUMNS, defaults={"is_active": 1})
        if not records:
            return 0

        self.conn.executemany(
            """
            INSERT INTO stocks (
                stock_code, stock_name, stock_name_en, market, sector, industry,
                listing_date, shares_outstanding, is_active
            )
            VALUES (
                :stock_code, :stock_name, :stock_name_en, :market, :sector, :industry,
                :listing_date, :shares_outstanding, :is_active
            )
            ON CONFLICT(stock_code) DO UPDATE SET
                stock_name = excluded.stock_name,
                stock_name_en = COALESCE(excluded.stock_name_en, stocks.stock_name_en),
                market = excluded.market,
                sector = COALESCE(excluded.sector, stocks.sector),
                industry = COALESCE(excluded.industry, stocks.industry),
                listing_date = COALESCE(excluded.listing_date, stocks.listing_date),
                shares_outstanding = COALESCE(excluded.shares_outstanding, stocks.shares_outstanding),
                is_active = excluded.is_active,
                updated_at = datetime('now')
            """,
            records,
        )
        self.conn.commit()
        return len(records)

    def update_stock_metadata(self, rows: pd.DataFrame | Iterable[Mapping[str, Any]]) -> int:
        """기존 stocks 행의 메타데이터(listing_date, industry)만 UPDATE한다.

        INSERT를 시도하지 않으므로 stock_name NOT NULL 제약과 충돌하지 않는다.
        """
        raw_records = rows.to_dict("records") if isinstance(rows, pd.DataFrame) else list(rows)
        if not raw_records:
            return 0

        params = [
            (
                _clean_value(r.get("stock_name_en")),
                _clean_value(r.get("industry")),
                _clean_value(r.get("listing_date")),
                _clean_value(r.get("shares_outstanding")),
                str(r["stock_code"]).zfill(6),
            )
            for r in raw_records
        ]
        self.conn.executemany(
            """
            UPDATE stocks SET
                stock_name_en     = COALESCE(?, stock_name_en),
                industry          = COALESCE(?, industry),
                listing_date      = COALESCE(?, listing_date),
                shares_outstanding = COALESCE(?, shares_outstanding),
                updated_at        = datetime('now')
            WHERE stock_code = ?
            """,
            params,
        )
        self.conn.commit()
        return len(params)

    def upsert_prices(self, rows: pd.DataFrame | Iterable[Mapping[str, Any]]) -> int:
        records = _records(rows, PRICE_COLUMNS)
        if not records:
            return 0

        self.conn.executemany(
            """
            INSERT INTO prices (
                stock_code, date, open, high, low, close, volume,
                market_cap, per, pbr, dividend_yield
            )
            VALUES (
                :stock_code, :date, :open, :high, :low, :close, :volume,
                :market_cap, :per, :pbr, :dividend_yield
            )
            ON CONFLICT(stock_code, date) DO UPDATE SET
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                volume = excluded.volume,
                market_cap = excluded.market_cap,
                per = excluded.per,
                pbr = excluded.pbr,
                dividend_yield = excluded.dividend_yield
            """,
            records,
        )
        self.conn.commit()
        return len(records)

    def update_prices_ratios(self, rows: pd.DataFrame | Iterable[Mapping[str, Any]]) -> int:
        """기존 prices 행의 per, pbr, dividend_yield를 업데이트한다."""
        records = _records(rows, ["stock_code", "date", "per", "pbr", "dividend_yield"])
        if not records:
            return 0

        self.conn.executemany(
            """
            UPDATE prices
            SET per = :per, pbr = :pbr, dividend_yield = :dividend_yield
            WHERE stock_code = :stock_code AND date = :date
            """,
            records,
        )
        self.conn.commit()
        return len(records)

    def upsert_fundamentals(self, rows: pd.DataFrame | Iterable[Mapping[str, Any]]) -> int:
        records = _records(
            rows,
            FUNDAMENTAL_COLUMNS,
            defaults={"fiscal_quarter": 0, "data_source": "dart"},
        )
        for record in records:
            if record["fiscal_quarter"] is None:
                record["fiscal_quarter"] = 0
        if not records:
            return 0

        self.conn.executemany(
            """
            INSERT INTO fundamentals (
                stock_code, fiscal_year, fiscal_quarter, revenue, gross_profit,
                operating_profit, ebitda, net_profit, total_assets, current_assets,
                cash_and_equiv, total_liabilities, current_liabilities, total_equity,
                total_debt, operating_cf, capex, free_cash_flow, eps, bps, dps,
                roe, roa, gross_margin, operating_margin, net_margin, debt_to_equity,
                current_ratio, interest_coverage, data_source
            )
            VALUES (
                :stock_code, :fiscal_year, :fiscal_quarter, :revenue, :gross_profit,
                :operating_profit, :ebitda, :net_profit, :total_assets, :current_assets,
                :cash_and_equiv, :total_liabilities, :current_liabilities, :total_equity,
                :total_debt, :operating_cf, :capex, :free_cash_flow, :eps, :bps, :dps,
                :roe, :roa, :gross_margin, :operating_margin, :net_margin, :debt_to_equity,
                :current_ratio, :interest_coverage, :data_source
            )
            ON CONFLICT(stock_code, fiscal_year, fiscal_quarter) DO UPDATE SET
                revenue = excluded.revenue,
                gross_profit = excluded.gross_profit,
                operating_profit = excluded.operating_profit,
                ebitda = excluded.ebitda,
                net_profit = excluded.net_profit,
                total_assets = excluded.total_assets,
                current_assets = excluded.current_assets,
                cash_and_equiv = excluded.cash_and_equiv,
                total_liabilities = excluded.total_liabilities,
                current_liabilities = excluded.current_liabilities,
                total_equity = excluded.total_equity,
                total_debt = excluded.total_debt,
                operating_cf = excluded.operating_cf,
                capex = excluded.capex,
                free_cash_flow = excluded.free_cash_flow,
                eps = excluded.eps,
                bps = excluded.bps,
                dps = excluded.dps,
                roe = excluded.roe,
                roa = excluded.roa,
                gross_margin = excluded.gross_margin,
                operating_margin = excluded.operating_margin,
                net_margin = excluded.net_margin,
                debt_to_equity = excluded.debt_to_equity,
                current_ratio = excluded.current_ratio,
                interest_coverage = excluded.interest_coverage,
                data_source = excluded.data_source,
                collected_at = datetime('now', '+9 hours')
            """,
            records,
        )
        self.conn.commit()
        return len(records)

    def get_screening_dataset(self, run_date: str | date | None = None) -> pd.DataFrame:
        """Stage 1과 후속 스코어링 입력용 병합 데이터셋을 반환한다.

        활성 종목을 기준으로 최신 가격 스냅샷과 최신 연간 재무 데이터를 붙인다.
        ``run_date``가 주어지면 해당 날짜 이하의 가격만 대상으로 한다.
        """
        params: dict[str, Any] = {"run_date": None}
        price_date_filter = ""
        if run_date is not None:
            params["run_date"] = run_date.isoformat() if isinstance(run_date, date) else run_date
            price_date_filter = "WHERE date <= :run_date"

        query = f"""
            WITH avg_trading_value AS (
                SELECT
                    stock_code,
                    AVG(close * volume) AS avg_trading_value_20d
                FROM (
                    SELECT
                        stock_code, close, volume,
                        ROW_NUMBER() OVER (
                            PARTITION BY stock_code ORDER BY date DESC
                        ) AS rn
                    FROM prices
                )
                WHERE rn <= 20
                GROUP BY stock_code
            ),
            latest_prices AS (
                SELECT *
                FROM (
                    SELECT
                        p.*,
                        ROW_NUMBER() OVER (
                            PARTITION BY p.stock_code
                            ORDER BY p.date DESC
                        ) AS rn
                    FROM prices p
                    {price_date_filter}
                )
                WHERE rn = 1
            ),
            latest_fundamentals AS (
                SELECT *
                FROM (
                    SELECT
                        f.*,
                        ROW_NUMBER() OVER (
                            PARTITION BY f.stock_code
                            ORDER BY f.fiscal_year DESC, f.fiscal_quarter DESC
                        ) AS rn
                    FROM fundamentals f
                    WHERE f.fiscal_quarter = 0
                )
                WHERE rn = 1
            )
            SELECT
                s.stock_code,
                s.stock_name,
                s.stock_name_en,
                s.market,
                s.sector,
                s.industry,
                s.listing_date,
                s.shares_outstanding,
                s.is_active,
                CASE
                    WHEN s.listing_date IS NULL THEN NULL
                    ELSE CAST(julianday(COALESCE(:run_date, lp.date, date('now'))) - julianday(s.listing_date) AS INTEGER)
                END AS listing_days,
                av.avg_trading_value_20d,
                lp.date AS price_date,
                lp.open,
                lp.high,
                lp.low,
                lp.close,
                lp.volume,
                lp.market_cap,
                lp.per,
                lp.pbr,
                lp.dividend_yield,
                lf.fiscal_year,
                lf.fiscal_quarter,
                lf.revenue,
                lf.gross_profit,
                lf.operating_profit,
                lf.ebitda,
                lf.net_profit,
                lf.total_assets,
                lf.current_assets,
                lf.cash_and_equiv,
                lf.total_liabilities,
                lf.current_liabilities,
                lf.total_equity,
                lf.total_debt,
                lf.operating_cf,
                lf.capex,
                lf.free_cash_flow,
                lf.eps,
                lf.bps,
                lf.dps,
                lf.roe,
                lf.roa,
                lf.gross_margin,
                lf.operating_margin,
                lf.net_margin,
                lf.debt_to_equity,
                lf.current_ratio,
                lf.interest_coverage,
                lf.data_source
            FROM stocks s
            LEFT JOIN avg_trading_value av ON av.stock_code = s.stock_code
            LEFT JOIN latest_prices lp ON lp.stock_code = s.stock_code
            LEFT JOIN latest_fundamentals lf ON lf.stock_code = s.stock_code
            WHERE s.is_active = 1
            ORDER BY s.market, s.stock_code
        """
        return pd.read_sql_query(query, self.conn, params=params)

    def upsert_scores(self, rows: pd.DataFrame | Iterable[Mapping[str, Any]]) -> int:
        records = _records(
            rows,
            SCORE_COLUMNS,
            defaults={"stage1_pass": 0, "is_value_trap": 0, "trap_flag_count": 0},
        )
        if not records:
            return 0

        self.conn.executemany(
            """
            INSERT INTO scores (
                stock_code, run_date, stage1_pass, value_score, quality_score,
                safety_score, growth_score, momentum_score, composite_score,
                is_value_trap, trap_flag_count, final_rank
            )
            VALUES (
                :stock_code, :run_date, :stage1_pass, :value_score, :quality_score,
                :safety_score, :growth_score, :momentum_score, :composite_score,
                :is_value_trap, :trap_flag_count, :final_rank
            )
            ON CONFLICT(stock_code, run_date) DO UPDATE SET
                stage1_pass = excluded.stage1_pass,
                value_score = excluded.value_score,
                quality_score = excluded.quality_score,
                safety_score = excluded.safety_score,
                growth_score = excluded.growth_score,
                momentum_score = excluded.momentum_score,
                composite_score = excluded.composite_score,
                is_value_trap = excluded.is_value_trap,
                trap_flag_count = excluded.trap_flag_count,
                final_rank = excluded.final_rank
            """,
            records,
        )
        self.conn.commit()
        return len(records)

    def upsert_rankings(self, rows: pd.DataFrame | Iterable[Mapping[str, Any]]) -> int:
        records = _records(rows, RANKING_COLUMNS, defaults={"risk_flag_count": 0})
        if not records:
            return 0

        self.conn.executemany(
            """
            INSERT INTO rankings (
                run_date, rank, stock_code, stock_name, market, sector,
                composite_score, value_score, quality_score, safety_score,
                growth_score, momentum_score, market_cap_b, per, pbr, roe,
                dividend_yield, debt_to_equity, risk_flag_count, highest_severity
            )
            VALUES (
                :run_date, :rank, :stock_code, :stock_name, :market, :sector,
                :composite_score, :value_score, :quality_score, :safety_score,
                :growth_score, :momentum_score, :market_cap_b, :per, :pbr, :roe,
                :dividend_yield, :debt_to_equity, :risk_flag_count, :highest_severity
            )
            ON CONFLICT(run_date, stock_code) DO UPDATE SET
                rank = excluded.rank,
                stock_name = excluded.stock_name,
                market = excluded.market,
                sector = excluded.sector,
                composite_score = excluded.composite_score,
                value_score = excluded.value_score,
                quality_score = excluded.quality_score,
                safety_score = excluded.safety_score,
                growth_score = excluded.growth_score,
                momentum_score = excluded.momentum_score,
                market_cap_b = excluded.market_cap_b,
                per = excluded.per,
                pbr = excluded.pbr,
                roe = excluded.roe,
                dividend_yield = excluded.dividend_yield,
                debt_to_equity = excluded.debt_to_equity,
                risk_flag_count = excluded.risk_flag_count,
                highest_severity = excluded.highest_severity
            """,
            records,
        )
        self.conn.commit()
        return len(records)

    def upsert_risk_flags(self, rows: pd.DataFrame | Iterable[Mapping[str, Any]]) -> int:
        records = _records(rows, RISK_FLAG_COLUMNS)
        if not records:
            return 0

        keys = {(record["stock_code"], record["run_date"]) for record in records}
        with self.conn:
            self.conn.executemany(
                "DELETE FROM risk_flags WHERE stock_code = ? AND run_date = ?",
                sorted(keys),
            )
            self.conn.executemany(
                """
                INSERT INTO risk_flags (
                    stock_code, run_date, flag_type, flag_description, severity,
                    metric_value, threshold_value
                )
                VALUES (
                    :stock_code, :run_date, :flag_type, :flag_description, :severity,
                    :metric_value, :threshold_value
                )
                """,
                records,
            )
        return len(records)

    def upsert_ai_insights(self, rows: pd.DataFrame | Iterable[Mapping[str, Any]]) -> int:
        records = _records(rows, AI_INSIGHT_COLUMNS)
        if not records:
            return 0

        self.conn.executemany(
            """
            INSERT INTO ai_insights (
                ticker, run_date, guide_text, sentiment, generated_at, model_used
            )
            VALUES (
                :ticker, :run_date, :guide_text, :sentiment, :generated_at, :model_used
            )
            ON CONFLICT(ticker, run_date) DO UPDATE SET
                guide_text = excluded.guide_text,
                sentiment = excluded.sentiment,
                generated_at = excluded.generated_at,
                model_used = excluded.model_used
            """,
            records,
        )
        self.conn.commit()
        return len(records)

    def get_ai_insight(self, ticker: str, run_date: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT ticker, run_date, guide_text, sentiment, generated_at, model_used
            FROM ai_insights
            WHERE ticker = ? AND run_date = ?
            """,
            (ticker, run_date),
        ).fetchone()
        if row is None:
            return None
        return dict(zip(AI_INSIGHT_COLUMNS, row, strict=True))

    def record_run_start(
        self,
        run_date: str | date,
        pipeline_version: str | None = None,
    ) -> None:
        normalized_run_date = _normalize_date(run_date)
        now = _utc_now()
        self.conn.execute(
            """
            INSERT INTO pipeline_runs (
                run_date, started_at, status, pipeline_version, error_message, warnings
            )
            VALUES (?, ?, 'RUNNING', ?, NULL, NULL)
            ON CONFLICT(run_date) DO UPDATE SET
                started_at = excluded.started_at,
                completed_at = NULL,
                duration_seconds = NULL,
                status = 'RUNNING',
                stocks_collected = 0,
                stocks_with_data = 0,
                collection_errors = 0,
                stage1_pass_count = 0,
                stage2_score_count = 0,
                stage3_trap_count = 0,
                final_candidates = 0,
                pipeline_version = excluded.pipeline_version,
                error_message = NULL,
                warnings = NULL
            """,
            (normalized_run_date, now, pipeline_version),
        )
        self.conn.commit()

    def record_run_success(
        self,
        run_date: str | date,
        *,
        stocks_collected: int = 0,
        stocks_with_data: int = 0,
        collection_errors: int = 0,
        stage1_pass_count: int = 0,
        stage2_score_count: int = 0,
        stage3_trap_count: int = 0,
        final_candidates: int = 0,
        warnings: list[str] | None = None,
    ) -> None:
        self._record_run_finished(
            run_date,
            status="SUCCESS",
            stocks_collected=stocks_collected,
            stocks_with_data=stocks_with_data,
            collection_errors=collection_errors,
            stage1_pass_count=stage1_pass_count,
            stage2_score_count=stage2_score_count,
            stage3_trap_count=stage3_trap_count,
            final_candidates=final_candidates,
            error_message=None,
            warnings=warnings,
        )

    def record_run_failure(
        self,
        run_date: str | date,
        error_message: str,
        *,
        stocks_collected: int = 0,
        stocks_with_data: int = 0,
        collection_errors: int = 0,
        warnings: list[str] | None = None,
    ) -> None:
        self._record_run_finished(
            run_date,
            status="FAILED",
            stocks_collected=stocks_collected,
            stocks_with_data=stocks_with_data,
            collection_errors=collection_errors,
            stage1_pass_count=0,
            stage2_score_count=0,
            stage3_trap_count=0,
            final_candidates=0,
            error_message=error_message,
            warnings=warnings,
        )

    def _record_run_finished(
        self,
        run_date: str | date,
        *,
        status: str,
        stocks_collected: int,
        stocks_with_data: int,
        collection_errors: int,
        stage1_pass_count: int,
        stage2_score_count: int,
        stage3_trap_count: int,
        final_candidates: int,
        error_message: str | None,
        warnings: list[str] | None,
    ) -> None:
        normalized_run_date = _normalize_date(run_date)
        completed_at = _utc_now()
        started_at = self.conn.execute(
            "SELECT started_at FROM pipeline_runs WHERE run_date = ?",
            (normalized_run_date,),
        ).fetchone()
        started_at_value = started_at[0] if started_at else completed_at
        duration_seconds = _duration_seconds(started_at_value, completed_at)

        self.conn.execute(
            """
            INSERT INTO pipeline_runs (
                run_date, started_at, completed_at, duration_seconds, status,
                stocks_collected, stocks_with_data, collection_errors,
                stage1_pass_count, stage2_score_count, stage3_trap_count,
                final_candidates, error_message, warnings
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_date) DO UPDATE SET
                completed_at = excluded.completed_at,
                duration_seconds = excluded.duration_seconds,
                status = excluded.status,
                stocks_collected = excluded.stocks_collected,
                stocks_with_data = excluded.stocks_with_data,
                collection_errors = excluded.collection_errors,
                stage1_pass_count = excluded.stage1_pass_count,
                stage2_score_count = excluded.stage2_score_count,
                stage3_trap_count = excluded.stage3_trap_count,
                final_candidates = excluded.final_candidates,
                error_message = excluded.error_message,
                warnings = excluded.warnings
            """,
            (
                normalized_run_date,
                started_at_value,
                completed_at,
                duration_seconds,
                status,
                stocks_collected,
                stocks_with_data,
                collection_errors,
                stage1_pass_count,
                stage2_score_count,
                stage3_trap_count,
                final_candidates,
                error_message,
                json.dumps(warnings, ensure_ascii=False) if warnings is not None else None,
            ),
        )
        self.conn.commit()

    def get_cached_fundamental_pairs(
        self,
        codes: list[str],
        fiscal_years: list[int],
        ttl_days: int = 30,
    ) -> set[tuple[str, int]]:
        """TTL 이내에 수집된 (stock_code, fiscal_year) 쌍을 반환한다.

        반환된 쌍은 API 호출을 건너뛸 수 있는 캐시 HIT 목록이다.
        fiscal_quarter = 0 (연간)만 대상으로 한다.

        Args:
            codes: 조회 대상 종목 코드 리스트
            fiscal_years: 조회 대상 회계년도 리스트
            ttl_days: 캐시 유효 기간 (일), 기본값 30일

        Returns:
            TTL 이내에 수집된 (stock_code, fiscal_year) 튜플 집합
        """
        if not codes or not fiscal_years:
            return set()

        placeholders_codes = ",".join("?" * len(codes))
        placeholders_years = ",".join("?" * len(fiscal_years))

        rows = self.conn.execute(
            f"""
            SELECT DISTINCT stock_code, fiscal_year
            FROM fundamentals
            WHERE fiscal_quarter = 0
              AND stock_code IN ({placeholders_codes})
              AND fiscal_year IN ({placeholders_years})
              AND julianday('now') - julianday(collected_at) <= ?
            """,
            [*codes, *fiscal_years, ttl_days],
        ).fetchall()

        return {(str(row[0]), int(row[1])) for row in rows}

    def get_fundamentals_by_codes_years(
        self,
        code_year_pairs: list[tuple[str, int]],
    ) -> pd.DataFrame:
        """지정된 (stock_code, fiscal_year) 쌍의 재무 데이터를 조회한다.

        Args:
            code_year_pairs: (stock_code, fiscal_year) 튜플 리스트

        Returns:
            매칭되는 fundamentals 데이터
        """
        if not code_year_pairs:
            return pd.DataFrame(columns=FUNDAMENTAL_COLUMNS)

        # (code, year) 쌍을 WHERE 절로 변환
        conditions = " OR ".join(["(stock_code = ? AND fiscal_year = ? AND fiscal_quarter = 0)"] * len(code_year_pairs))
        params: list[str | int] = []
        for code, year in code_year_pairs:
            params.extend([str(code).zfill(6), int(year)])

        query = f"""
            SELECT {', '.join(FUNDAMENTAL_COLUMNS)}
            FROM fundamentals
            WHERE {conditions}
            ORDER BY stock_code, fiscal_year DESC
        """

        return pd.read_sql_query(query, self.conn, params=tuple(params))


def _records(
    rows: pd.DataFrame | Iterable[Mapping[str, Any]],
    columns: list[str],
    defaults: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    defaults = defaults or {}
    raw_records = rows.to_dict("records") if isinstance(rows, pd.DataFrame) else list(rows)

    records: list[dict[str, Any]] = []
    for raw in raw_records:
        record = {}
        for column in columns:
            value = raw.get(column, defaults.get(column))
            record[column] = _clean_value(value)
        records.append(record)
    return records


def _clean_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _normalize_date(value: str | date) -> str:
    return value.isoformat() if isinstance(value, date) else value


def _utc_now() -> str:
    kst = timezone(timedelta(hours=9))
    return datetime.now(kst).replace(microsecond=0).isoformat()


def _duration_seconds(started_at: str, completed_at: str) -> int:
    start = _parse_utc_timestamp(started_at)
    end = _parse_utc_timestamp(completed_at)
    return max(0, int((end - start).total_seconds()))


def _parse_utc_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
