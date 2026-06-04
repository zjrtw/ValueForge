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
from contextlib import suppress
from datetime import date
from pathlib import Path

import pandas as pd

from src.collectors.dart_financials import fetch_financial_statements, fetch_company_metadata
from src.collectors.krx_prices import fetch_daily_price_data
from src.collectors.krx_tickers import fetch_ticker_list
from src.collectors.market_ratios import calculate_market_ratios
from src.db.repository import Repository
from src.screening.stage1_filter import stage1_filter
from src.screening.stage2_scorer import stage2_score
from src.screening.stage3_trap_detector import FLAG_SPECS, stage3_detect_traps
from src.screening.stage4_ranker import stage4_rank
from src.screening.stage5_ai_analysis import stage5_ai_analysis
from src.storage.uploader import R2Uploader
from src.utils.config import settings
from src.utils.error_handling import check_collection_threshold
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
        tickers, n_collected, n_errors = _collect(repo, run_date)
        stats.update(
            stocks_collected=n_collected,
            stocks_with_data=n_collected - n_errors,
            collection_errors=n_errors,
        )
        check_collection_threshold(n_collected - n_errors, n_collected)

        # ── Phase 2: 스크리닝 ───────────────────────────────────────────────
        stage3_all, ranked = _screen(repo, run_date)
        stats.update(
            stage1_pass_count=len(stage3_all),
            stage2_score_count=len(stage3_all),
            stage3_trap_count=int(stage3_all["is_value_trap"].sum()),
            final_candidates=len(ranked),
        )

        # ── Phase 3: 결과 저장 ─────────────────────────────────────────────
        _write_results(repo, run_date, stage3_all, ranked)

        # ── Phase 3-5: Stage 5 AI 정성 분석 (GEMINI_API_KEY 설정 시 실행) ──
        ai_insights_count = _run_stage5(conn, ranked, run_date.isoformat())
        stats["ai_insights_count"] = ai_insights_count

        # ── Phase 4: VACUUM / ANALYZE ──────────────────────────────────────
        conn.execute("VACUUM")
        conn.execute("ANALYZE")
        conn.commit()
        log.info("pipeline_db_optimized")

        db_stats = {k: v for k, v in stats.items() if k != "ai_insights_count"}
        repo.record_run_success(run_date, **db_stats)
        log.info("pipeline_success", run_date=run_date.isoformat(), **stats)

        # ── Phase 5: R2 업로드 ─────────────────────────────────────────────
        if upload and len(ranked) > 0:
            _upload(run_date, _db_path, ranked, stats)
        elif upload and len(ranked) == 0:
            log.warning("pipeline_skipped_upload_no_candidates", run_date=run_date.isoformat())

        return stats

    except Exception as exc:
        log.error("pipeline_failed", error=str(exc))
        with suppress(Exception):
            repo.record_run_failure(
                run_date,
                str(exc),
                stocks_collected=stats.get("stocks_collected", 0),
                stocks_with_data=stats.get("stocks_with_data", 0),
                collection_errors=stats.get("collection_errors", 0),
            )
        raise

    finally:
        conn.close()
        # DB 삭제 정책
        # PRESERVE_DB=False (기본): db_path가 None이면 삭제 (로컬 테스트)
        # PRESERVE_DB=True: DB 항상 유지 (운영 환경, 캐시 활용)
        should_delete = (db_path is None and not settings.PRESERVE_DB)
        if should_delete and _db_path.exists():
            _db_path.unlink()
            log.info("pipeline_temp_db_removed", path=str(_db_path))
        elif db_path is None and settings.PRESERVE_DB and _db_path.exists():
            log.info("pipeline_db_preserved", path=str(_db_path))


# ---------------------------------------------------------------------------
# 내부 Phase 함수
# ---------------------------------------------------------------------------


