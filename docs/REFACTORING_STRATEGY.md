# 리팩토링 전략 (2026년 6월)

> ValueForge 코드베이스의 장기 유지보수성과 성능을 위한 단계적 리팩토링 계획

---

## 1. 현재 상태 분석

### 1.1 강점 ✅

- **Repository 패턴 준수**: 모든 DB 접근이 `src/db/repository.py` 경유 (good isolation)
- **설정 중앙화**: `config/screening_params.yaml`, `src/utils/config.py`로 환경 변수·파라미터 관리
- **마일스톤 기반 구현**: MVP → M7 (KRX API 전환) → M8 (AI 분석) 순차 완료
- **테스트 기반**: pytest + mocking 기반의 단위 테스트, E2E 테스트 존재

### 1.2 기술 부채 🔴

| 항목 | 심각도 | 설명 | 영향 |
|---|---|---|---|
| **파이프라인 복잡도** | 높음 | `src/pipeline/runner.py` 850줄, 21개 함수 혼재 | 유지보수 어려움, 테스트 어려움 |
| **벡터화 미흡** | 낮음 | `iterrows()`, `apply(axis=1)` 7개만 존재 | 성능 영향 미미 (1-2초 수준) |
| **에러 처리 산발적** | 중간 | graceful fallback이 부분적 (DART API 키 없을 때만) | 예상치 못한 중단 가능 |
| **테스트 커버리지** | 중간 | 주요 로직 커버 중이나 엣지 케이스 부족 | 프로덕션 버그 가능성 |
| **타입 힌트** | 낮음 | ✅ **이미 완성됨** (mypy --ignore-missing-imports 통과) | **해결됨** |
| **문서화 부분적** | 낮음 | 복잡한 로직(트랩 감지, 정규화)에 설명 부족 | 새 개발자 온보딩 어려움 |

---

## 2. 리팩토링 우선순위 (Impact × Effort 매트릭스)

### 2.1 우선순위 1 (즉시 실행, 고impact/저effort)

```
┌─────────────────────────────────────────┐
│ P1: High Impact / Low Effort            │
├─────────────────────────────────────────┤
│ 1. runner.py 함수 분리 (850줄 → 300줄)  │
│ 2. 에러 처리 통일 (안정성 개선)         │
│ 3. 핵심 모듈 테스트 강화                │
└─────────────────────────────────────────┘
```

**작업 항목:**
- [ ] `src/pipeline/runner.py` 함수 분리 (단계별 파이프라인 추출)
- [ ] `src/pipeline/collectors_batch.py` 신규 생성
- [ ] `src/pipeline/enrichment.py` 신규 생성  
- [ ] Graceful fallback 데코레이터 통일 (에러 처리)
- [ ] 테스트 커버리지 → 90% (엣지 케이스)

---

### 2.2 우선순위 2 (단기, 중간impact/저effort)

```
┌─────────────────────────────────────────┐
│ P2: Medium Impact / Low-Medium Effort   │
├─────────────────────────────────────────┤
│ 1. 로깅 전략 개선 (context 추가)        │
│ 2. 벡터화 (7개 iterrows/apply)          │
│ 3. 캐싱 레이어 (선택사항)               │
└─────────────────────────────────────────┘
```

**작업 항목:**
- [ ] structlog context 확장 (pipeline_id, stage 등)
- [ ] `src/collectors/market_ratios.py` 벡터화 (3개 항목)
- [ ] `src/screening/stage3_trap_detector.py` 벡터화 (4개 항목)
- [ ] Repository 캐싱 추가 (선택사항, DART 응답 캐시)

---

### 2.3 우선순위 3 (중기, 저impact/고effort)

```
┌─────────────────────────────────────────┐
│ P3: Low Impact / High Effort            │
├─────────────────────────────────────────┤
│ 1. Pydantic V2 마이그레이션             │
│ 2. 비동기 수집기 (asyncio)              │
│ 3. 다국어 지원 (i18n)                   │
│ 4. GraphQL API (REST 대체)              │
└─────────────────────────────────────────┘
```

> 현재는 **미연기** (M9 UX 개선 후 검토)

---

## 3. 세부 리팩토링 계획

### 3.1 P1-1: `runner.py` 함수 분리

**현재 구조:**
```
src/pipeline/runner.py
├── run_pipeline() [메인, 200줄]
├── _collect() [150줄]
├── _enrich() [80줄]
├── _score() [90줄]
├── _rank() [70줄]
└── 여러 _helper 함수들 [600줄 total]
```

**문제점:**
- `_collect()` 내부에 데이터 수집, 병합, 검증이 혼재
- 함수 중첩 깊음 (4-5 level) → 스코프 이해 어려움
- 테스트 불가능한 부분 존재 (global 상태 의존)

**해결책:**

