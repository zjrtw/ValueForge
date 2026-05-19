# 향후 업그레이드 경로

> **ValueForge** | 주요 리팩토링 없이 아키텍처를 진화시키는 방법

## 목차

1. [설계 철학](#1-설계-철학)
2. [SQLite → PostgreSQL](#2-sqlite--postgresql)
3. [Streamlit → FastAPI + React](#3-streamlit--fastapi--react)
4. [cron → Celery 워커](#4-cron--celery-워커)
5. [AI 분석 추가](#5-ai-분석-추가)
6. [백테스팅 엔진 추가](#6-백테스팅-엔진-추가)
7. [알림 시스템 추가](#7-알림-시스템-추가)
8. [업그레이드 로드맵](#8-업그레이드-로드맵)

---

## 1. 설계 철학

현재 아키텍처는 각 컴포넌트를 독립적으로 교체할 수 있는 클린 경계로 설계되었다:

| 추상화 포인트 | 파일 | 교체 용이성 |
|---|---|---|
| Repository 패턴 | `src/db/repository.py` | SQLite → PostgreSQL: DB 레이어만 변경 |
| 추상 수집기 베이스 | `src/collectors/base_collector.py` | 새 데이터 소스 추가 시 스크리너 영향 없음 |
| 독립 스코어러 | `src/scoring/` | 각 차원 독립적으로 수정·추가 가능 |
| UI/데이터 분리 | Streamlit은 SQLite만 읽음 | 프론트엔드를 어떤 것으로든 교체 가능 |

---

## 2. SQLite → PostgreSQL

**트리거**: 동시 대시보드 사용자 100명 초과, 실시간 갱신 필요, 멀티 라이터 파이프라인.

**마이그레이션 경로**:

1. `src/db/repository.py`에서 `sqlite3` → `psycopg2` 또는 `asyncpg` 교체
2. SQL 문법 변경 최소화 (SQLite는 PostgreSQL과 대부분 호환)
3. [Neon](https://neon.tech) (서버리스 PostgreSQL, 넉넉한 무료 티어) 또는 [Supabase](https://supabase.com) 사용
4. 스키마는 동일 유지 — 인덱스만 PostgreSQL에 맞게 최적화

**코드 변경 범위**: `repository.py` 1개 파일만 변경. 파이프라인·스코어링·UI 코드 무변경.

**예상 작업량**: 2-3일

---

## 3. Streamlit → FastAPI + React

**트리거**: 커스텀 UI, 사용자 인증, 모바일 반응형, 고급 인터랙션 필요.

**마이그레이션 경로**:

1. `src/api/` 디렉토리에 FastAPI 백엔드 구축 — 기존 SQLite 쿼리를 REST 엔드포인트로 노출
2. React 프론트엔드가 Streamlit 대신 FastAPI에서 데이터 읽음
3. Streamlit은 내부 도구용으로 유지하면서 React가 사용자 서비스
4. FastAPI에서 JWT 인증, 레이트 리밋, 커스텀 비즈니스 로직 추가 가능

```
현재:     Streamlit → SQLite (직접 연결)
V2:       React → FastAPI → SQLite/PostgreSQL
```

**예상 작업량**: 2-4주

---

## 4. cron → Celery 워커

**트리거**: 다중 데이터 소스, 복잡한 재시도 로직, 병렬 수집, 실시간 처리 필요.

**마이그레이션 경로**:

1. Redis 브로커 추가 (Redis Cloud 무료 티어: 30MB)
2. 수집기 함수를 Celery 태스크로 래핑
3. APScheduler 또는 Celery Beat가 cron 대체
4. 워커 수평 확장 가능 — 각 워커가 종목 서브셋 수집

```python
# 예시: Celery 태스크로 전환
@celery_app.task(bind=True, max_retries=3)
def collect_ticker_data(self, stock_code: str) -> dict:
    try:
        return KRXCollector().get_price(stock_code)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
```

**예상 작업량**: 1-2주

---

## 5. AI 분석 추가

**트리거**: 사용자가 자연어 설명 또는 패턴 감지 기능 요청.

**마이그레이션 경로**:

1. `anthropic` SDK를 파이프라인 의존성에 추가
2. Stage 4 랭킹 완료 후 상위 10개 종목에 대해 Claude API로 간단한 분석 생성
3. `stock_analysis` 테이블을 SQLite에 추가
4. Streamlit 종목 상세 페이지에 AI 코멘터리 섹션 추가

**예상 비용**: 종목당 ~$0.01 × 10개 = $0.10/일 = ~$3/월

**예상 작업량**: 2-3일

→ Claude API 통합: [claude-api 스킬](../CLAUDE.md) 참조

---

## 6. 백테스팅 엔진 추가

**트리거**: 스크리닝 방법론을 과거 데이터로 검증하고 싶은 사용자 수요.

**마이그레이션 경로**:

1. `vectorbt` 또는 `backtrader` 라이브러리 추가
2. `src/backtesting/` 모듈 신설
3. R2의 `history/*.db` 파일들이 이미 과거 스크리닝 결과 보유 → 미래 주가 대비 백테스트 가능
4. Streamlit에 백테스트 결과 페이지 추가

**예상 작업량**: 2-4주 (실질적인 기능 영역)

---

## 7. 알림 시스템 추가

**트리거**: 사용자가 관심 종목 순위 변동 시 알림 원할 때.

**마이그레이션 경로 (Telegram 봇 — 가장 단순)**:

1. `python-telegram-bot` 추가
2. 파이프라인 완료 후 추가 단계: 전일 대비 랭킹 변동 비교
3. 큰 순위 변동 시 Telegram 봇으로 메시지 발송

**비용**: 무료 (Telegram API 무료)

**예상 작업량**: 2일

---

## 8. 업그레이드 로드맵

```
MVP (현재)
  │
  ├── V1.1: 점수 추세 차트 + 전일 델타 표시       [1주]
  ├── V1.2: 섹터 상대 스코어링                    [1주]
  ├── V1.3: Telegram 알림 (선택적 종목 모니터링)   [2일]
  └── V1.4: 상위 10개 종목 AI 코멘터리             [3일]

V2 (3-6개월 후)
  ├── FastAPI 백엔드                              [2-4주]
  ├── PostgreSQL 마이그레이션                     [2-3일]
  └── 백테스팅 엔진                              [2-4주]

V3 (6-12개월 후)
  ├── React 프론트엔드
  ├── 사용자 인증 (Clerk 또는 Supabase Auth)
  ├── 포트폴리오 추적
  └── 실시간 장중 데이터 (예산 허용 시)
```

### 교체 난이도 요약

| 컴포넌트 | 교체 난이도 | 사유 |
|---|---|---|
| SQLite → PostgreSQL | ★★☆☆☆ | Repository 패턴으로 DB 레이어 격리됨 |
| Streamlit → FastAPI 백엔드 | ★★★☆☆ | API 레이어 신설 필요, UI 로직은 그대로 |
| cron → Celery | ★★★☆☆ | 브로커 인프라 추가, 태스크 래핑 필요 |
| AI 분석 추가 | ★★☆☆☆ | 파이프라인에 후처리 단계만 추가 |
| React 프론트엔드 | ★★★★☆ | 완전히 새로운 기술 스택, 백엔드 API 필요 |
