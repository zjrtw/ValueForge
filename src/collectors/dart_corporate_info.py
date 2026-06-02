"""DART API를 통한 기업 공시 및 지배구조 정보 수집."""

from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from src.utils.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)


def fetch_disclosure_dates(
    tickers: pd.DataFrame | None = None,
    client: Any | None = None,
) -> pd.DataFrame:
    """각 종목의 최근 공시 정보를 수집한다.

    반환 컬럼: stock_code, latest_disclosure_date, disclosure_delay_days

    - latest_disclosure_date: 가장 최근 공시일 (연간 재무제표 기준)
    - disclosure_delay_days: 공시 지연 일수 (오늘로부터 며칠 이전인지)
    """
    if client is None:
        try:
            from opendartreader import OpenDartReader
            client = OpenDartReader(settings.DART_API_KEY)
        except Exception:
            log.warning("disclosure date fetch skipped: no DART client")
            return pd.DataFrame(columns=["stock_code", "latest_disclosure_date", "disclosure_delay_days"])

    if tickers is None:
        from src.collectors.krx_tickers import fetch_ticker_list
        tickers = fetch_ticker_list()

    codes = tickers["stock_code"].astype(str).str.zfill(6).tolist()

    if settings.MAX_TICKERS > 0:
        codes = codes[: settings.MAX_TICKERS]

    rows: list[dict[str, Any]] = []
    today = datetime.now().date()

    for code in codes:
        try:
            # 최근 공시 정보 조회 (연간 재무제표만)
            disclosures = client.finstate_all_search(code)

            if disclosures is None or disclosures.empty:
                continue

            # 연간 재무제표 공시만 필터
            annual_disclosures = disclosures[
                (disclosures.get("report_nm", "").str.contains("사업보고서|정정공시|반기보고서", na=False, regex=True))
            ]

            if annual_disclosures.empty:
                continue

            # 가장 최근 공시
            latest = annual_disclosures.iloc[0]
            disclosure_date_str = latest.get("dcls_date")

            if not disclosure_date_str:
                continue

            try:
                disclosure_date = datetime.strptime(str(disclosure_date_str), "%Y-%m-%d").date()
            except (ValueError, TypeError):
                continue

            delay_days = (today - disclosure_date).days

            rows.append({
                "stock_code": code,
                "latest_disclosure_date": disclosure_date.isoformat(),
                "disclosure_delay_days": delay_days,
            })

        except Exception as exc:
            log.warning(
                "disclosure date fetch failed",
                stock_code=code,
                error=str(exc),
            )

    log.info("disclosure date collection complete", total=len(rows))
    return (
        pd.DataFrame(rows, columns=["stock_code", "latest_disclosure_date", "disclosure_delay_days"])
        if rows
        else pd.DataFrame(columns=["stock_code", "latest_disclosure_date", "disclosure_delay_days"])
    )


def fetch_major_shareholders(
    tickers: pd.DataFrame | None = None,
    client: Any | None = None,
) -> pd.DataFrame:
    """각 종목의 주요주주 정보를 수집한다.

    반환 컬럼: stock_code, largest_shareholder_ratio, institutional_ratio

    - largest_shareholder_ratio: 최대 주주 지분율 (%)
    - institutional_ratio: 기관 보유 비율 (%)
    """
    if client is None:
        try:
            from opendartreader import OpenDartReader
            client = OpenDartReader(settings.DART_API_KEY)
        except Exception:
            log.warning("major shareholder fetch skipped: no DART client")
            return pd.DataFrame(columns=["stock_code", "largest_shareholder_ratio", "institutional_ratio"])

    if tickers is None:
        from src.collectors.krx_tickers import fetch_ticker_list
        tickers = fetch_ticker_list()

    codes = tickers["stock_code"].astype(str).str.zfill(6).tolist()

    if settings.MAX_TICKERS > 0:
        codes = codes[: settings.MAX_TICKERS]

    rows: list[dict[str, Any]] = []

    for code in codes:
        try:
            # 주요주주 정보 조회
            shareholders = client.major_shareholders(code)

            if shareholders is None or shareholders.empty:
                continue

            # 최대 주주의 지분율
            largest_ratio = shareholders.iloc[0].get("ownership") if len(shareholders) > 0 else None

            # 기관투자자 비율 계산 (기관 항목들의 합)
            institutional = shareholders[shareholders.get("name", "").str.contains("기관|펀드|보험", na=False, regex=True)]
            institutional_ratio = institutional.get("ownership").sum() if not institutional.empty else None

            rows.append({
                "stock_code": code,
                "largest_shareholder_ratio": _parse_ratio(largest_ratio),
                "institutional_ratio": _parse_ratio(institutional_ratio),
            })

        except Exception as exc:
            log.warning(
                "major shareholder fetch failed",
                stock_code=code,
                error=str(exc),
            )

    log.info("major shareholder collection complete", total=len(rows))
    return (
        pd.DataFrame(rows, columns=["stock_code", "largest_shareholder_ratio", "institutional_ratio"])
        if rows
        else pd.DataFrame(columns=["stock_code", "largest_shareholder_ratio", "institutional_ratio"])
    )


def _parse_ratio(value: Any) -> float | None:
    """퍼센트 문자열을 float로 변환한다."""
    if value is None:
        return None

    text = str(value).strip().replace("%", "").replace(",", "")
    try:
        return float(text)
    except (ValueError, AttributeError):
        return None
