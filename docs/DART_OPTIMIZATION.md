# DART API 최적화 전략

## 개요

ValueForge의 DART API 호출 최적화는 **TTL 기반 캐싱**과 **스레드 세이프 quota 관리**로 이루어진다.

- **일 한도**: 10,000회
- **파이프라인 소비**: ~6,000회 (2,000개 종목 × 3개년)
- **최적화 효과**: 당일 재실행 시 0회로 감축

---

## 아키텍처

### 1. TTL 기반 캐싱

**구현**: `src/db/repository.py::get_cached_fundamental_pairs()`

```python
def get_cached_fundamental_pairs(
    codes: list[str],
    fiscal_years: list[int],
    ttl_days: int = 30
) -> set[tuple[str, int]]:
    """TTL 이내에 수집된 (stock_code, fiscal_year) 쌍 반환."""
    query = """
        SELECT DISTINCT stock_code, fiscal_year
        FROM fundamentals
        WHERE fiscal_quarter = 0
          AND stock_code IN ({})
          AND fiscal_year IN ({})
          AND julianday('now') - julianday(collected_at) <= ?
    """
```

**특징:**
- 별도 캐시 테이블 불필요 (fundamentals 테이블 재활용)
- `collected_at` 컬럼 활용 (이미 존재)
- SQLite `julianday()` 함수로 일수 비교
- 분기 데이터 제외 (fiscal_quarter = 0만)

**TTL 값 선택:**
- **30일 (기본)**: 연간 재무제표는 자주 변경되지 않음
- **7일**: 보수적 캐싱 (월 1회 갱신)
- **90일**: 적극적 캐싱 (분기 갱신)

```bash
# 30일 TTL로 캐싱 활성화 (기본값)
fundamentals = fetch_financial_statements(tickers, conn=repo.conn)

# 7일 TTL로 변경
fundamentals = fetch_financial_statements(
    tickers, 
    conn=repo.conn, 
    cache_ttl_days=7
)

# 캐싱 비활성화 (conn=None)
fundamentals = fetch_financial_statements(tickers)
```

### 2. 스레드 세이프 Quota 관리

**구현**: `src/utils/rate_limiter.py::DailyQuotaTracker`

```python
class DailyQuotaTracker:
    def __init__(self, daily_limit: int = 10000):
        self._lock = threading.Lock()
        self._limit = daily_limit
        
    def try_acquire(self, count: int = 1) -> bool:
        """원자적(atomic) quota 확인 및 차감."""
        with self._lock:
            if self._calls >= self._limit - count:
                return False
            self._calls += count
            return True
```

**특징:**
- `Lock` 기반 원자적 연산 (TOCTOU 경합 방지)
- `parallel_map()` 멀티스레딩 환경에서 안전
- Check-then-act를 단일 호출로 통합

**사용:**
```python
# parallel_map에서 안전하게 호출
if not _quota_tracker.try_acquire(1):
    return None  # 호출하지 않음
response = dart.finstate(code, year, reprt_code)
```

---

## 성능 벤치마크

### 시나리오별 API 호출 횟수

| 시나리오 | 종목 수 | 연수 | 호출 수 (변경 전) | 호출 수 (변경 후) | 감축율 |
|---|---|---|---|---|---|
| 초회 실행 | 2,000 | 3 | 6,000 | 6,000 | 0% |
| 당일 재실행 | 2,000 | 3 | 6,000 | 0 | 100% |
| 부분 재실행 (50% 성공) | 2,000 | 3 | 6,000 | ~3,000 | 50% |
| 31일 후 재실행 | 2,000 | 3 | 6,000 | 6,000 | 0% (TTL 만료) |
| 개발 테스트 (50 종목) | 50 | 3 | 150 | 0 | 100% |

### 실행 시간 단축

```bash
# 변경 전: DART 수집 단계
2025-01-20 09:15:30 [info] collect_fundamentals_start
2025-01-20 09:18:45 [info] collect_fundamentals_done  # ~3분 15초

# 변경 후: DART 수집 단계 (캐시 HIT)
2026-05-30 09:15:30 [info] collect_fundamentals_start
2026-05-30 09:15:32 [info] collect_fundamentals_done  # ~2초 (API 0회)
```

### 로그 추적

```python
# Repository에서 캐시 HIT 통계
log.info(
    "dart financial cache hit",
    cached=150,  # 캐시된 쌍 수
    total=300,   # 전체 필요 쌍 수
    cache_rate=50.0  # %
)
```

---

## 구현 상세

### 파이프라인 통합 (1줄 변경)

**변경 전:**
```python
# src/pipeline/runner.py:164
fundamentals = fetch_financial_statements(tickers)
```

**변경 후:**
```python
# src/pipeline/runner.py:164
fundamentals = fetch_financial_statements(tickers, conn=repo.conn)
```

효과: 이 1줄만으로 캐싱이 자동 활성화된다.

### 수집기 내부 로직

```python
# src/collectors/dart_financials.py:76-87
cached_pairs: set[tuple[str, int]] = set()
if conn is not None:
    from src.db.repository import Repository
    repo = Repository(conn)
    cached_pairs = repo.get_cached_fundamental_pairs(
        codes, fiscal_years, cache_ttl_days
    )
    if cached_pairs:
        log.info(
            "dart financial cache hit",
            cached=len(cached_pairs),
            total=len(codes) * len(fiscal_years),
        )

# 캐시 체크
def _fetch_and_normalize(code_year: tuple[str, int]) -> dict | None:
    code, fiscal_year = code_year
    if (code, fiscal_year) in cached_pairs:  # 캐시 HIT
        return None
    if not _quota_tracker.try_acquire(1):    # 스레드 세이프 체크
        return None
    # API 호출...
```