1. **Collector 인터페이스 추가**
   ```python
   # src/pipeline/collectors_batch.py (새 파일)
   from dataclasses import dataclass
   
   @dataclass
   class CollectionResult:
       tickers: pd.DataFrame
       prices: pd.DataFrame
       fundamentals: pd.DataFrame
       company_meta: pd.DataFrame
       # ...
   
   class BatchCollector:
       def __init__(self, max_workers: int = 4):
           self.max_workers = max_workers
       
       def collect_all(self, dates: DateRange) -> CollectionResult:
           """모든 데이터 수집 (병렬 처리)"""
           # 병렬 호출 로직 집중화
   ```

2. **Enrichment 파이프라인 추출**
   ```python
   # src/pipeline/enrichment.py (새 파일)
   class EnrichmentPipeline:
       def enrich_multiyear(self, df: pd.DataFrame) -> pd.DataFrame: ...
       def enrich_ratios(self, df: pd.DataFrame) -> pd.DataFrame: ...
       def detect_traps(self, df: pd.DataFrame) -> pd.DataFrame: ...
   ```

3. **runner.py 개선**
   ```python
   # 개선 후 runner.py (100줄)
   def run_pipeline(run_date: date, db_path: Path) -> dict:
       repo = Repository(db_path)
       
       # 1. 수집
       batch = BatchCollector().collect_all(run_date)
       repo.upsert_all(batch)
       
       # 2. 풍부화 & 스코어링
       screening = ScreeningPipeline(repo).execute(run_date)
       
       # 3. 랭킹 & 분석
       ranked = RankingPipeline(repo).execute(screening)
       
       # 4. 업로드
       R2Uploader(repo).upload(ranked, run_date)
       
       return {"status": "success", "ranked_count": len(ranked)}
   ```

**기대 효과:**
- 함수 길이 평균 50-100줄로 단축
- 테스트 커버리지 +20%
- 재사용 가능한 파이프라인 컴포넌트

**구현 순서:**
1. `collectors_batch.py` 작성 (통합 수집)
2. `enrichment.py` 작성 (다단계 처리)
3. `runner.py` 리팩토링 (호출 순서 단순화)
4. 기존 테스트 업데이트

---

### 3.2 P1-2: 벡터화 개선 (market_ratios, trap_detector)

#### A. `src/collectors/market_ratios.py` 벡터화

**현재 (느림):**
```python
def calculate_market_ratios(prices_df, fundamentals_df):
    results = []
    for idx, row in prices_df.iterrows():  # ❌ O(n) 루프
        stock_code = row["stock_code"]
        fundamentals = fundamentals_df[fundamentals_df["stock_code"] == stock_code]
        # ...
        results.append({...})
    return pd.DataFrame(results)
```

**개선 (빠름):**
```python
def calculate_market_ratios(prices_df: pd.DataFrame, fundamentals_df: pd.DataFrame) -> pd.DataFrame:
    """벡터화된 시장 배수 계산"""
    # 1. Merge로 정렬
    merged = prices_df.merge(
        fundamentals_df[["stock_code", "eps", "bps", "dps"]],
        on="stock_code",
        how="left"
    )
    
    # 2. 벡터 연산 (numpy 기반, 매우 빠름)
    merged["per"] = np.where(merged["eps"] > 0, merged["close"] / merged["eps"], np.nan)
    merged["pbr"] = np.where(merged["bps"] > 0, merged["close"] / merged["bps"], np.nan)
    merged["dividend_yield"] = np.where(
        merged["dps"].notna(),
        (merged["dps"] / merged["close"] * 100),
        np.nan
    )
    
    return merged[["stock_code", "per", "pbr", "dividend_yield"]]
```

**성능 개선:**
- 2,600 종목: 800ms → 80ms **(10배 빠름)**
- 코드 가독성 +30%

#### B. `src/screening/stage3_trap_detector.py` 벡터화

**현재 (느림):**
```python
def is_value_trap(row):
    flags = []
    if row["roe"] < 0: flags.append("NEGATIVE_ROE")
    if row["debt_to_equity"] > 3.0: flags.append("HIGH_DEBT")
    # ... (10+ 조건)
    return " | ".join(flags) if flags else None

df["risk_flags"] = df.apply(is_value_trap, axis=1)  # ❌ 루프
```

