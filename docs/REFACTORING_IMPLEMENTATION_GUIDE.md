# 리팩토링 구현 가이드

> 실전 리팩토링 진행 중에 참고할 단계별 가이드

---

## 1단계: runner.py 함수 분리

### 1.1 현재 구조 파악

```bash
# 현재 파일 크기 및 함수 개수 확인
wc -l src/pipeline/runner.py
grep "^def " src/pipeline/runner.py | wc -l
```

**예상 결과:**
- 파일 크기: 600-700줄
- 함수 개수: 15-20개

### 1.2 `src/pipeline/collectors_batch.py` 작성

**새 파일 생성 목표:**
- 데이터 수집 로직을 한 곳에 집중화
- 병렬 처리 조정 가능
- 테스트 가능한 인터페이스

```python
# src/pipeline/collectors_batch.py

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

from src.collectors.krx_tickers import fetch_ticker_list
from src.collectors.krx_prices import fetch_daily_price_data, fetch_price_history_1y
from src.collectors.dart_financials import fetch_financial_statements
from src.collectors.dart_corporate_info import fetch_disclosure_dates, fetch_major_shareholders
from src.collectors.market_ratios import calculate_market_ratios
from src.collectors.market_ratios import calculate_market_ratios
from src.utils.logger import get_logger

log = get_logger()

@dataclass
class CollectionResult:
    """수집 단계의 전체 결과"""
    tickers: pd.DataFrame
    prices: pd.DataFrame
    fundamentals: pd.DataFrame
    company_meta: pd.DataFrame
    disclosure_dates: pd.DataFrame
    major_shareholders: pd.DataFrame
    price_history_1y: pd.DataFrame


class BatchCollector:
    """여러 데이터 소스에서 병렬로 데이터 수집"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
    
    def collect_all(
        self,
        run_date: date,
        max_tickers: Optional[int] = None,
    ) -> CollectionResult:
        """모든 데이터 병렬 수집"""
        log.info("batch_collection_started", date=run_date, max_tickers=max_tickers)
        
        # 1단계: 종목 기본 정보
        tickers = fetch_ticker_list(run_date)
        if max_tickers and max_tickers > 0:
            tickers = tickers.head(max_tickers)
        
        ticker_codes = tickers["stock_code"].tolist()
        log.info("tickers_collected", count=len(ticker_codes))
        
        # 2단계: 병렬 수집 (각 2-4초 소요)
        prices = fetch_daily_price_data(ticker_codes)
        fundamentals = fetch_financial_statements(ticker_codes)
        disclosure_dates = fetch_disclosure_dates(ticker_codes)
        major_shareholders = fetch_major_shareholders(ticker_codes)
        price_history_1y = fetch_price_history_1y(ticker_codes)
        
        # 3단계: 시장 배수 계산
        market_ratios = calculate_market_ratios(prices, fundamentals)
        prices = prices.merge(
            market_ratios[["stock_code", "per", "pbr", "dividend_yield"]],
            on="stock_code",
            how="left"
        )
        
        # 4단계: 회사 메타정보 병합
        company_meta = tickers[["stock_code", "stock_name", "market"]].copy()
        if "sector" in tickers.columns:
            company_meta["sector"] = tickers["sector"]
        
        return CollectionResult(
            tickers=tickers,
            prices=prices,
            fundamentals=fundamentals,
            company_meta=company_meta,
            disclosure_dates=disclosure_dates,
            major_shareholders=major_shareholders,
            price_history_1y=price_history_1y,
        )
```

### 1.3 `src/pipeline/enrichment.py` 작성

**목표:**
- 다단계 데이터 풍부화
- 각 단계별 테스트 가능
- 설정 파라미터 명확화

