"""Streamlit 데이터 캐싱 레이어.

Streamlit Cloud에서 무거운 연산을 하지 않는다.
사전 연산된 SQLite 데이터를 조회·반환만 한다.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

from src.db.schema import migrate_schema
from src.storage.downloader import download_latest_db, get_metadata


@st.cache_resource(ttl=1800)
def get_db_connection() -> sqlite3.Connection:
    """로컬 DB 우선, 없으면 R2에서 다운로드 후 읽기 전용 연결을 반환한다."""
    # [안정성] 실행 위치(cwd)에 영향받지 않도록 파일 기준 절대 경로 사용
    project_root = Path(__file__).parents[2]
    local_pipeline_db = project_root / "data" / "valueforge_local.db"
    r2_cached_db = project_root / ".local" / "valueforge_latest.db"

    if local_pipeline_db.exists():
        db_path = str(local_pipeline_db)
    elif r2_cached_db.exists():
        db_path = str(r2_cached_db)
    else:
        db_path = str(download_latest_db())

    # [안정성] 스키마 마이그레이션 (ai_insights 테이블 등 누락 방지)
    # UI는 기본적으로 읽기 전용 권한일 수 있으나, 로컬 환경에서는 쓰기 권한이 필요할 수 있음
    # 여기서는 테이블 존재 여부만 보장하기 위해 마이그레이션 실행
    try:
        tmp_conn = sqlite3.connect(db_path)
        migrate_schema(tmp_conn)
        tmp_conn.close()
    except Exception:
        # 권한 문제 등으로 실패할 경우 로그만 남기고 진행
        pass

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@st.cache_data(ttl=1800)
def load_rankings(
    market: str | None = None,
    min_score: float = 0.0,
) -> pd.DataFrame:
    """최신 성공 실행의 랭킹 데이터를 반환한다.

    Args:
        market:    'KOSPI' | 'KOSDAQ' | None(전체).
        min_score: composite_score 하한값 (0–100).
    """
    conn = get_db_connection()
    query = """
        SELECT r.*, s.listing_date
        FROM rankings r
        JOIN stocks s ON r.stock_code = s.stock_code
        WHERE r.run_date = (
            SELECT MAX(run_date) FROM pipeline_runs WHERE status = 'SUCCESS'
        )
          AND r.composite_score >= ?
    """
    params: list = [min_score]
    if market:
        query += " AND r.market = ?"
        params.append(market)
    query += " ORDER BY r.rank ASC"
    return pd.read_sql_query(query, conn, params=params)


@st.cache_data(ttl=1800)
def load_scores_with_filters(
    market: str | None = None,
    min_score: float = 0.0,
    require_stage1: bool = True,
    exclude_value_trap: bool = True,
) -> pd.DataFrame:
    """scores 테이블에서 필터링된 데이터를 반환한다 (테스트용).

    Args:
        market: 'KOSPI' | 'KOSDAQ' | None(전체).
        min_score: composite_score 하한값.
        require_stage1: Stage1 통과 필수 여부.
        exclude_value_trap: 가치함정 제외 여부.
    """
    conn = get_db_connection()
    latest_run_date = conn.execute(
        "SELECT MAX(run_date) FROM pipeline_runs WHERE status = 'SUCCESS'"
    ).fetchone()[0]

    if not latest_run_date:
        return pd.DataFrame()

    query = """
        SELECT
            ROW_NUMBER() OVER (ORDER BY sc.composite_score DESC) as rank,
            sc.stock_code,
            st.stock_name,
            st.market,
            st.sector,
            sc.composite_score,
            sc.value_score,
            sc.quality_score,
            sc.safety_score,
            sc.growth_score,
            sc.momentum_score,
            sc.stage1_pass,
            sc.is_value_trap,
            pr.market_cap_b,
            pr.per,
            pr.pbr,
            pr.roe,
            pr.dividend_yield,
            pr.debt_to_equity,
            pr.risk_flag_count,
            pr.highest_severity,
            sc.run_date,
            st.listing_date
        FROM scores sc
        JOIN stocks st ON sc.stock_code = st.stock_code
        LEFT JOIN rankings pr ON sc.stock_code = pr.stock_code AND sc.run_date = pr.run_date
        WHERE sc.run_date = ?
          AND sc.composite_score >= ?
    """
    params: list = [latest_run_date, min_score]

    if require_stage1:
        query += " AND sc.stage1_pass = 1"

    if exclude_value_trap:
        query += " AND sc.is_value_trap = 0"

    if market:
        query += " AND st.market = ?"
        params.append(market)

    query += " ORDER BY sc.composite_score DESC"
    return pd.read_sql_query(query, conn, params=params)


@st.cache_data(ttl=1800)
def load_rankings_skip_stage1(
    market: str | None = None,
    min_score: float = 0.0,
) -> pd.DataFrame:
    """Stage1 필터를 무시하고 모든 점수를 반환한다 (테스트용).

    Args:
        market:    'KOSPI' | 'KOSDAQ' | None(전체).
        min_score: composite_score 하한값 (0–100).
    """
    conn = get_db_connection()
    latest_run_date = conn.execute(
        "SELECT MAX(run_date) FROM pipeline_runs WHERE status = 'SUCCESS'"
    ).fetchone()[0]

    if not latest_run_date:
        return pd.DataFrame()

    query = """
        SELECT
            ROW_NUMBER() OVER (ORDER BY sc.composite_score DESC) as rank,
            sc.stock_code,
            st.stock_name,
            st.market,
            st.sector,
            sc.composite_score,
            sc.value_score,
            sc.quality_score,
            sc.safety_score,
            sc.growth_score,
            sc.momentum_score,
            sc.stage1_pass,
            pr.market_cap_b,
            pr.per,
            pr.pbr,
            pr.roe,
            pr.dividend_yield,
            pr.debt_to_equity,
            pr.risk_flag_count,
            pr.highest_severity,
            sc.run_date,
            st.listing_date
        FROM scores sc
        JOIN stocks st ON sc.stock_code = st.stock_code
        LEFT JOIN rankings pr ON sc.stock_code = pr.stock_code AND sc.run_date = pr.run_date
        WHERE sc.run_date = ?
          AND sc.composite_score >= ?
    """
    params: list = [latest_run_date, min_score]
    if market:
        query += " AND st.market = ?"
        params.append(market)
    query += " ORDER BY sc.composite_score DESC"
    return pd.read_sql_query(query, conn, params=params)


@st.cache_data(ttl=1800)
def load_stock_detail(stock_code: str) -> dict[str, pd.DataFrame]:
    """종목 상세 데이터를 scores / flags / fundamentals / prices 딕셔너리로 반환한다."""
    conn = get_db_connection()
    return {
        "scores": pd.read_sql_query(
            "SELECT * FROM scores WHERE stock_code = ? ORDER BY run_date DESC LIMIT 1",
            conn,
            params=[stock_code],
        ),
        "flags": pd.read_sql_query(
            "SELECT * FROM risk_flags WHERE stock_code = ? ORDER BY run_date DESC",
            conn,
            params=[stock_code],
        ),
        "fundamentals": pd.read_sql_query(
            "SELECT * FROM fundamentals WHERE stock_code = ?"
            " ORDER BY fiscal_year DESC, fiscal_quarter DESC LIMIT 6",
            conn,
            params=[stock_code],
        ),
        "prices": pd.read_sql_query(
            "SELECT date, close, volume, per, pbr"
            " FROM prices WHERE stock_code = ? ORDER BY date DESC LIMIT 252",
            conn,
            params=[stock_code],
        ),
    }


@st.cache_data(ttl=300)
def load_metadata() -> dict:
    """latest_metadata.json을 반환한다. DB 다운로드 없이 신선도를 확인할 때 사용한다."""
    return get_metadata()


def get_latest_run_date(conn: sqlite3.Connection) -> str | None:
    """가장 최근 성공 실행 날짜를 반환한다 (없으면 None)."""
    row = conn.execute(
        "SELECT MAX(run_date) FROM pipeline_runs WHERE status = 'SUCCESS'"
    ).fetchone()
    return row[0] if row else None


@st.cache_data(ttl=1800)
def load_ai_insight(stock_code: str) -> dict | None:
    """종목의 최신 AI 인사이트(가이드)를 반환한다. 데이터 없으면 None."""
    conn = get_db_connection()
    try:
        row = conn.execute(
            """
            SELECT ticker, run_date, guide_text, sentiment, generated_at, model_used
            FROM ai_insights
            WHERE ticker = ?
            ORDER BY run_date DESC
            LIMIT 1
            """,
            (stock_code,),
        ).fetchone()
    except Exception:
        return None
    return dict(row) if row else None


@st.cache_data(ttl=1800)
def load_ai_analysis(stock_code: str) -> dict | None:
    """종목의 최신 종합 AI 분석을 반환한다. 데이터 없으면 None."""
    conn = get_db_connection()
    try:
        row = conn.execute(
            """
            SELECT stock_code, run_date, analysis_text, analysis_type, generated_at
            FROM ai_analysis
            WHERE stock_code = ?
            ORDER BY run_date DESC
            LIMIT 1
            """,
            (stock_code,),
        ).fetchone()
    except Exception:
        return None
    return dict(row) if row else None


@st.cache_data(ttl=300)
def load_pipeline_stats() -> list[dict]:
    """최신 파이프라인 실행 통계를 반환한다."""
    conn = get_db_connection()
    row = conn.execute(
        """
        SELECT
            run_date,
            started_at,
            completed_at,
            status,
            duration_seconds,
            stocks_collected,
            stocks_with_data,
            collection_errors,
            stage1_pass_count,
            stage2_score_count,
            stage3_trap_count,
            final_candidates,
            error_message
        FROM pipeline_runs
        WHERE status = 'SUCCESS'
        ORDER BY run_date DESC
        LIMIT 5
        """
    ).fetchall()

    if not row:
        return []

    return [dict(r) for r in row]
