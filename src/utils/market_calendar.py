"""한국 주식시장(KRX) 거래일 판별 유틸리티."""
from __future__ import annotations

from datetime import date, datetime, timezone

import exchange_calendars as xcals

from src.utils.logger import get_logger

log = get_logger(__name__)

_EXCHANGE = "XKRX"


def _get_calendar():
    return xcals.get_calendar(_EXCHANGE)


def is_trading_day(check_date: date | None = None) -> bool:
    """주어진 날짜가 KRX 거래일이면 True를 반환한다.

    Args:
        check_date: 확인할 날짜. None이면 오늘(UTC+9 기준)을 사용한다.

    Returns:
        True  — 거래일
        False — 휴장일 (주말, 공휴일, 대체공휴일 등)
    """
    target = check_date or _today_kst()
    cal = _get_calendar()
    result: bool = cal.is_session(target.isoformat())
    log.info(
        "trading_day_check",
        date=target.isoformat(),
        is_trading_day=result,
    )
    return result


def next_trading_day(after: date | None = None) -> date:
    """주어진 날짜 이후 첫 번째 거래일을 반환한다."""
    base = after or _today_kst()
    cal = _get_calendar()
    session = cal.date_to_session(base.isoformat(), direction="next")
    return date.fromisoformat(str(session.date()))


def prev_trading_day(before: date | None = None) -> date:
    """주어진 날짜 이전(포함) 가장 최근 거래일을 반환한다."""
    base = before or _today_kst()
    cal = _get_calendar()
    session = cal.date_to_session(base.isoformat(), direction="previous")
    return date.fromisoformat(str(session.date()))


def _today_kst() -> date:
    """현재 한국 표준시(UTC+9) 기준 오늘 날짜를 반환한다."""
    from datetime import timedelta
    return (datetime.now(tz=timezone.utc) + timedelta(hours=9)).date()
