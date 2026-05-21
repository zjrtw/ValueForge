"""ValueForge 파이프라인 오케스트레이터.

사용법:
    python -m src.pipeline.runner
    python -m src.pipeline.runner --date 2025-01-20
    MAX_TICKERS=50 python -m src.pipeline.runner --date today
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from src.collectors.dart_financials import fetch_financial_statements
from src.collectors.krx_prices import fetch_avg_trading_value_20d, fetch_daily_price_data
from src.collectors.krx_tickers import fetch_ticker_list
from src.db.repository import Repository
from src.screening.stage1_filter import stage1_filter
from src.screening.stage2_scorer import stage2_score
from src.screening.stage3_trap_detector import FLAG_SPECS, stage3_detect_traps
from src.screening.stage4_ranker import stage4_rank
from src.storage.uploader import R2Uploader
from src.utils.config import settings
from src.utils.error_handling import PipelineAbortError, check_collection_threshold
from src.utils.logger import get_logger
from src.utils.market_calendar import is_trading_day

log = get_logger(__name__)

PIPELINE_VERSION = "1.0.0"
_DB_FILENAME_TEMPLATE = "valueforge_{date}.db"


# ---------------------------------------------------------------------------
# 공개 진입점
# ---------------------------------------------------------------------------


def run_pipeline(
    run_date: date,
    *,
    db_path: Path | None = None,
    upload: bool = True,
) -> dict:
    """전체 파이프라인을 실행하고 통계 딕셔너리를 반환한다.

    1. 수집: tickers → prices → avg_volume → fundamentals
    2. 스크리닝: Stage 1 → 2 → 3 → 4
    3. 결과 저장: scores, risk_flags, rankings
    4. VACUUM / ANALYZE
    5. R2 업로드 (upload=True 시)
    """
    _db_path = db_path or _default_db_path(run_date)
    _db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(_db_path))
    repo = Repository(conn)
    stats: dict = {}

    try:
        repo.record_run_start(run_date, pipeline_version=PIPELINE_VERSION)
        log.info("pipeline_start", run_date=run_date.isoformat())

        # ── Phase 1: 수집 ──────────────────────────────────────────────────
        tickers, avg_vol, n_collected, n_errors = _collect(repo, run_date)
        stats.update(
            stocks_collected=n_collected,
            stocks_with_data=n_collected - n_errors,
            collection_errors=n_errors,
        )
        check_collection_threshold(n_collected - n_errors, n_collected)

        # ── Phase 2: 스크리닝 ───────────────────────────────────────────────
        stage3_all, ranked = _screen(repo, run_date, avg_vol)
        stats.update(
            stage1_pass_count=len(stage3_all),
            stage2_score_count=len(stage3_all),
            stage3_trap_count=int(stage3_all["is_value_trap"].sum()),
            final_candidates=len(ranked),
        )

        # ── Phase 3: 결과 저장 ─────────────────────────────────────────────
        _write_results(repo, run_date, stage3_all, ranked)

        # ── Phase 4: VACUUM / ANALYZE ──────────────────────────────────────
        conn.execute("VACUUM")
        conn.execute("ANALYZE")
        conn.commit()
        log.info("pipeline_db_optimized")

        # ── Phase 5: R2 업로드 ─────────────────────────────────────────────
        if upload:
            _upload(run_date, _db_path, ranked, stats)

        repo.record_run_success(run_date, **stats)
        log.info("pipeline_success", run_date=run_date.isoformat(), **stats)
        return stats

    except Exception as exc:
        log.error("pipeline_failed", error=str(exc))
        try:
            repo.record_run_failure(
                run_date,
                str(exc),
                stocks_collected=stats.get("stocks_collected", 0),
                stocks_with_data=stats.get("stocks_with_data", 0),
                collection_errors=stats.get("collection_errors", 0),
            )
        except Exception:
            pass
        raise

    finally:
        conn.close()
        if db_path is None and _db_path.exists():
            _db_path.unlink()
            log.info("pipeline_temp_db_removed", path=str(_db_path))


# ---------------------------------------------------------------------------
# 내부 Phase 함수
# ---------------------------------------------------------------------------


def _collect(
    repo: Repository,
    run_date: date,
) -> tuple[pd.DataFrame, pd.DataFrame, int, int]:
    """수집 단계: tickers → prices → avg_vol → fundamentals."""
    # 1. 종목 코드
    log.info("collect_tickers_start")
    tickers = fetch_ticker_list(run_date.isoformat())
    repo.upsert_stocks(tickers)
    log.info("collect_tickers_done", count=len(tickers))

    # 2. 일별 주가
    log.info("collect_prices_start")
    prices = fetch_daily_price_data(run_date, tickers)
    n_collected = len(tickers)
    n_errors = 0
    if not prices.empty:
        repo.upsert_prices(prices)
        log.info("collect_prices_done", count=len(prices))
    else:
        log.warning("collect_prices_empty")
        n_errors = n_collected

    # 3. 20일 평균 거래대금 (DB에 저장 안 함 — 스크리닝 시 병합)
    log.info("collect_avg_volume_start")
    avg_vol = fetch_avg_trading_value_20d(run_date, tickers)
    log.info("collect_avg_volume_done", count=len(avg_vol))

    # 4. DART 재무 데이터
    log.info("collect_fundamentals_start")
    fundamentals = fetch_financial_statements(tickers)
    if not fundamentals.empty:
        repo.upsert_fundamentals(fundamentals)
        log.info("collect_fundamentals_done", count=len(fundamentals))
    else:
        log.warning("collect_fundamentals_empty")

    return tickers, avg_vol, n_collected, n_errors


def _screen(
    repo: Repository,
    run_date: date,
    avg_vol: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """스크리닝 단계: Stage 1 → 2 → 3 → 4."""
    dataset = repo.get_screening_dataset(run_date)
    log.info("screen_dataset_loaded", rows=len(dataset))

    # avg_trading_value_20d 병합 (Stage 1 필터 조건, 아직 없을 때만)
    if (
        not avg_vol.empty
        and "avg_trading_value_20d" in avg_vol.columns
        and "avg_trading_value_20d" not in dataset.columns
    ):
        dataset = dataset.merge(
            avg_vol[["stock_code", "avg_trading_value_20d"]],
            on="stock_code",
            how="left",
        )

    # 다년도 재무 컬럼 추가 (Stage 3 함정 감지용)
    dataset = _enrich_multiyear(dataset, repo.conn)

    # Stage 1
    s1 = stage1_filter(dataset)
    log.info("stage1_done", pass_count=len(s1))

    # Stage 2
    s2 = stage2_score(s1)
    log.info("stage2_done")

    # Stage 3
    s3 = stage3_detect_traps(s2)
    trap_count = int(s3["is_value_trap"].sum())
    log.info("stage3_done", trap_count=trap_count)

    # Stage 4
    s4 = stage4_rank(s3)
    log.info("stage4_done", final_count=len(s4))

    return s3, s4


def _write_results(
    repo: Repository,
    run_date: date,
    stage3_all: pd.DataFrame,
    ranked: pd.DataFrame,
) -> None:
    """scores, risk_flags, rankings 테이블에 결과를 저장한다."""
    run_date_str = run_date.isoformat()

    # scores (Stage 1 통과 전 종목)
    scores_df = _build_scores_df(stage3_all, ranked, run_date_str)
    repo.upsert_scores(scores_df)
    log.info("scores_written", count=len(scores_df))

    # risk_flags (플래그 있는 종목)
    risk_rows = _build_risk_flags(stage3_all, run_date_str)
    if risk_rows:
        repo.upsert_risk_flags(risk_rows)
        log.info("risk_flags_written", count=len(risk_rows))

    # rankings (Stage 4 최종 순위)
    rankings_df = _build_rankings_df(ranked, run_date_str)
    repo.upsert_rankings(rankings_df)
    log.info("rankings_written", count=len(rankings_df))


def _upload(
    run_date: date,
    db_path: Path,
    ranked: pd.DataFrame,
    stats: dict,
) -> None:
    """R2 업로드 순서: backup → latest → metadata → cleanup."""
    uploader = R2Uploader()
    uploader.upload_backup(db_path, run_date)
    uploader.upload_latest(db_path)
    uploader.upload_metadata(
        run_date,
        db_path=db_path,
        stocks_collected=stats.get("stocks_collected", 0),
        stage1_pass=stats.get("stage1_pass_count", 0),
        stage3_trap_count=stats.get("stage3_trap_count", 0),
        final_candidates=stats.get("final_candidates", 0),
        ranked_df=ranked,
    )
    uploader.cleanup_old_backups()
    log.info("r2_upload_complete")


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------


def _enrich_multiyear(df: pd.DataFrame, conn: sqlite3.Connection) -> pd.DataFrame:
    """Stage 3 함정 감지용 다년도 컬럼(yr1/yr2/yr3)을 추가한다."""
    query = """
        SELECT stock_code, fiscal_year,
               operating_profit, free_cash_flow, operating_margin
        FROM fundamentals
        WHERE fiscal_quarter = 0
        ORDER BY stock_code, fiscal_year DESC
    """
    hist = pd.read_sql_query(query, conn)
    if hist.empty:
        return df

    hist["yr_rank"] = (
        hist.groupby("stock_code")["fiscal_year"]
        .rank(ascending=False, method="first")
        .astype(int)
    )
    hist = hist[hist["yr_rank"] <= 3]

    result = df.copy()
    for col, prefix in [
        ("operating_profit", "op_profit"),
        ("free_cash_flow", "fcf"),
        ("operating_margin", "op_margin"),
    ]:
        pivot = hist.pivot_table(
            index="stock_code", columns="yr_rank", values=col, aggfunc="first"
        )
        pivot.columns = [f"{prefix}_yr{int(c)}" for c in pivot.columns]
        result = result.merge(pivot.reset_index(), on="stock_code", how="left")

    return result


def _build_scores_df(
    stage3_all: pd.DataFrame,
    ranked: pd.DataFrame,
    run_date_str: str,
) -> pd.DataFrame:
    df = stage3_all.copy()
    df["run_date"] = run_date_str
    df["stage1_pass"] = 1
    df["trap_flag_count"] = (
        df.get("critical_flag_count", 0)
        + df.get("high_flag_count", 0)
        + df.get("medium_flag_count", 0)
        + df.get("low_flag_count", 0)
    )
    df["is_value_trap"] = df["is_value_trap"].astype(int)

    # final_rank: ranked 종목만 존재 (함정은 NULL)
    rank_map = ranked.set_index("stock_code")["final_rank"].to_dict()
    df["final_rank"] = df["stock_code"].map(rank_map)
    return df


def _build_risk_flags(
    stage3_all: pd.DataFrame,
    run_date_str: str,
) -> list[dict]:
    if "risk_flags" not in stage3_all.columns or stage3_all.empty:
        return []
    flag_by_name = {s.name: s for s in FLAG_SPECS}
    rows: list[dict] = []
    flagged = stage3_all[
        stage3_all["risk_flags"].fillna("").astype(str).str.len() > 0
    ]
    for _, row in flagged.iterrows():
        for flag_name in row["risk_flags"].split(","):
            flag_name = flag_name.strip()
            if not flag_name or flag_name not in flag_by_name:
                continue
            spec = flag_by_name[flag_name]
            rows.append({
                "stock_code": row["stock_code"],
                "run_date": run_date_str,
                "flag_type": flag_name,
                "flag_description": spec.description,
                "severity": spec.severity.value,
                "metric_value": None,
                "threshold_value": None,
            })
    return rows


def _build_rankings_df(ranked: pd.DataFrame, run_date_str: str) -> pd.DataFrame:
    df = ranked.copy()
    df["run_date"] = run_date_str
    df["rank"] = df["final_rank"]
    df["market_cap_b"] = pd.to_numeric(df.get("market_cap", None), errors="coerce") / 1e9
    df["risk_flag_count"] = (
        pd.to_numeric(df.get("critical_flag_count", 0), errors="coerce").fillna(0)
        + pd.to_numeric(df.get("high_flag_count", 0), errors="coerce").fillna(0)
        + pd.to_numeric(df.get("medium_flag_count", 0), errors="coerce").fillna(0)
        + pd.to_numeric(df.get("low_flag_count", 0), errors="coerce").fillna(0)
    ).astype(int)
    df["highest_severity"] = df.apply(_highest_severity, axis=1)
    return df


def _highest_severity(row: pd.Series) -> str | None:
    if pd.to_numeric(row.get("critical_flag_count", 0), errors="coerce") > 0:
        return "CRITICAL"
    if pd.to_numeric(row.get("high_flag_count", 0), errors="coerce") > 0:
        return "HIGH"
    if pd.to_numeric(row.get("medium_flag_count", 0), errors="coerce") > 0:
        return "MEDIUM"
    if pd.to_numeric(row.get("low_flag_count", 0), errors="coerce") > 0:
        return "LOW"
    return None


def _default_db_path(run_date: date) -> Path:
    tmp = Path(tempfile.gettempdir())
    return tmp / _DB_FILENAME_TEMPLATE.format(date=run_date.isoformat())


def _resolve_date(date_str: str | None) -> date:
    if date_str is None or date_str.lower() == "today":
        return date.today()
    return date.fromisoformat(date_str)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ValueForge 스크리닝 파이프라인")
    parser.add_argument(
        "--date",
        default="today",
        help="실행 기준일 (YYYY-MM-DD 또는 'today'). 기본값: today",
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="R2 업로드를 건너뛴다 (로컬 테스트용)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# CLI 진입점
# ---------------------------------------------------------------------------


def main() -> None:
    args = _parse_args()
    run_date = _resolve_date(args.date)
    upload = not args.no_upload

    if not is_trading_day(run_date):
        log.info("pipeline_skipped_non_trading_day", run_date=run_date.isoformat())
        sys.exit(0)

    try:
        stats = run_pipeline(run_date, upload=upload)
        log.info("pipeline_complete", **stats)
        sys.exit(0)
    except Exception as exc:
        log.error("pipeline_aborted", error=str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
