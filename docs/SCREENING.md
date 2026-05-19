# 4단계 스크리닝 설계

> **ValueForge** | 가치 투자 필터링·스코어링·가치 함정 감지

## 목차

1. [개요](#1-개요)
2. [Stage 1 — 빠른 필터](#2-stage-1--빠른-필터)
3. [Stage 2 — 심화 스코어링](#3-stage-2--심화-스코어링)
4. [Stage 3 — 가치 함정 감지](#4-stage-3--가치-함정-감지)
5. [Stage 4 — 최종 랭킹](#5-stage-4--최종-랭킹)
6. [스코어링 가중치 설정](#6-스코어링-가중치-설정)

---

## 1. 개요

한국 시장은 KOSPI·KOSDAQ 합산 약 2,500-2,800개 활성 종목이 있다. 파이프라인은 4단계를 거쳐 30-80개의 진정한 가치 후보군으로 축소한다.

```
전체 종목 (~2,600개)
       │
       │ Stage 1: 빠른 필터 (주가 데이터만 사용)
       ▼
~400-700개
       │
       │ Stage 2: 심화 스코어링 (DART 재무 데이터 활용)
       ▼
~400-700개 (복합 점수 부여)
       │
       │ Stage 3: 가치 함정 감지
       ▼
~300-600개 (함정 플래그/제거)
       │
       │ Stage 4: 최종 랭킹
       ▼
상위 50-100개 후보
```

모든 스코어는 **현재 스크리닝 유니버스 내 백분위 순위**로 정규화된다. 절대 기준이 아닌 시장 상대 비교다.

---

## 2. Stage 1 — 빠른 필터

**목적**: pykrx에서 직접 제공하는 주가·기본 비율 데이터만으로 명백히 비가치인 종목 제거. DART 데이터 불필요.

### 기준 (모두 통과해야 함)

| 지표 | 기준값 | 근거 |
|---|---|---|
| 시가총액 | ≥ 500억 원 | 소형주 제거 (유동성·조작 리스크) |
| 20일 평균 일 거래대금 | ≥ 500억 원 | 최소 유동성 (진입·청산 가능) |
| PER | 1 < PER ≤ 30 | 적자 종목 및 극단적 고평가 제외 |
| PBR | 0.1 < PBR ≤ 3.0 | 심각한 부실·고평가 종목 제외 |
| 상장 기간 | ≥ 1년 | 신규 상장 투기 종목 제외 |
| 활성 여부 | `is_active = 1` | 거래정지·상장폐지 종목 제외 |

### 구현

```python
# src/screening/stage1_filter.py

def stage1_filter(df: pd.DataFrame) -> pd.DataFrame:
    """
    입력: stock_code, market_cap, avg_volume_20d, per, pbr,
          listing_years, is_active 컬럼 포함 DataFrame
    출력: 필터 통과 종목 DataFrame
    """
    mask = (
        (df['market_cap'] >= 50_000)           # 500억 원 (백만 원 단위)
        & (df['avg_volume_20d'] >= 50_000)     # 500억 원 일 거래대금
        & (df['per'] > 1) & (df['per'] <= 30)
        & (df['pbr'] > 0.1) & (df['pbr'] <= 3.0)
        & (df['listing_years'] >= 1)
        & (df['is_active'] == 1)
        & df['per'].notna()
        & df['pbr'].notna()
    )
    return df[mask].copy()
```

---

## 3. Stage 2 — 심화 스코어링

**목적**: Stage 1 통과 종목에 5차원 복합 점수(0-100) 부여. DART 재무 데이터 활용.

### 정규화 전략

```python
# src/scoring/normalizer.py

def percentile_rank_score(
    series: pd.Series,
    higher_is_better: bool = True
) -> pd.Series:
    """
    스크리닝 유니버스 내 백분위 순위 기반 0-100 점수 반환.
    절대 기준이 아닌 유니버스 상대 비교.
    """
    ranked = series.rank(pct=True, na_option='bottom')
    if not higher_is_better:
        ranked = 1 - ranked
    return (ranked * 100).clip(0, 100)
```

---

### 3.1 가치 점수 (Value Score) — 가중치 30%

저평가 정도를 측정한다.

| 지표 | 가중치 | 방향 | 출처 |
|---|---|---|---|
| PER (역수) | 30% | 낮을수록 좋음 | pykrx |
| PBR (역수) | 25% | 낮을수록 좋음 | pykrx |
| EV/EBITDA (역수) | 25% | 낮을수록 좋음 | 산출값 |
| 배당수익률 | 20% | 높을수록 좋음 | pykrx |

```python
# src/scoring/value_scorer.py

def compute_value_score(df: pd.DataFrame) -> pd.Series:
    per_score     = percentile_rank_score(df['per'],        higher_is_better=False)
    pbr_score     = percentile_rank_score(df['pbr'],        higher_is_better=False)
    ev_ebitda     = (df['market_cap'] + df['total_debt'] - df['cash_and_equiv']) / df['ebitda']
    ev_score      = percentile_rank_score(ev_ebitda,        higher_is_better=False)
    div_score     = percentile_rank_score(df['dividend_yield'], higher_is_better=True)

    return (
        per_score  * 0.30 +
        pbr_score  * 0.25 +
        ev_score   * 0.25 +
        div_score  * 0.20
    )
```

---

### 3.2 품질 점수 (Quality Score) — 가중치 25%

사업 품질 및 수익성 일관성을 측정한다.

| 지표 | 가중치 | 방향 |
|---|---|---|
| ROE | 30% | 높을수록 좋음 |
| ROA | 25% | 높을수록 좋음 |
| 영업이익률 | 25% | 높을수록 좋음 |
| ROE 3년 표준편차 (역수) | 20% | 낮을수록 좋음 (안정성) |

```python
# src/scoring/quality_scorer.py

def compute_quality_score(df: pd.DataFrame) -> pd.Series:
    roe_score   = percentile_rank_score(df['roe'],              higher_is_better=True)
    roa_score   = percentile_rank_score(df['roa'],              higher_is_better=True)
    margin_score = percentile_rank_score(df['operating_margin'], higher_is_better=True)
    stability   = percentile_rank_score(df['roe_3yr_std'],      higher_is_better=False)

    return (
        roe_score    * 0.30 +
        roa_score    * 0.25 +
        margin_score * 0.25 +
        stability    * 0.20
    )
```

---

### 3.3 안전성 점수 (Safety Score) — 가중치 20%

재무 건전성 및 지급 능력을 측정한다.

| 지표 | 가중치 | 방향 |
|---|---|---|
| 부채비율 (역수) | 35% | 낮을수록 좋음 |
| 유동비율 | 35% | 높을수록 좋음 |
| 이자보상배율 (EBITDA/이자비용) | 30% | 높을수록 좋음 |

```python
# src/scoring/safety_scorer.py

def compute_safety_score(df: pd.DataFrame) -> pd.Series:
    de_score = percentile_rank_score(df['debt_to_equity'],   higher_is_better=False)
    cr_score = percentile_rank_score(df['current_ratio'],    higher_is_better=True)
    ic_score = percentile_rank_score(df['interest_coverage'],higher_is_better=True)

    return (
        de_score * 0.35 +
        cr_score * 0.35 +
        ic_score * 0.30
    )
```

---

### 3.4 성장성 점수 (Growth Score) — 가중치 15%

이익·매출 성장 궤적을 측정한다.

| 지표 | 가중치 | 방향 |
|---|---|---|
| 매출 YoY 성장률 | 25% | 높을수록 좋음 |
| 영업이익 YoY 성장률 | 35% | 높을수록 좋음 |
| EPS YoY 성장률 | 25% | 높을수록 좋음 |
| FCF YoY 성장률 | 15% | 높을수록 좋음 |

```python
# src/scoring/growth_scorer.py

def compute_growth_score(df: pd.DataFrame) -> pd.Series:
    rev_g = percentile_rank_score(df['revenue_growth_yoy'],   higher_is_better=True)
    op_g  = percentile_rank_score(df['op_profit_growth_yoy'], higher_is_better=True)
    eps_g = percentile_rank_score(df['eps_growth_yoy'],       higher_is_better=True)
    fcf_g = percentile_rank_score(df['fcf_growth_yoy'],       higher_is_better=True)

    return (
        rev_g * 0.25 +
        op_g  * 0.35 +
        eps_g * 0.25 +
        fcf_g * 0.15
    )
```

---

### 3.5 모멘텀 점수 (Momentum Score) — 가중치 10%

시장 대비 최근 주가 추세를 측정한다. 가치+모멘텀 조합은 실증적으로 강한 팩터다.

| 지표 | 가중치 | 방향 |
|---|---|---|
| 6개월 수익률 vs KOSPI | 50% | 높을수록 좋음 |
| 3개월 수익률 vs KOSPI | 30% | 높을수록 좋음 |
| 1개월 수익률 (절대) | 20% | 높을수록 좋음 |

```python
# src/scoring/momentum_scorer.py

def compute_momentum_score(
    df: pd.DataFrame,
    kospi_6m: float,
    kospi_3m: float
) -> pd.Series:
    rel_6m = df['return_6m'] - kospi_6m
    rel_3m = df['return_3m'] - kospi_3m

    mom6_score = percentile_rank_score(rel_6m,         higher_is_better=True)
    mom3_score = percentile_rank_score(rel_3m,         higher_is_better=True)
    mom1_score = percentile_rank_score(df['return_1m'],higher_is_better=True)

    return (
        mom6_score * 0.50 +
        mom3_score * 0.30 +
        mom1_score * 0.20
    )
```

---

### 3.6 복합 점수 산출

```python
# src/screening/stage2_scorer.py

WEIGHTS = {
    'value':    0.30,
    'quality':  0.25,
    'safety':   0.20,
    'growth':   0.15,
    'momentum': 0.10,
}

def compute_composite_score(df: pd.DataFrame) -> pd.Series:
    return (
        df['value_score']    * WEIGHTS['value'] +
        df['quality_score']  * WEIGHTS['quality'] +
        df['safety_score']   * WEIGHTS['safety'] +
        df['growth_score']   * WEIGHTS['growth'] +
        df['momentum_score'] * WEIGHTS['momentum']
    )
```

> **가중치 변경**: `config/screening_params.yaml`에서 관리. 코드에 하드코딩 금지.

---

## 4. Stage 3 — 가치 함정 감지

**목적**: 겉보기에 저렴하지만 구조적 문제가 있어 "가치 함정"인 종목 식별. PER·PBR이 낮아도 가격이 낮은 데는 이유가 있다.

### 플래그 정의

```python
# src/screening/stage3_trap_detector.py

VALUE_TRAP_FLAGS = {

    # CRITICAL — 자동 실격
    'NEGATIVE_EQUITY': {
        'condition': lambda f: f['total_equity'] <= 0,
        'description': '자기자본이 마이너스 (기술적 부도 상태)',
        'severity': 'CRITICAL'
    },
    'PERSISTENT_OPERATING_LOSS': {
        'condition': lambda f: (f['op_profit_yr1'] < 0) & (f['op_profit_yr2'] < 0),
        'description': '2년 연속 영업손실',
        'severity': 'CRITICAL'
    },

    # HIGH — 강한 실격 신호
    'NEGATIVE_ROE': {
        'condition': lambda f: f['roe'] < -5,
        'description': 'ROE가 -5% 미만 (자본 훼손)',
        'severity': 'HIGH'
    },
    'EXCESSIVE_DEBT': {
        'condition': lambda f: f['debt_to_equity'] > 3.0,
        'description': '부채비율 300% 초과 (지급불능 리스크)',
        'severity': 'HIGH'
    },
    'PERSISTENT_NEGATIVE_FCF': {
        'condition': lambda f: (
            (f['fcf_yr1'] < 0) & (f['fcf_yr2'] < 0) & (f['fcf_yr3'] < 0)
        ),
        'description': '3년 연속 잉여현금흐름(FCF) 적자',
        'severity': 'HIGH'
    },
    'REVENUE_COLLAPSE': {
        'condition': lambda f: f['revenue_growth_yoy'] < -20,
        'description': '매출 YoY 20% 이상 감소',
        'severity': 'HIGH'
    },

    # MEDIUM — 경고 (자동 실격 아님)
    'DECLINING_MARGINS': {
        'condition': lambda f: (
            (f['op_margin_yr1'] < f['op_margin_yr2']) &
            (f['op_margin_yr2'] < f['op_margin_yr3'])
        ),
        'description': '3년 연속 영업이익률 하락',
        'severity': 'MEDIUM'
    },
    'DECLINING_REVENUE': {
        'condition': lambda f: f['revenue_growth_yoy'] < -5,
        'description': '매출 YoY 5% 이상 감소',
        'severity': 'MEDIUM'
    },
    'LOW_INTEREST_COVERAGE': {
        'condition': lambda f: f['interest_coverage'] < 1.5,
        'description': 'EBITDA 이자보상배율 1.5배 미만 (채무상환 리스크)',
        'severity': 'MEDIUM'
    },

    # LOW — 정보성
    'HOLDING_COMPANY': {
        'condition': lambda f: f['industry'] == '지주회사',
        'description': '지주회사 (구조적 할인 가능성)',
        'severity': 'LOW'
    },
    'HIGH_CAPEX': {
        'condition': lambda f: (f['capex'] / f['revenue']) > 0.15,
        'description': 'CAPEX가 매출의 15% 초과 (자본집약적)',
        'severity': 'LOW'
    },
}
```

### 자동 실격 규칙

```python
def is_value_trap(flags: list[dict]) -> bool:
    """
    다음 조건 중 하나라도 해당하면 True (랭킹에서 완전 제외):
    - CRITICAL 플래그 1개 이상
    - HIGH 플래그 2개 이상
    """
    has_critical = any(f['severity'] == 'CRITICAL' for f in flags)
    high_count   = sum(1 for f in flags if f['severity'] == 'HIGH')
    return has_critical or high_count >= 2
```

---

## 5. Stage 4 — 최종 랭킹

**목적**: 모든 필터 적용 후 최종 순위 목록 생성.

```python
# src/screening/stage4_ranker.py

def stage4_rank(df: pd.DataFrame) -> pd.DataFrame:
    # 자동 실격 가치 함정 제거
    df = df[~df['is_value_trap']].copy()

    # 잔존 리스크 플래그에 대한 복합 점수 패널티
    # MEDIUM 플래그 1개: -2점, HIGH 플래그 1개: -5점
    def apply_penalty(row) -> float:
        medium = row.get('medium_flag_count', 0) * 2
        high   = row.get('high_flag_count', 0)   * 5
        return max(0, row['composite_score'] - medium - high)

    df['adjusted_score'] = df.apply(apply_penalty, axis=1)

    # 조정 복합 점수 기준 내림차순 정렬
    df = df.sort_values('adjusted_score', ascending=False)
    df['final_rank'] = range(1, len(df) + 1)

    return df.head(100)  # 상위 100개 반환
```

### 랭킹 방법론 요약

1. CRITICAL 플래그 보유 종목 → 완전 제외
2. HIGH 플래그 2개 이상 종목 → 완전 제외
3. 잔존 종목을 복합 점수 - 리스크 패널티 기준으로 정렬
4. 상위 100개를 `rankings` 테이블에 기록

---

## 6. 스코어링 가중치 설정

가중치는 `config/screening_params.yaml`에서 관리한다. 코드 수정 없이 조정 가능.

```yaml
# config/screening_params.yaml

stage1:
  min_market_cap_million_krw: 50000     # 500억 원
  min_avg_daily_volume_million_krw: 5000 # 50억 원
  per_min: 1.0
  per_max: 30.0
  pbr_min: 0.1
  pbr_max: 3.0
  min_listing_years: 1

stage2_weights:
  value:    0.30
  quality:  0.25
  safety:   0.20
  growth:   0.15
  momentum: 0.10

stage3_trap_rules:
  excessive_debt_ratio: 3.0
  revenue_collapse_threshold: -0.20
  negative_roe_threshold: -5.0
  low_interest_coverage: 1.5

stage4:
  max_candidates: 100
  medium_flag_penalty: 2
  high_flag_penalty: 5
```