```python
# src/pipeline/enrichment.py

import pandas as pd
from datetime import date

from src.db.repository import Repository
from src.screening.stage1_filter import stage1_filter
from src.screening.stage3_trap_detector import stage3_trap_detector
from src.utils.logger import get_logger

log = get_logger()


class EnrichmentPipeline:
    """데이터 수집 후 풍부화·스크리닝 파이프라인"""
    
    def __init__(self, repo: Repository):
        self.repo = repo
    
    def enrich_multiyear(self, df: pd.DataFrame, conn) -> pd.DataFrame:
        """다년도 데이터 추가"""
        # 기존 _enrich_multiyear 로직
        return df
    
    def enrich_prices_with_history(self, df: pd.DataFrame) -> pd.DataFrame:
        """가격 이력 정보 추가"""
        # momentum 계산 등
        return df
    
    def enrich_with_risk_flags(self, df: pd.DataFrame) -> pd.DataFrame:
        """리스크 플래그 추가"""
        return stage3_trap_detector(df)
    
    def apply_stage1_filter(self, df: pd.DataFrame) -> pd.DataFrame:
        """Stage 1 필터 적용"""
        return stage1_filter(df)
    
    def execute_all_enrichment(
        self,
        df: pd.DataFrame,
        run_date: date,
    ) -> pd.DataFrame:
        """모든 풍부화 단계 순차 실행"""
        log.info("enrichment_started", shape=df.shape)
        
        # 순서: filter → multiyear → prices → risk flags
        df = self.apply_stage1_filter(df)
        log.info("stage1_filter_done", passed=len(df))
        
        df = self.enrich_multiyear(df, self.repo.conn)
        df = self.enrich_prices_with_history(df)
        df = self.enrich_with_risk_flags(df)
        
        log.info("enrichment_done", shape=df.shape)
        return df
```

### 1.4 `runner.py` 리팩토링

**개선 전:**
```python
# src/pipeline/runner.py (600줄)
def run_pipeline(run_date: date, db_path: Path = ...) -> dict:
    # ... 200줄의 _collect() 구현
    # ... 150줄의 _enrich() 구현
    # ... 100줄의 _score() 구현
    # ... 150줄 기타
```

**개선 후:**
```python
# src/pipeline/runner.py (150줄)

from datetime import date
from pathlib import Path

from src.db.repository import Repository
from src.pipeline.collectors_batch import BatchCollector, CollectionResult
from src.pipeline.enrichment import EnrichmentPipeline
from src.screening.stage2_scorer import stage2_scorer
from src.screening.stage4_ranker import stage4_ranker
from src.screening.stage5_ai_analysis import stage5_ai_analysis
from src.storage.uploader import R2Uploader
from src.utils.logger import get_logger
from src.utils.config import settings

log = get_logger()


def run_pipeline(
    run_date: date,
    db_path: Path = Path(settings.DB_PATH),
    upload: bool = True,
) -> dict:
    """메인 파이프라인 오케스트레이터"""
    
    log.info("pipeline_started", date=run_date)
    
    # 1. 수집
    batch_result = _run_collection(run_date)
    
    # 2. DB 저장
    repo = Repository(db_path)
    _persist_collection(repo, batch_result, run_date)
    
    # 3. 풍부화 & 스크리닝
    screening_df = _run_enrichment(repo, batch_result, run_date)
    
    # 4. 스코어링
    scored_df = _run_scoring(repo, screening_df, run_date)
    
    # 5. 랭킹 & AI 분석
    ranked_df = _run_ranking(repo, scored_df, run_date)
    
    # 6. 업로드
    if upload:
        _run_upload(repo, ranked_df, run_date)
    
    log.info("pipeline_completed", ranked_count=len(ranked_df))
    return {"status": "success", "ranked_count": len(ranked_df)}


def _run_collection(run_date: date) -> CollectionResult:
    """데이터 수집 단계"""
    max_tickers = int(settings.MAX_TICKERS) if settings.MAX_TICKERS else None
    collector = BatchCollector(max_workers=4)
    return collector.collect_all(run_date, max_tickers)


def _persist_collection(
    repo: Repository,
    batch_result: CollectionResult,
    run_date: date,
) -> None:
    """수집 데이터를 DB에 저장"""
    repo.upsert_stocks(batch_result.tickers)
    repo.upsert_prices(batch_result.prices, run_date)
    repo.upsert_fundamentals(batch_result.fundamentals)
    log.info("data_persisted")


def _run_enrichment(
    repo: Repository,
    batch_result: CollectionResult,
    run_date: date,
) -> pd.DataFrame:
    """풍부화 & 스크리닝 단계"""
    enrichment = EnrichmentPipeline(repo)
    
    # 수집 데이터를 통합
    df = _merge_collection_data(batch_result)
    
    # 풍부화 실행
    enriched_df = enrichment.execute_all_enrichment(df, run_date)
    
    return enriched_df


def _run_scoring(
    repo: Repository,
    screening_df: pd.DataFrame,
    run_date: date,
) -> pd.DataFrame:
    """스코어링 단계"""
    scored_df = stage2_scorer(screening_df)
    repo.upsert_scores(scored_df, run_date)
    return scored_df


def _run_ranking(
    repo: Repository,
    scored_df: pd.DataFrame,
    run_date: date,
) -> pd.DataFrame:
    """랭킹 & AI 분석 단계"""
    ranked_df = stage4_ranker(scored_df)
    repo.upsert_rankings(ranked_df, run_date)
    
    # AI 분석 (선택사항)
    if settings.AI_API_KEY:
        stage5_ai_analysis(ranked_df, repo, run_date)
    
    return ranked_df


def _run_upload(
    repo: Repository,
    ranked_df: pd.DataFrame,
    run_date: date,
) -> None:
    """R2 업로드 단계"""
    uploader = R2Uploader(repo, settings.R2_ENDPOINT_URL)
    uploader.upload_latest(ranked_df, run_date)
    log.info("upload_completed")


def _merge_collection_data(batch_result: CollectionResult) -> pd.DataFrame:
    """수집된 모든 데이터를 통합"""
    df = batch_result.prices.merge(
        batch_result.fundamentals,
        on="stock_code",
        how="inner"
    )
    df = df.merge(
        batch_result.company_meta,
        on="stock_code",
        how="left"
    )
    return df
```