def _collect(
    repo: Repository,
    run_date: date,
) -> tuple[pd.DataFrame, int, int]:
    """수집 단계: tickers → prices → fundamentals."""
    # 1. 종목 코드 (listing_date, shares_outstanding 포함)
    log.info("collect_tickers_start")
    tickers = fetch_ticker_list(run_date.isoformat())
    log.info("collect_tickers_done", count=len(tickers))

    # 1-1. stocks 선삽입 — prices FK 제약 충족을 위해 기본 정보로 먼저 저장
    repo.upsert_stocks(tickers)

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

    # 4. DART에서 회사 정보 및 업종 정보 수집
    log.info("collect_company_metadata_start")
    company_meta = fetch_company_metadata(tickers)
    if not company_meta.empty:
        # tickers에 sector 정보 병합
        meta_sector = company_meta[["stock_code", "sector"]].copy()
        tickers = tickers.merge(meta_sector, on="stock_code", how="left", suffixes=("", "_meta"))
        # 새로 수집한 sector가 있으면 사용, 없으면 기존 값 유지
        if "sector_meta" in tickers.columns:
            tickers["sector"] = tickers["sector_meta"].fillna(tickers["sector"])
            tickers = tickers.drop(columns=["sector_meta"])
        log.info("collect_company_metadata_done", count=len(company_meta), sector_updated=(tickers["sector"] != "Unknown").sum())
    else:
        log.warning("collect_company_metadata_empty")

    repo.upsert_stocks(tickers)

    # 3. DART 재무 데이터
    log.info("collect_fundamentals_start")
    fundamentals = fetch_financial_statements(tickers, conn=repo.conn)
    if not fundamentals.empty:
        # bps가 없으면 자체 계산 (total_equity / shares_outstanding)
        fundamentals = _calculate_missing_bps(fundamentals, tickers)
        repo.upsert_fundamentals(fundamentals)
        log.info("collect_fundamentals_done", count=len(fundamentals))
    else:
        log.warning("collect_fundamentals_empty")

    # 4. 시장 배수 계산 (PER, PBR, 배당수익률)
    if not prices.empty and not fundamentals.empty:
        log.info("calculate_market_ratios_start")
        ratios = calculate_market_ratios(prices, fundamentals)
        if not ratios.empty:
            # 디버그: per/pbr 값 확인
            per_not_null = ratios["per"].notna().sum()
            pbr_not_null = ratios["pbr"].notna().sum()
            log.info("calculate_market_ratios_debug", total=len(ratios), per_valid=per_not_null, pbr_valid=pbr_not_null)

            repo.update_prices_ratios(ratios)
            log.info("calculate_market_ratios_done", count=len(ratios))
        else:
            log.warning("calculate_market_ratios_empty")
    else:
        log.warning("calculate_market_ratios_skipped", prices_empty=prices.empty, fundamentals_empty=fundamentals.empty)

    return tickers, n_collected, n_errors