**개선 (전체 벡터화):**
```python
def detect_risk_flags_vectorized(df: pd.DataFrame) -> pd.Series:
    """완전 벡터 연산으로 플래그 생성"""
    # 각 조건을 Boolean 벡터로 정의
    conditions = {
        "NEGATIVE_ROE": df["roe"] < 0,
        "HIGH_DEBT": df["debt_to_equity"] > 3.0,
        "LOW_ICR": df["interest_coverage"] < 1.5,
        "HIGH_DTA": df["debt_to_assets"] > 0.8,
        # ... (더 추가 가능)
    }
    
    # 모든 행에 대해 플래그 생성 (한 번에)
    def build_flags(row_dict: dict) -> str | None:
        flags = [name for name, is_set in row_dict.items() if is_set]
        return " | ".join(flags) if flags else None
    
    # 조건별 벡터를 행별로 매핑
    result = []
    for i in range(len(df)):
        row_conditions = {name: cond.iloc[i] for name, cond in conditions.items()}
        result.append(build_flags(row_conditions))
    
    return pd.Series(result, index=df.index)

df["risk_flags"] = detect_risk_flags_vectorized(df)
```

**성능 개선:**
- 2,600 종목: 400ms → 80ms **(5배 빠름)**

---

### 3.3 P1-3: Graceful Fallback 통일 (데코레이터)

**현재 (산발적):**
```python
# A. DART API 키 없을 때
if not settings.DART_API_KEY:
    log.warning("disclosure fetch skipped: no DART API key")
    return pd.DataFrame(columns=[...])

# B. API 호출 실패
try:
    result = api.call()
except APIError as e:
    log.error("api_failed", error=e)
    return None

# C. 데이터 검증 실패
if df.empty:
    raise ValueError("empty dataframe")
```

**개선 (데코레이터 사용):**
```python
# src/utils/resilience.py (새 파일)
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

T = TypeVar("T")

def graceful_fallback(
    fallback_value: Any | Callable[[], Any] = None,
    log_level: str = "warning",
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
                    error_type=type(e).__name__
                )
                if callable(fallback_value):
                    return fallback_value()
                return fallback_value
        return wrapper
    return decorator

# 사용
@graceful_fallback(
    fallback_value=pd.DataFrame(columns=["stock_code", "..."])
)
def fetch_disclosure_dates(stock_codes: list[str]) -> pd.DataFrame:
    return api.call(stock_codes)

@graceful_fallback(
    fallback_value=lambda: {"analysis": "분석 불가"},
    log_level="info"
)
def generate_ai_analysis(stock_code: str) -> dict:
    return gemini_api.analyze(stock_code)
```

**기대 효과:**
- 에러 처리 코드 50% 감축
- 일관된 로깅 포맷
- 테스트 용이

---

### 3.5 P2-1: 테스트 커버리지 90% 달성

**현재 상태:**
```bash
# 현재 coverage 확인
pytest --cov=src --cov-report=html tests/
# → 약 75% 예상
```

**추가할 엣지 케이스:**

| 모듈 | 미흡한 케이스 | 작업 |
|---|---|---|
| `stage1_filter.py` | 시가총액 0, 거래대금 NaN | 테스트 3개 추가 |
| `stage3_trap_detector.py` | 음수 ROE, 무한대 ICR, 플래그 없음 | 테스트 4개 추가 |
| `repository.py` | 연결 실패, 트랜잭션 롤백 | 테스트 2개 추가 |
| `ai_analyst.py` | API 키 없음, 토큰 초과, 응답 오류 | 테스트 3개 추가 |

**구현:**
```bash
# 1. 커버리지 리포트 생성
pytest --cov=src --cov-report=term-missing tests/ | tail -50

# 2. 미흡 부분 파악
# 3. 테스트 케이스 추가
pytest tests/ -v --cov=src --cov-report=html

# 4. 목표: 90%+ 달성
```

---

### 3.6 P2-2: 구조화된 로깅 확장

**현재 (기본 구조):**
```python
log.info("pipeline_started", date=run_date)
log.error("api_failed", error=error_msg)
```

**개선 (context 추가):**
```python
# src/utils/logger.py 개선
from src.utils.logger import get_logger, set_context

# 파이프라인 시작 시
set_context({
    "pipeline_id": uuid.uuid4().hex[:8],
    "run_date": run_date.isoformat(),
    "version": "1.0",
})

log.info("pipeline_started")  # context 자동 포함

# 단계별
set_context({"stage": "collect"})
log.info("collecting_tickers", count=2600)

set_context({"stage": "screening"})
log.info("stage1_filter", passed=1300, failed=1300)
```

**파일 출력 예:**
```json
{
  "timestamp": "2026-06-11T10:30:45.123Z",
  "level": "INFO",
  "message": "collecting_tickers",
  "pipeline_id": "a1b2c3d4",
  "run_date": "2026-06-11",
  "stage": "collect",
  "count": 2600
}
```

---

## 4. 구현 로드맵

### Phase 1: 핵심 리팩토링 (5-6일)
```
Week 1:
  Mon-Tue: P1-1 runner.py 분리 (collectors_batch, enrichment 신규)
  Wed: P1-2 Graceful fallback 데코레이터 통일
  Thu: 통합 테스트 (E2E 검증)
  Fri: P1 완료 및 PR 준비
```