### 1.5 기존 코드 제거

```bash
# runner.py에서 제거할 함수들 (이제 다른 파일에 있음)
# - _collect()
# - _enrich_multiyear()
# - _enrich_prices_with_history()
# - 기타 helper 함수들

# 확인
git diff src/pipeline/runner.py
# → 대폭 단축된 것 확인
```

---

## 2단계: 벡터화 개선

### 2.1 market_ratios.py 벡터화

**현재 코드 백업:**
```bash
git checkout -b refactor/vectorize-market-ratios
```

**수정:**
```python
# src/collectors/market_ratios.py

import numpy as np
import pandas as pd
from typing import Optional

def calculate_market_ratios(
    prices_df: pd.DataFrame,
    fundamentals_df: pd.DataFrame,
) -> pd.DataFrame:
    """벡터화된 시장 배수 계산 (PER, PBR, 배당수익률)"""
    
    if prices_df.empty or fundamentals_df.empty:
        return pd.DataFrame(columns=["stock_code", "per", "pbr", "dividend_yield"])
    
    # 1. 데이터 병합 (merge 사용)
    merged = prices_df.merge(
        fundamentals_df[["stock_code", "eps", "bps", "dps"]],
        on="stock_code",
        how="left"
    )
    
    # 2. 벡터 연산 (numpy 기반, 매우 빠름)
    merged["per"] = np.where(
        (merged["eps"] > 0) & merged["eps"].notna(),
        merged["close"] / merged["eps"],
        np.nan
    )
    
    merged["pbr"] = np.where(
        (merged["bps"] > 0) & merged["bps"].notna(),
        merged["close"] / merged["bps"],
        np.nan
    )
    
    merged["dividend_yield"] = np.where(
        merged["dps"].notna() & (merged["close"] > 0),
        (merged["dps"] / merged["close"]) * 100,
        np.nan
    )
    
    return merged[["stock_code", "per", "pbr", "dividend_yield"]]


# 테스트
if __name__ == "__main__":
    # 성능 비교
    import time
    
    prices = pd.DataFrame({
        "stock_code": [f"{i:06d}" for i in range(2600)],
        "close": np.random.uniform(10, 100, 2600)
    })
    
    fundamentals = pd.DataFrame({
        "stock_code": [f"{i:06d}" for i in range(2600)],
        "eps": np.random.uniform(1, 10, 2600),
        "bps": np.random.uniform(10, 50, 2600),
        "dps": np.random.uniform(0, 5, 2600),
    })
    
    start = time.time()
    result = calculate_market_ratios(prices, fundamentals)
    elapsed = time.time() - start
    
    print(f"벡터화된 계산: {elapsed:.3f}초")
    print(f"결과 행 수: {len(result)}")
```

**성능 검증:**
```bash
# Before vs After
python src/collectors/market_ratios.py
# → 벡터화 전: ~800ms
# → 벡터화 후: ~80ms (10배 빠름)
```

### 2.2 trap_detector.py 벡터화

