# ValueForge

**한국 주식 가치 스크리너** — KOSPI·KOSDAQ 전 종목 대상 일일 자동 가치투자 스크리닝 플랫폼

---

## 프로젝트 개요

ValueForge는 매일 장 마감 후 자동으로 한국 주식 시장 전체를 스캔하여 가치투자 관점에서 매력적인 종목 후보를 선별한다. 벤저민 그레이엄·워렌 버핏 스타일의 4단계 스크리닝 파이프라인을 적용하고, 가치 함정을 감지·제거한 후 순위를 매겨 웹 대시보드로 제공한다.

**핵심 목표**: 무료 인프라로, 1인 개발자가 유지보수할 수 있는 시스템.

---

## 기술 스택

| 계층 | 기술 |
|---|---|
| 데이터 수집 | Python + pykrx + DART OpenAPI (open-dart-reader) |
| 데이터베이스 | SQLite (파일 기반, 서버 불필요) |
| 스토리지 | Cloudflare R2 (S3 호환, 무료 10GB) |
| 스케줄러 | Hetzner CX11 VPS + cron 또는 GitHub Actions |
| 대시보드 | Streamlit Cloud (무료 티어) |
| 언어 | Python 3.11+ |

---

## 아키텍처 요약

```
[장 마감 후 자동 실행]
pykrx + DART OpenAPI
      │
      ▼
4단계 스크리닝 파이프라인
  Stage 1: 빠른 필터 (~2,600개 → ~400-700개)
  Stage 2: 5차원 스코어링 (가치·품질·안전성·성장성·모멘텀)
  Stage 3: 가치 함정 감지 및 제거
  Stage 4: 최종 랭킹 (상위 50-100개)
      │
      ▼
SQLite 저장 → Cloudflare R2 업로드
      │
      ▼
Streamlit Cloud 대시보드 (30분마다 R2에서 갱신)
```

상세 아키텍처 → [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## 로컬 설정

### 사전 요구사항

- Python 3.11+
- [DART OpenAPI 키](https://opendart.fss.or.kr) (무료 등록)
- [Cloudflare R2](https://cloudflare.com/r2) 버킷 및 API 토큰

### 설치

```bash
git clone https://github.com/yourname/valueforge
cd valueforge
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

### 환경 변수 설정

```bash
cp .env.example .env
# .env 파일에 아래 항목 입력
```

```bash
DART_API_KEY=your_dart_api_key
R2_ACCOUNT_ID=your_cloudflare_account_id
R2_ACCESS_KEY_ID=your_r2_access_key
R2_SECRET_ACCESS_KEY=your_r2_secret_key
R2_BUCKET_NAME=valueforge-bucket
```

### 실행

```bash
# 파이프라인 실행 (소규모 테스트: 50개 종목)
MAX_TICKERS=50 python -m src.pipeline.runner

# Streamlit 대시보드 로컬 실행
streamlit run src/ui/app.py

# 테스트
pytest tests/ -v
```

---

## 배포 개요

| 컴포넌트 | 방법 | 비용 |
|---|---|---|
| 파이프라인 스케줄러 | Hetzner CX11 + cron | $3.29/월 |
| 스토리지 | Cloudflare R2 | $0 |
| 대시보드 | Streamlit Community Cloud | $0 |

상세 배포 가이드 → [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

---

## 문서 색인

| 문서 | 내용 |
|---|---|
| [docs/PRD.md](docs/PRD.md) | 제품 요구사항 정의서 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 시스템 아키텍처 및 컴포넌트 다이어그램 |
| [docs/DATABASE.md](docs/DATABASE.md) | SQLite 스키마, 인덱스, 쿼리 전략 |
| [docs/SCREENING.md](docs/SCREENING.md) | 4단계 스크리닝 알고리즘 설계 |
| [docs/STORAGE.md](docs/STORAGE.md) | Cloudflare R2 스토리지 설계 |
| [docs/STREAMLIT.md](docs/STREAMLIT.md) | Streamlit 대시보드 설계 |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | 배포 전략, Docker, VPS, CI/CD |
| [docs/TASKS.md](docs/TASKS.md) | 마일스톤별 구현 태스크 |
| [docs/COST_ANALYSIS.md](docs/COST_ANALYSIS.md) | 단계별 비용 분석 |
| [docs/FUTURE_UPGRADE.md](docs/FUTURE_UPGRADE.md) | 향후 아키텍처 진화 경로 |
| [docs/CLAUDE.md](docs/CLAUDE.md) | Claude Code 개발 워크플로우 가이드 |

---

## 주요 설계 결정

- **SQLite = 전송 레이어**: 파이프라인과 대시보드 간 단일 파일로 데이터 교환. API 서버 불필요.
- **에페머럴 분석 서버**: 파이프라인은 실행 후 종료. 상시 가동 서버 없음.
- **읽기 전용 대시보드**: Streamlit Cloud는 R2에서 읽기만 수행. 무거운 연산 일체 실행 불가.
- **R2 자격증명 분리**: 파이프라인은 읽기+쓰기 토큰, Streamlit은 읽기 전용 토큰 사용.
