# 미사용 코드 보고서

> 2026-06-11 코드 정리 대상 분석

---

## 1. 완전 미사용 함수 (제거 권장)

### 1.1 `_extract_code_from_isin()` 🔴 **제거**

**위치**: `src/collectors/krx_prices.py:327`

```python
def _extract_code_from_isin(isin: object) -> str:
    """ISIN 코드에서 KRX 종목코드 추출"""
    # 구현 있음
```

**현황**:
- 정의만 있음
- 어디서도 호출되지 않음 ❌
- 테스트 없음

**권장 조치**: **완전 제거**

---

### 1.2 `load_rankings_skip_stage1()` 🟡 **확인 필요**

**위치**: `src/ui/data_loader.py:149`

```python
@st.cache_data(ttl=1800)
def load_rankings_skip_stage1(market: str | None = None, min_score: float = 0.0) -> pd.DataFrame:
    """Stage1 필터를 무시하고 모든 점수를 반환한다 (테스트용)."""
```

**현황**:
- 정의만 있음 (테스트용이라고 명시)
- 어디서도 호출되지 않음 ❌
- UI 코드에서 미사용

**권장 조치**: 
- 테스트 환경에서 필요한지 확인 후 제거
- 또는 `# deprecated` 주석 추가하고 보관

---

### 1.3 `_shift_query_date()` 🔴 **제거**

**위치**: `src/collectors/krx_prices.py` (약 280줄 근처)

```python
def _shift_query_date(...) -> str:
    """구식 날짜 처리 함수"""
```

**현황**:
- 정의만 있음
- 호출 없음 ❌
- 테스트 없음

**권장 조치**: **완전 제거**

---

### 1.4 `_normalize_history_frame()` 🔴 **제거**

**위치**: `src/collectors/krx_prices.py`

```python
def _normalize_history_frame(...) -> pd.DataFrame:
    """구식 가격 정규화"""
```

**현황**:
- 정의만 있음
- 호출 없음 ❌
- 테스트 없음

**권장 조치**: **완전 제거**

---

## 2. 테스트에서만 사용되는 함수 (검토 필요)

### 2.1 `fetch_price_history_1y()` 🟡 **검토 권장**

**위치**: `src/collectors/krx_prices.py:193`

```python
def fetch_price_history_1y(
    base_date: str | date | None = None,
    tickers: pd.DataFrame | None = None,
    lookback_days: int = 260,
    max_rows_per_ticker: int = 252,
) -> pd.DataFrame:
```

**현황**:
- 정의: ✅
- runner.py에서 호출: ❌ **미사용**
- 테스트에서 호출: ✅ (5개 테스트)

**분석**:
- 1년 주가 이력 수집 함수
- TASKS.md에서 M1-5로 정의됨
- 하지만 현재 파이프라인에서는 `fetch_daily_price_data()`만 사용

**권장 조치**:
```
옵션 1: runner.py에 통합 (모멘텀 계산용)
옵션 2: 테스트용으로 보관 (테스트 커버 있으므로 안전)
옵션 3: 향후 모멘텀 개선 시 재활성화
```

---

### 2.2 `fetch_avg_trading_value_20d()` 🟡 **검토 권간**

**위치**: `src/collectors/krx_prices.py:89`

```python
def fetch_avg_trading_value_20d(
    base_date: str | date | None = None,
    tickers: pd.DataFrame | None = None,
    lookback_days: int = 30,
    window: int = 20,
    conn: sqlite3.Connection | None = None,
) -> pd.DataFrame:
```

**현황**:
- 정의: ✅
- runner.py에서 호출: ❌ **미사용**
- 테스트에서 호출: ✅ (5개 테스트)

**분석**:
- Stage 1 필터에서 거래대금 기준에 사용되도록 설계됨
- TASKS.md M1-4로 정의됨
- 하지만 현재는 `fetch_daily_price_data()`의 `trading_value`를 직접 사용

**권장 조치**:
```
옵션 1: runner.py에서 활성화 (더 정확한 거래대금 필터링)
옵션 2: 불필요하면 제거 (현재 로직으로 충분하면)
옵션 3: 테스트용으로만 보관
```

---

## 3. 테스트 커버리지 없는 중요 파일

**테스트가 없는 파일 13개:**