---

## TTL 설정 가이드

### 권장 TTL값

```yaml
# config/screening_params.yaml 또는 .env에 추가 가능
dart_cache_ttl_days: 30  # 기본: 30일
```

### 시나리오별 추천

| 시나리오 | TTL | 이유 |
|---|---|---|
| 프로덕션 (일일 실행) | 30일 | 재무제표는 월 1회 공시. 월간 갱신으로 충분 |
| 개발 (반복 테스트) | 7일 | 테스트 데이터 변경 시 빠른 재수집 |
| 분기 갱신 | 90일 | 분기별 실행. 장기 안정성 |
| 캐싱 비활성화 | 0 | 항상 최신 데이터 (quota 소비 증가) |

### 캐시 만료 확인

```python
# 수동으로 캐시 상태 확인
from src.db.repository import Repository
import sqlite3

conn = sqlite3.connect("valueforge.db")
repo = Repository(conn)

# 캐시된 쌍 조회
cached = repo.get_cached_fundamental_pairs(
    codes=["005930", "000660"],
    fiscal_years=[2023, 2024, 2025],
    ttl_days=30
)
print(f"30일 이내 캐시: {len(cached)} 쌍")

# 직접 쿼리로 확인
import datetime
query = """
    SELECT stock_code, fiscal_year, MAX(collected_at) as last_collected
    FROM fundamentals
    WHERE fiscal_quarter = 0
    GROUP BY stock_code, fiscal_year
    ORDER BY last_collected DESC
"""
result = conn.execute(query).fetchall()
for code, year, collected_at in result:
    days_ago = (datetime.datetime.now() - datetime.datetime.fromisoformat(collected_at)).days
    print(f"{code}/{year}: {days_ago}일 전")
```

---

## 트러블슈팅

### 문제 1: "캐시가 작동하지 않음"

**증상:** 매번 DART API 호출 6,000회 발생

**원인:**
1. `conn=None` (기본값이므로 캐싱 비활성화)
2. TTL 초과 (30일 지남)
3. fundamentals 테이블이 비어있음

**해결:**
```python
# ✅ conn 전달 확인
fundamentals = fetch_financial_statements(tickers, conn=repo.conn)

# ✅ TTL 재설정
fundamentals = fetch_financial_statements(
    tickers, 
    conn=repo.conn,
    cache_ttl_days=90  # TTL 연장
)

# ✅ 캐시 상태 확인
cached = repo.get_cached_fundamental_pairs(
    codes, fiscal_years, ttl_days=30
)
print(f"캐시된 쌍: {len(cached)}")
```

### 문제 2: "quota 한도 도달 메시지"

**증상:** `dart daily quota exhausted` 로그 반복

**원인:** 
- 병렬 수집 과정에서 quota 체크 실패
- 이전 실행에서 누적된 호출

**해결:**
```python
# 현재 quota 상태 확인
from src.collectors.dart_financials import _quota_tracker
print(f"남은 quota: {_quota_tracker._limit - _quota_tracker._calls}")

# 테스트 실행으로 quota 절약
MAX_TICKERS=50 python -m src.pipeline.runner --date today --no-upload
```

### 문제 3: "캐시 업데이트 안 됨"

**증상:** 새 데이터가 있어도 캐시만 반환

**원인:** TTL이 아직 유효함

**해결:**
```python
# TTL을 0으로 설정하여 강제 갱신
fundamentals = fetch_financial_statements(
    tickers,
    conn=repo.conn,
    cache_ttl_days=0  # 캐시 무시, 항상 수집
)

# 또는 DB에서 직접 삭제
import sqlite3
conn = sqlite3.connect("valueforge.db")
conn.execute(
    "DELETE FROM fundamentals WHERE stock_code = ? AND fiscal_year = ?",
    ("005930", 2024)
)
conn.commit()
```

---

## 다음 단계 (선택사항)

### 1. 배치 API 활용

DART OpenAPI의 배치 엔드포인트 검토:
- `/list` 엔드포인트로 공시 목록 조회 후 필터링
- 불필요한 호출 사전 차단

### 2. 메모리 캐싱 계층

파이프라인 실행 중 메모리 캐시 추가:
```python
from functools import lru_cache

@lru_cache(maxsize=512)
def _fetch_cached_statement(code: str, year: int) -> dict:
    # DB에서만 조회, API 호출 없음
    ...
```

### 3. 캐시 워밍

파이프라인 시작 전 자주 조회하는 종목 사전 로드:
```python
# TOP 100 종목의 캐시 미리 로드
top_tickers = repo.get_top_market_cap(100)
cached = repo.get_cached_fundamental_pairs(
    top_tickers, years, ttl_days=0
)
```

---

## 관련 문서

- [DATABASE.md](DATABASE.md) - `fundamentals` 테이블 스키마
- [ARCHITECTURE.md](ARCHITECTURE.md) - 전체 파이프라인 아키텍처
- [docs/CLAUDE.md](CLAUDE.md) - 코드 작성 원칙 (Repository 패턴)