def _screen(
    repo: Repository,
    run_date: date,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """스크리닝 단계: Stage 1 → 2 → 3 → 4."""
    dataset = repo.get_screening_dataset(run_date)
    log.info("screen_dataset_loaded", rows=len(dataset))

    # 다년도 재무 컬럼 추가 (Stage 3 함정 감지용)
    dataset = _enrich_multiyear(dataset, repo.conn)

    # YoY 성장률 컬럼 추가 (Stage 2 성장 점수 계산용)
    from src.scoring.growth_scorer import add_yoy_growth_columns

    dataset = add_yoy_growth_columns(dataset)

    # 모멘텀 수익률 계산 (가격 이력 필요)
    momentum_df = _calculate_momentum_returns(dataset, repo.conn)
    dataset = dataset.merge(
        momentum_df[["stock_code", "return_6m", "return_3m", "return_1m"]],
        on="stock_code",
        how="left"
    )
    log.info("growth_momentum_calculated", growth_cols_added=True, momentum_cols_added=True)

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
    # sector, market 등 필수 메타데이터를 stocks 테이블에서 보충
    rankings_df = _build_rankings_df(ranked, run_date_str, repo.conn)
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


def _calculate_momentum_returns(
    dataset: pd.DataFrame,
    conn: sqlite3.Connection,
) -> pd.DataFrame:
    """각 종목의 가격 이력에서 모멘텀 수익률(6M, 3M, 1M)을 계산한다."""
    codes = dataset["stock_code"].unique().tolist()
    if not codes:
        return pd.DataFrame(columns=["stock_code", "return_6m", "return_3m", "return_1m"])

    placeholders = ",".join(["?"] * len(codes))
    query = f"""
        SELECT stock_code, date, close
        FROM prices
        WHERE stock_code IN ({placeholders})
        ORDER BY stock_code, date DESC
    """
    prices_df = pd.read_sql_query(query, conn, params=codes)

    if prices_df.empty:
        result = pd.DataFrame({"stock_code": codes})
        for col in ["return_6m", "return_3m", "return_1m"]:
            result[col] = None
        return result

    from src.scoring.momentum_scorer import latest_momentum_returns

    # 모멘텀 수익률 계산
    momentum_df = latest_momentum_returns(prices_df)
    return momentum_df[["stock_code", "return_6m", "return_3m", "return_1m"]]


def _calculate_missing_bps(
    fundamentals: pd.DataFrame,
    tickers: pd.DataFrame,
) -> pd.DataFrame:
    """bps(주당순자산)가 없으면 total_equity / shares_outstanding으로 계산한다."""
    result = fundamentals.copy()

    # bps가 없는 행 찾기
    missing_bps = result["bps"].isna() & result["total_equity"].notna()
    if not missing_bps.any():
        return result

    # tickers의 shares_outstanding merge
    ticker_shares = tickers[["stock_code", "shares_outstanding"]].copy()
    result = result.merge(ticker_shares, on="stock_code", how="left")

    # bps 계산
    result.loc[missing_bps, "bps"] = (
        result.loc[missing_bps, "total_equity"] / result.loc[missing_bps, "shares_outstanding"]
    )

    # shares_outstanding 컬럼 제거 (fundamentals 테이블에는 필요 없음)
    result = result.drop(columns=["shares_outstanding"], errors="ignore")

    log.info("bps_calculated", calculated=missing_bps.sum())
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


def _build_rankings_df(ranked: pd.DataFrame, run_date_str: str, conn: sqlite3.Connection) -> pd.DataFrame:
    df = ranked.copy()
    df["run_date"] = run_date_str
    df["rank"] = df["final_rank"]
    market_cap = df["market_cap"] if "market_cap" in df.columns else pd.Series(0, index=df.index)
    df["market_cap_b"] = pd.to_numeric(market_cap, errors="coerce") / 1e9
    critical_flags = df["critical_flag_count"] if "critical_flag_count" in df.columns else pd.Series(0, index=df.index)
    high_flags = df["high_flag_count"] if "high_flag_count" in df.columns else pd.Series(0, index=df.index)
    medium_flags = df["medium_flag_count"] if "medium_flag_count" in df.columns else pd.Series(0, index=df.index)
    low_flags = df["low_flag_count"] if "low_flag_count" in df.columns else pd.Series(0, index=df.index)
    df["risk_flag_count"] = (
        pd.to_numeric(critical_flags, errors="coerce").fillna(0)
        + pd.to_numeric(high_flags, errors="coerce").fillna(0)
        + pd.to_numeric(medium_flags, errors="coerce").fillna(0)
        + pd.to_numeric(low_flags, errors="coerce").fillna(0)
    ).astype(int)
    df["highest_severity"] = [_highest_severity(row) for _, row in df.iterrows()]

    # stocks 테이블에서 stock_name, market, sector를 보충
    # (stage 거치면서 손실될 수 있으므로 명시적으로 재추가)
    if "stock_code" in df.columns:
        stocks_info = pd.read_sql_query(
            "SELECT stock_code, stock_name, market, sector FROM stocks",
            conn,
        )
        # 기존 값을 유지하면서 NULL인 부분만 채우기
        for col in ["stock_name", "market", "sector"]:
            if col not in df.columns:
                df = df.merge(
                    stocks_info[["stock_code", col]],
                    on="stock_code",
                    how="left",
                )
            else:
                # 기존 값이 NULL이면 stocks 테이블 값으로 채우기
                stocks_merge = stocks_info[["stock_code", col]].rename(columns={col: f"{col}_from_stocks"})
                df = df.merge(stocks_merge, on="stock_code", how="left")
                df[col] = df[col].fillna(df[f"{col}_from_stocks"])
                df = df.drop(columns=[f"{col}_from_stocks"])

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


def _run_stage5(
    conn: sqlite3.Connection,
    ranked: pd.DataFrame,
    run_date_str: str,
) -> int:
    """Stage 5 AI 분석을 실행하고 저장된 인사이트 수를 반환한다.

    실패해도 예외를 전파하지 않아 전체 파이프라인이 중단되지 않는다.
    """
    try:
        count = stage5_ai_analysis(ranked, conn, run_date_str)
        if count > 0:
            log.info("stage5_done", ai_insights_saved=count)
        return count
    except Exception as exc:
        log.warning("stage5_failed", error=str(exc))
        return 0


def _default_db_path(run_date: date) -> Path:
    tmp = Path(tempfile.gettempdir())
    return tmp / _DB_FILENAME_TEMPLATE.format(date=run_date.isoformat())


def _resolve_date(date_str: str | None) -> date:
    if date_str is None or date_str.lower() == "today":
        return date.today()
    return date.fromisoformat(date_str)


def _parse_args() -> argparse.Namespace:
    import os
    parser = argparse.ArgumentParser(description="ValueForge 스크리닝 파이프라인")
    parser.add_argument(
        "--date",
        default="today",
        help="실행 기준일 (YYYY-MM-DD 또는 'today'). 기본값: today",
    )
    # GitHub Actions(CI 환경)에서만 업로드, 로컬에서는 기본 비활성화
    default_no_upload = not os.getenv("CI", "").lower() in ("true", "1")
    parser.add_argument(
        "--no-upload",
        action="store_true",
        default=default_no_upload,
        help="R2 업로드를 건너뛴다 (로컬 테스트용, 기본값: True)",
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="DB 파일 저장 경로 (지정 시 파이프라인 종료 후 파일 유지)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# CLI 진입점
# ---------------------------------------------------------------------------


def main() -> None:
    args = _parse_args()
    run_date = _resolve_date(args.date)
    upload = not args.no_upload
    db_path = Path(args.db_path) if args.db_path else None

    if not is_trading_day(run_date):
        log.info("pipeline_skipped_non_trading_day", run_date=run_date.isoformat())
        sys.exit(0)

    try:
        stats = run_pipeline(run_date, upload=upload, db_path=db_path)
        log.info("pipeline_complete", **stats)
        sys.exit(0)
    except Exception as exc:
        log.error("pipeline_aborted", error=str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