| 파일 | 영향도 | 권장 조치 |
|---|---|---|
| `src/analysis/ai_analyst.py` | 🔴 높음 | 테스트 추가 필요 |
| `src/collectors/dart_corporate_info.py` | 🟡 중간 | 테스트 추가 권장 |
| `src/collectors/dart_news.py` | 🟡 중간 | 테스트 추가 권장 |
| `src/collectors/krx_client.py` | 🔴 높음 | 테스트 추가 필요 |
| `src/screening/stage3_trap_detector.py` | 🔴 높음 | 테스트 추가 필요 |
| `src/screening/stage5_ai_analysis.py` | 🟡 중간 | 테스트 추가 권장 |
| `src/ui/app.py` | 🟢 낮음 | Streamlit은 일반적으로 테스트 어려움 |
| `src/ui/components/*.py` | 🟢 낮음 | UI 컴포넌트는 수동 테스트 권장 |
| `src/ui/views/*.py` | 🟢 낮음 | UI 페이지는 수동 테스트 권장 |
| `src/utils/concurrent.py` | 🟡 중간 | 테스트 추가 권장 |
| `src/utils/config.py` | 🟡 중간 | 테스트 추가 권장 (설정은 중요) |
| `src/utils/error_handling.py` | 🟡 중간 | 테스트 추가 권장 |
| `src/utils/industry_mapper.py` | 🟡 중간 | 테스트 추가 권장 |

---

## 4. 의심스러운 import

### 4.1 미사용 import 확인

**검사 대상**:
- `src/utils/config.py`: 모든 import 사용 ✅
- `src/pipeline/runner.py`: 확인 필요

---

## 5. 정리 액션 플랜

### Phase 1: 즉시 제거 (낮은 위험)
```
☐ _extract_code_from_isin() 제거
☐ _shift_query_date() 제거  
☐ _normalize_history_frame() 제거
```

**예상 시간**: 10분  
**영향도**: 매우 낮음 (사용 안 함)

---

### Phase 2: 검토 후 결정 (중간 위험)
```
☐ load_rankings_skip_stage1() 검토
   - 실제로 테스트에서 필요한지 확인
   - 필요 없으면 제거

☐ fetch_price_history_1y() 검토
   - 모멘텀 계산에 필요한지 확인
   - 필요하면 runner.py에 통합
   - 불필요하면 제거

☐ fetch_avg_trading_value_20d() 검토
   - 거래대금 필터링에 필요한지 확인
   - 필요하면 runner.py에 통합
   - 불필요하면 제거
```

**예상 시간**: 30분  
**영향도**: 낮음-중간 (테스트 코드 있음)

---

### Phase 3: 테스트 추가 (중간 위험)

**우선순위 높음** (핵심 로직):
```
☐ src/analysis/ai_analyst.py (3-4시간)
☐ src/collectors/krx_client.py (2-3시간)
☐ src/screening/stage3_trap_detector.py (2-3시간)
```

**우선순위 중간** (지원 로직):
```
☐ src/collectors/dart_corporate_info.py (2시간)
☐ src/screening/stage5_ai_analysis.py (2시간)
☐ src/utils/config.py (1시간)
☐ src/utils/concurrent.py (1시간)
```

**예상 총 시간**: 13-16시간  
**영향도**: 높음 (테스트 커버리지 +15-20%)

---

## 6. 실행 가이드

### 6.1 즉시 실행 (5분)

```bash
# 1단계: 미사용 함수 제거 확인
git grep "_extract_code_from_isin\|_shift_query_date\|_normalize_history_frame"

# 2단계: 안전하게 제거
# src/collectors/krx_prices.py에서 해당 함수 삭제

# 3단계: 테스트 실행
pytest tests/test_collectors/test_krx_prices.py -v

# 4단계: 커밋
git add -A && git commit -m "refactor: remove unused helper functions"
```

---

### 6.2 검토 후 실행 (1시간)

```bash
# 각 함수별로 다음을 확인:
# 1. grep -r "함수명" src/ --include="*.py" (runner.py에서 사용?)
# 2. 테스트 실행 후 제거 시 영향 확인
# 3. 필요 시 runner.py에 통합
```

---

## 7. 체크리스트

### 코드 정리
- [ ] Phase 1: 완전 미사용 3개 함수 제거
- [ ] Phase 2: 테스트전용 2개 함수 검토 후 결정
- [ ] Phase 3: 불필요한 import 제거 (찾은 것 있으면)

### 테스트 추가
- [ ] 높은 우선순위 파일들 테스트 추가 (3개)
- [ ] 중간 우선순위 파일들 테스트 추가 (4개)
- [ ] 최종 커버리지 90%+ 달성

### 검증
- [ ] 기존 테스트 모두 통과
- [ ] E2E 파이프라인 정상 동작
- [ ] PR 리뷰 & 병합

---

## 8. 예상 효과

**코드 정리 완료 후:**
- 파일 크기: 약 100줄 감소
- 복잡도: 낮아짐
- 유지보수성: +10%
- 가독성: +5%
- 혼동 가능성: -20% (미사용 함수 제거)

---

## 참고

- [REFACTORING_STRATEGY.md](./REFACTORING_STRATEGY.md) - 전체 리팩토링 계획
- [TASKS.md](./TASKS.md) - 마일스톤 및 함수 설계 기록
