"""Streamlit 데이터 캐싱 레이어.

Streamlit Cloud에서 무거운 연산을 하지 않는다.
사전 연산된 SQLite 데이터를 조회·반환만 한다.
"""
from __future__ import annotations

import sqlite3

import pandas as pd
import streamlit as st

from src.storage.downloader import download_latest_db, get_metadata


@st.cache_resource(ttl=1800)
def get_db_connection() -> sqlite3.Connection:
    """R2에서 latest.db를 30분마다 1회 다운로드 후 읽기 전용 연결을 반환한다."""
    db_path = download_latest_db()
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
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
