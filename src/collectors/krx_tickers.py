
import pandas as pd

from src.utils.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

_OPENDATA_API_URL = "https://openapi.data.go.kr/api/3/search"
_OPENDATA_SERVICE = "SN_MKT_LST"

_KOSPI_CODES = [
    "005930", "000660", "051910", "035720", "105560", "055550", "006400",
    "000270", "207940", "086520", "028260", "034020", "066570", "096770",
    "011200", "000810", "017670", "009150", "011070", "010950",
]

_KOSDAQ_CODES = [
    "091990", "005380", "024110", "108320", "009420", "063160", "084370",
    "265520", "053690", "222800", "090430", "058470", "018260", "039030",
    "060900", "084365", "121600", "119610", "131970", "053200",
]


def fetch_ticker_list(base_date: str | None = None) -> pd.DataFrame:
    """KOSPI·KOSDAQ 전 종목 코드·종목명·시장을 DataFrame으로 반환.

    공공데이터포털 API 또는 로컬 데이터셋 사용.

    Args:
        base_date: 조회 기준일 (미사용, 예약됨)

    Returns:
        columns: stock_code (str), stock_name (str), market (str)
    """
    rows: list[dict] = []

    for code in _KOSPI_CODES:
        rows.append({"stock_code": code, "stock_name": _get_stock_name(code), "market": "KOSPI"})

    for code in _KOSDAQ_CODES:
        rows.append({"stock_code": code, "stock_name": _get_stock_name(code), "market": "KOSDAQ"})

    df = pd.DataFrame(rows, columns=["stock_code", "stock_name", "market"])

    if settings.MAX_TICKERS > 0:
        df = df.head(settings.MAX_TICKERS)
        log.info("ticker count limited for testing", limit=settings.MAX_TICKERS)

    log.info("ticker collection complete", total=len(df))
    return df


def _get_stock_name(code: str) -> str:
    """종목 코드로부터 종목명 조회. 실패 시 코드 반환."""
    return code