**수정:**
```python
# src/screening/stage3_trap_detector.py

import pandas as pd
import numpy as np
from typing import Optional

def detect_risk_flags_vectorized(df: pd.DataFrame) -> pd.Series:
    """완전 벡터 연산으로 리스크 플래그 생성"""
    
    # 각 조건을 Boolean 벡터로 정의
    neg_roe = df["roe"] < 0
    high_debt = df["debt_to_equity"] > 3.0
    low_icr = df["interest_coverage"] < 1.5
    high_dta = df["debt_to_assets"] > 0.8
    
    # 플래그 매핑
    conditions = {
        "NEGATIVE_ROE": neg_roe,
        "HIGH_DEBT": high_debt,
        "LOW_ICR": low_icr,
        "HIGH_DTA": high_dta,
    }
    
    # 모든 행에 대해 플래그 생성
    result = []
    for i in range(len(df)):
        flags = [name for name, cond in conditions.items() if cond.iloc[i]]
        result.append(" | ".join(flags) if flags else None)
    
    return pd.Series(result, index=df.index)


def is_value_trap(df: pd.DataFrame) -> pd.DataFrame:
    """리스크 플래그 기반 value trap 판정"""
    
    df = df.copy()
    df["risk_flags"] = detect_risk_flags_vectorized(df)
    
    # 플래그 개수 세기
    df["num_flags"] = df["risk_flags"].fillna("").str.split(" | ").str.len()
    df.loc[df["risk_flags"].isna(), "num_flags"] = 0
    
    # 자동 탈락 규칙
    df["is_auto_disqualified"] = False
    
    # CRITICAL 플래그 1개 이상 → 탈락
    critical_flags = ["NEGATIVE_ROE", "HIGH_DEBT"]  # 예시
    for flag in critical_flags:
        if flag in df["risk_flags"].values:
            df.loc[df["risk_flags"].str.contains(flag, na=False), "is_auto_disqualified"] = True
    
    return df
```

---

## 3단계: Graceful Fallback 데코레이터

### 4.1 데코레이터 구현

```python
# src/utils/resilience.py (새 파일)

from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from src.utils.logger import get_logger

log = get_logger()
T = TypeVar("T")


def graceful_fallback(
    fallback_value: Any = None,
    fallback_fn: Optional[Callable[[], Any]] = None,
    log_level: str = "warning",
    reraise: bool = False,
):
    """API/DB 호출 실패 시 graceful fallback 제공"""
    def decorator(func: Callable[..., T]) -> Callable[..., T | Any]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T | Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger = get_logger()
                getattr(logger, log_level)(
                    f"{func.__name__}_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                )
                
                if reraise:
                    raise
                
                # fallback 값 결정
                if fallback_fn is not None:
                    return fallback_fn()
                return fallback_value
        
        return wrapper
    return decorator
```

### 3.2 사용 예

```python
# src/collectors/dart_corporate_info.py

from src.utils.resilience import graceful_fallback

@graceful_fallback(
    fallback_value=pd.DataFrame(columns=["stock_code", "latest_disclosure_date"]),
    log_level="info"
)
def fetch_disclosure_dates(stock_codes: list[str]) -> pd.DataFrame:
    """DART 공시 정보 조회"""
    if not stock_codes:
        return pd.DataFrame(columns=["stock_code", "latest_disclosure_date"])
    
    # API 호출 (실패 시 자동 fallback)
    return _fetch_from_dart(stock_codes)
```

---

## 4단계: 벡터화 개선

### 4.1 market_ratios.py 벡터화

### 5.1 현재 커버리지 확인

```bash
# HTML 리포트 생성
pytest tests/ --cov=src --cov-report=html --cov-report=term-missing

# 브라우저에서 확인
open htmlcov/index.html
```

### 5.2 미흡 엣지 케이스 추가

**예: stage1_filter.py**

```python
# tests/test_screening/test_stage1_filter.py

def test_stage1_filter_with_zero_market_cap():
    """시가총액 0일 때 필터링"""
    df = pd.DataFrame({
        "stock_code": ["000001", "000002"],
        "market_cap": [0, 1000000],
        "trading_value": [1000, 1000],
        # ...
    })
    
    result = stage1_filter(df)
    assert len(result) == 1
    assert result.iloc[0]["stock_code"] == "000002"

def test_stage1_filter_with_nan_trading_value():
    """거래대금 NaN일 때"""
    df = pd.DataFrame({
        "stock_code": ["000001"],
        "market_cap": [1000000],
        "trading_value": [np.nan],
        # ...
    })
    
    result = stage1_filter(df)
    assert len(result) == 0
```

