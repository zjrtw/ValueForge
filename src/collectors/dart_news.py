"""DART 공시 뉴스 및 최근 공지사항 수집."""

from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from src.utils.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)


def fetch_recent_disclosures(
    stock_code: str,
    days: int = 30,
    client: Any | None = None,
) -> list[dict[str, Any]]:
    """특정 종목의 최근 공시 내용을 수집한다.

    Args:
        stock_code: 6자리 종목 코드
        days: 조회 일수 (기본 30일)
        client: DART 클라이언트

    Returns:
        공시 정보 딕셔너리 리스트
        - title: 공시 제목
        - date: 공시일
        - summary: 공시 요약
    """
    if client is None:
        try:
            from opendartreader import OpenDartReader
            client = OpenDartReader(settings.DART_API_KEY)
        except Exception:
            log.warning("disclosure fetch skipped: no DART client")
            return []

    code = str(stock_code).zfill(6)
    rows: list[dict[str, Any]] = []

    try:
        # 최근 공시 정보 조회
        disclosures = client.finstate_all_search(code)

        if disclosures is None or disclosures.empty:
            return []

        # 최근 30일 공시만 필터
        cutoff_date = (datetime.now() - timedelta(days=days)).date()
        recent = disclosures[
            pd.to_datetime(disclosures.get("dcls_date", ""), errors="coerce").dt.date >= cutoff_date
        ]

        if recent.empty:
            return []

        for _, row in recent.iterrows():
            try:
                title = row.get("report_nm", "")
                date = row.get("dcls_date", "")

                rows.append({
                    "stock_code": code,
                    "title": title,
                    "date": str(date),
                    "summary": f"공시: {title} ({date})",
                })
            except Exception:
                continue

    except Exception as exc:
        log.warning("disclosure fetch failed", stock_code=code, error=str(exc))

    return rows


def summarize_disclosure_news(
    stock_code: str,
    stock_name: str,
    days: int = 30,
    client: Any | None = None,
) -> str:
    """종목의 최근 공시 내용을 요약한다.

    Returns:
        공시 요약 텍스트
    """
    disclosures = fetch_recent_disclosures(stock_code, days, client)

    if not disclosures:
        return "최근 30일 이내 공시 정보 없음"

    # 공시 제목만 추출
    titles = [d["title"] for d in disclosures[:5]]  # 최근 5개만

    summary = f"{stock_name}의 최근 주요 공시:\n"
    for i, title in enumerate(titles, 1):
        summary += f"{i}. {title}\n"

    return summary
