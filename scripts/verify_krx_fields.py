"""M7-2: KRX Open API 응답 필드 상세 검증 스크립트."""
import sys
import json

sys.path.insert(0, ".")

from dotenv import load_dotenv
load_dotenv()

from src.collectors.krx_client import _post, fetch_market_daily, fetch_issue_base_info

TEST_DATES = ["20260528", "20260527", "20260526", "20260522"]


def check_daily(endpoint: str) -> None:
    rows: list[dict] = []
    used_date = None
    for d in TEST_DATES:
        try:
            rows = fetch_market_daily(endpoint, d)
            if rows:
                used_date = d
                break
        except Exception as exc:
            print(f"  {d} skip: {exc}")

    if not rows:
        print(f"ERROR: {endpoint} 데이터 없음")
        return

    print(f"\n=== {endpoint} ({used_date}) - {len(rows)}개 종목 ===")
    first = rows[0]
    for k, v in first.items():
        print(f"  {k:<30} = {repr(v)}")

    per_pbr = [k for k in first if k.upper() in ("PER", "PBR")]
    div_keys = [k for k in first if any(x in k.upper() for x in ("DIV", "DVD", "DPS", "YLD", "YD"))]
    print(f"\n  [PER/PBR]   : {per_pbr or '없음'}")
    print(f"  [배당수익률] : {div_keys or '없음'}")


def check_base_info_raw(endpoint: str) -> None:
    """raw 응답 출력으로 파라미터 문제 디버그."""
    print(f"\n=== {endpoint} (raw) ===")
    # 빈 body
    try:
        data = _post(endpoint, {})
        keys = list(data.keys()) if isinstance(data, dict) else "list"
        print(f"  빈 body 결과: keys={keys}, len={len(data) if isinstance(data, list) else '?'}")
        if isinstance(data, dict):
            for k, v in data.items():
                preview = repr(v)[:120]
                print(f"  {k}: {preview}")
    except Exception as exc:
        print(f"  빈 body 실패: {exc}")

    # 날짜 파라미터 포함
    for d in TEST_DATES[:2]:
        try:
            data = _post(endpoint, {"basDd": d})
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, list) and v:
                        print(f"  basDd={d} -> '{k}' 배열 {len(v)}개, 첫행={list(v[0].keys())}")
                        return
            print(f"  basDd={d} -> {list(data.keys()) if isinstance(data, dict) else type(data)}")
        except Exception as exc:
            print(f"  basDd={d} 실패: {exc}")


def find_per_pbr_endpoint() -> None:
    """PER/PBR/배당수익률 전용 엔드포인트 탐색."""
    print("\n=== PER/PBR/배당수익률 엔드포인트 탐색 ===")
    candidates = [
        ("sto/stk_bydd_trd_pbr", {"basDd": "20260528"}),
        ("sto/stk_mktcap_trd", {"basDd": "20260528"}),
        ("sto/stk_per_pbr_dvd", {"basDd": "20260528"}),
        ("idx/stk_idx_ddpr", {"basDd": "20260528"}),
    ]
    import requests as req
    from src.utils.config import settings
    base = "https://data-dbg.krx.co.kr/svc/apis"
    headers = {"AUTH_KEY": settings.KRX_AUTH_KEY.strip(), "Content-Type": "application/json"}
    for path, payload in candidates:
        url = f"{base}/{path}"
        try:
            r = req.post(url, headers=headers, json=payload, timeout=10)
            print(f"  {path}: HTTP {r.status_code}")
            if r.status_code == 200:
                d = r.json()
                print(f"    keys={list(d.keys()) if isinstance(d, dict) else 'list'}")
        except Exception as exc:
            print(f"  {path}: {exc}")


if __name__ == "__main__":
    check_daily("stk_bydd_trd")
    check_daily("ksq_bydd_trd")
    check_base_info_raw("stk_isu_base_info")
    check_base_info_raw("ksq_isu_base_info")
    find_per_pbr_endpoint()