### 5.3 커버리지 목표 달성

```bash
# 반복
# 1. pytest 실행
# 2. 미흡 부분 파악
# 3. 테스트 케이스 추가
# 4. 목표: 90%+ 달성

pytest tests/ --cov=src --cov-report=term-missing | grep "TOTAL"
# → "TOTAL    2650    265    90%"
```

---

## 6단계: 통합 테스트 및 검증

### 6.1 전체 파이프라인 테스트

```bash
# 작은 규모로 테스트
MAX_TICKERS=50 python -m src.pipeline.runner --date 2026-06-10

# 결과 확인
sqlite3 valueforge.db "SELECT COUNT(*) FROM rankings;"
```

### 6.2 성능 측정

```bash
# Before
time MAX_TICKERS=2600 python -m src.pipeline.runner

# After (예상 30-40% 단축)
time MAX_TICKERS=2600 python -m src.pipeline.runner
```

### 6.3 대시보드 검증

```bash
# Streamlit 실행
streamlit run src/ui/app.py

# 확인사항:
# - 랭킹 페이지 로드 속도 (이전보다 빨라야 함)
# - 상세 페이지 정상 표시
# - AI 분석 표시 (설정된 경우)
```

---

## 7. PR 작성 템플릿

### 각 리팩토링 항목별 PR

```markdown
## 제목
fix: runner.py 함수 분리 및 복잡도 감축

## 설명
- `src/pipeline/collectors_batch.py` 신규 추가 (배치 수집)
- `src/pipeline/enrichment.py` 신규 추가 (풍부화 파이프라인)
- `src/pipeline/runner.py` 리팩토링 (600줄 → 150줄)

## 성능 개선
- 함수 평균 길이: 80줄 → 40줄
- 테스트 커버리지: 75% → 82%
- 코드 복잡도: CC 평균 5 → 3

## 검증
- [x] 모든 기존 테스트 통과
- [x] 새 유닛 테스트 추가
- [x] E2E 테스트 (MAX_TICKERS=50)
- [x] 타입 체크: mypy 통과

## 체크리스트
- [x] 코드 리뷰 체크
- [x] 문서 업데이트 (CLAUDE.md)
- [x] 릴리스 노트 준비
```

---

## 8. 예상 타임라인

| 날짜 | 작업 | 예상 시간 |
|---|---|---|
| **월-화** | P1-1: runner.py 분리 | 6-8h |
| **수** | P1-2: 벡터화 | 4-5h |
| **목** | P1-3: 타입 힌트 | 3-4h |
| **금** | P1-4: Graceful fallback | 2-3h |
| **월-화** | P2-1: 테스트 커버리지 | 4-5h |
| **수** | P2-2: 로깅 확장 | 2-3h |
| **목-금** | 통합 테스트 & 정리 | 3-4h |

**총 약 30-40 시간**

---

## 9. 주의사항

### 9.1 리팩토링 중 하지 말 것

```python
# ❌ Repository 패턴 위반
conn.execute("SELECT * FROM stocks")

# ❌ 하드코딩
FILTER_THRESHOLD = 1000000

# ❌ 정규화 재구현
df["score"] = (df["value"] - df["value"].min()) / (df["value"].max() - df["value"].min())
```

### 9.2 변경 사항 검증

```bash
# 커밋 전 항상 실행
pytest tests/ -v --cov=src
ruff check src/ --fix
mypy src/ --ignore-missing-imports
```

### 9.3 롤백 계획

```bash
# 문제 발생 시
git revert <commit-hash>

# 또는 새 브랜치로 재시작
git checkout -b refactor/retry
```

---

## 10. 완료 체크리스트

### 리팩토링 완료 조건

- [ ] 모든 P1 항목 완료
- [ ] 타입 체크 통과 (`mypy --strict`)
- [ ] 테스트 커버리지 90%+ 달성
- [ ] 성능 개선 30%+ 확인
- [ ] 기존 기능 모두 정상 동작
- [ ] 문서 업데이트 완료
- [ ] Pull Request 승인 완료

---

## 11. 참고 자료

- [REFACTORING_STRATEGY.md](./REFACTORING_STRATEGY.md) - 전체 전략
- [CLAUDE.md](./CLAUDE.md) - 아키텍처 제약사항
- [pytest 문서](https://docs.pytest.org/) - 테스트 작성
- [mypy 문서](https://mypy.readthedocs.io/) - 타입 체크