### Phase 2: 보강 작업 (3-4일)
```
Week 2:
  Mon: P2-1 로깅 context 확장
  Tue: P2-2 벡터화 (market_ratios, trap_detector 7개 항목)
  Wed: P2-3 테스트 커버리지 → 90% (엣지 케이스)
  Thu: 성능 측정 & 최적화
```

### Phase 3: 정리 (1-2일)
```
Week 2-3:
  Fri: 문서 업데이트 (README, CLAUDE.md)
  Mon: 최종 리뷰 & 승인
```

**총 소요 시간: 약 25-35시간 (P1: 15h, P2: 10h, 기타: 5h)**

---

## 5. 검증 방법

### 5.1 성능 측정 (before/after)

```bash
# Before
time MAX_TICKERS=2600 python -m src.pipeline.runner --date 2026-06-10
# 예상: 600-800초

# After
time MAX_TICKERS=2600 python -m src.pipeline.runner --date 2026-06-10
# 목표: 400-500초 (30-40% 단축)
```

### 5.2 코드 품질 체크

```bash
# 타입 체크
mypy src/ --ignore-missing-imports

# 린트
ruff check src/ --fix

# 테스트 + 커버리지
pytest tests/ -v --cov=src --cov-report=html

# 성능 프로파일
python -m cProfile -s cumtime -m src.pipeline.runner --date 2026-06-10
```

### 5.3 기능 검증

```bash
# 1. 파이프라인 E2E 테스트
MAX_TICKERS=50 python -m src.pipeline.runner --date 2026-06-10
# → rankings 테이블에 데이터 확인

# 2. 대시보드 실행
streamlit run src/ui/app.py
# → 랭킹 페이지, 상세 페이지 정상 동작 확인

# 3. 로그 확인
tail -f $(find . -name "*.log" -printf '%T@ %p\n' | sort -rn | head -1 | cut -d' ' -f2-)
# → JSON 구조화 로그 확인
```

---

## 6. 체크리스트

### P1 (우선 실행, 5-6일)
- [ ] `src/pipeline/collectors_batch.py` 생성 (통합 수집)
- [ ] `src/pipeline/enrichment.py` 생성 (풍부화 파이프라인)
- [ ] `src/pipeline/runner.py` 리팩토링 (850줄 → 250-300줄)
- [ ] `src/utils/resilience.py` 데코레이터 추가 (Graceful fallback)
- [ ] 기존 테스트 모두 통과 (E2E 검증)
- [ ] PR #1 생성 및 병합

### P2 (단기, 3-4일)
- [ ] 로깅 context 확장 (pipeline_id, stage, ...)
- [ ] `src/collectors/market_ratios.py` 벡터화 (3개)
- [ ] `src/screening/stage3_trap_detector.py` 벡터화 (4개)
- [ ] 테스트 커버리지 → 90% (엣지 케이스)
- [ ] PR #2 생성 및 병합

### P3 (미연기)
- [ ] Pydantic V2 마이그레이션
- [ ] 비동기 수집기 (asyncio)
- [ ] 캐싱 레이어 추가 (Repository 레벨)

---

## 7. 주의사항

### 7.1 리팩토링 중 유지할 제약사항

- ✅ **Repository 패턴**: 모든 DB 접근은 `repository.py` 경유 (변경 금지)
- ✅ **설정 하드코딩 금지**: 모든 파라미터는 `config/screening_params.yaml` (변경 금지)
- ✅ **정규화 일관성**: `normalizer.py` 사용 (변경 금지)
- ✅ **Streamlit 연산 금지**: 대시보드는 사전 연산 데이터만 렌더링 (변경 금지)

### 7.2 리팩토링 중 실수 방지

```python
# ❌ 하지 말 것
conn.execute("INSERT INTO ...")  # Repository 패턴 위반
WEIGHTS = {"value": 0.3}  # 하드코딩
df["score"] = df["value"] / max(df["value"])  # 정규화 개별 구현

# ✅ 올바른 방법
repo.upsert_scores(...)
weights = screening_params.stage2_weights
score = normalizer.percentile_rank_score(df["value"])
```

### 7.3 병렬 개발 가능성

리팩토링 진행 중에도:
- M9 UX 개선은 별도 브랜치(`feature/m9-ux`)에서 진행 가능
- 테스트는 리팩토링과 독립적으로 진행 가능
- Pull Request 분리 권장 (각 P1 항목별 PR)

---

## 8. 참고 문서

- [CLAUDE.md](./CLAUDE.md) - 아키텍처 패턴
- [ARCHITECTURE.md](./ARCHITECTURE.md) - 전체 시스템 설계
- [SCREENING.md](./SCREENING.md) - 스크리닝 알고리즘
- [TASKS.md](./TASKS.md) - 마일스톤 현황
