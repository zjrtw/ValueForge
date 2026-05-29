import requests

from src.utils.config import settings
from src.utils.logger import get_logger
from src.utils.rate_limiter import RateLimiter
from src.utils.retry import with_retry

log = get_logger(__name__)

_BASE_URL = "https://data-dbg.krx.co.kr/svc/apis/sto"
_rate_limiter = RateLimiter(min_delay_seconds=0.5)

# 일별 호출 한도 10,000회 — 내부 추적용 상수
DAILY_CALL_LIMIT = 10_000


class KrxApiError(Exception):
    """KRX Open API 호출 실패."""


@with_retry(max_attempts=3, delay=1.0, backoff=2.0, exceptions=(requests.RequestException,))
def _post(endpoint: str, payload: dict) -> dict:
    """인증키 헤더로 KRX Open API 엔드포인트를 POST 호출하고 JSON을 반환."""
    if not settings.KRX_AUTH_KEY:
        raise KrxApiError("KRX_AUTH_KEY가 설정되지 않았습니다.")

    url = f"{_BASE_URL}/{endpoint}"
    headers = {
        "AUTH_KEY": settings.KRX_AUTH_KEY.strip(),
        "Content-Type": "application/json",
    }

    _rate_limiter.wait()
    response = requests.post(url, headers=headers, json=payload, timeout=30)

    if response.status_code == 401:
        raise KrxApiError(f"인증 실패 (401): AUTH_KEY 확인 또는 해당 API 이용 승인 필요 - {endpoint}")
    if response.status_code == 400:
        raise KrxApiError(f"잘못된 요청 (400): 파라미터 확인 필요 - {endpoint}, payload={payload}")

    response.raise_for_status()
    return response.json()


def _extract_rows(data: dict) -> list[dict]:
    """KRX API 응답에서 레코드 배열을 추출.

    KRX 응답 포맷: {"OutBlock_1": [...]} 또는 {"output": [...]}
    """
    for key in ("OutBlock_1", "OutBlock1", "output", "data"):
        if key in data and isinstance(data[key], list):
            return data[key]
    # 응답 자체가 list인 경우 (일부 엔드포인트)
    if isinstance(data, list):
        return data
    log.warning("krx_unexpected_response_format", keys=list(data.keys()))
    return []


def fetch_market_daily(endpoint: str, bas_dd: str) -> list[dict]:
    """날짜 기준 시장 전체 일별매매 데이터를 반환.

    Args:
        endpoint: 'stk_bydd_trd' (KOSPI) 또는 'ksq_bydd_trd' (KOSDAQ)
        bas_dd:   기준일자 (YYYYMMDD)

    Returns:
        각 종목의 일별매매 정보 dict 리스트.
        필드 예시: ISU_SRT_CD, ISU_ABBRV, TDD_OPNPRC, TDD_HGPRC,
                   TDD_LWPRC, TDD_CLSPRC, ACC_TRDVOL, ACC_TRDVAL,
                   MKTCAP, PER, PBR, (DIV_YD — 검증 필요)
    """
    data = _post(endpoint, {"basDd": bas_dd})
    rows = _extract_rows(data)
    log.info("krx_daily_fetched", endpoint=endpoint, bas_dd=bas_dd, count=len(rows))
    return rows


def fetch_issue_base_info(endpoint: str, bas_dd: str) -> list[dict]:
    """종목기본정보를 반환.

    Args:
        endpoint: 'stk_isu_base_info' (KOSPI) 또는 'ksq_isu_base_info' (KOSDAQ)
        bas_dd:   기준일자 (YYYYMMDD)

    Returns:
        각 종목의 기본정보 dict 리스트.
        필드: ISU_CD, ISU_SRT_CD, ISU_NM, ISU_ABBRV, ISU_ENG_NM,
              LIST_DD (상장일 YYYY/MM/DD), LIST_SHRS (상장주식수),
              MKT_TP_NM, SECT_TP_NM, PARVAL
    """
    data = _post(endpoint, {"basDd": bas_dd})
    rows = _extract_rows(data)
    log.info("krx_base_info_fetched", endpoint=endpoint, bas_dd=bas_dd, count=len(rows))
    return rows
