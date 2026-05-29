# ValueForge

**한국 주식 가치 스크리너** — KOSPI·KOSDAQ 전 종목 대상 일일 자동 가치투자 스크리닝 플랫폼

[![테스트 CI](https://github.com/zjrtw/ValueForge/actions/workflows/test.yml/badge.svg)](https://github.com/zjrtw/ValueForge/actions/workflows/test.yml)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 개요

ValueForge는 매일 장 마감 후 자동으로 한국 주식 시장 전체를 스캔하여 가치투자 관점에서 매력적인 종목 후보를 선별합니다.

벤저민 그레이엄·워렌 버핏 스타일의 **4단계 스크리닝 파이프라인**을 적용하고, 가치 함정을 감지·제거한 후 순위를 매겨 웹 대시보드로 제공합니다.

> **핵심 원칙**: 무료 인프라, 1인 개발자 유지보수 가능, 모든 연산은 장 마감 후 사전 수행.

---

## 아키텍처

```
[장 마감 후 자동 실행 — 17:00 KST]
         │
         ├─► KRX Open API  → 주가·시가총액 (공식 API)
         ├─► DART OpenAPI → 연간 재무제표 + EPS·BPS·DPS (3개년)
         │
         ▼
  4단계 스크리닝 파이프라인
  ┌─ Stage 1: 빠른 필터        ~2,600개 → ~400~700개
  ├─ Stage 2: 5차원 스코어링   가치·품질·안전·성장·모멘텀
  ├─ Stage 3: 가치 함정 감지   CRITICAL/HIGH 플래그 자동 실격
  └─ Stage 4: 최종 랭킹        상위 100개
         │
         ▼
  SQLite DB → Cloudflare R2 업로드
         │
         ▼
  Streamlit Cloud 대시보드 (30분 캐시, 읽기 전용)
```

→ 상세 아키텍처: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## 기술 스택

| 계층 | 기술 | 비용 |
|---|---|---|
| 데이터 수집 | KRX Open API + DART OpenAPI | 무료 |
| 데이터베이스 | SQLite | 무료 |
| 스토리지 | Cloudflare R2 | 무료 (10GB) |
| 스케줄러 | Hetzner CX11 + cron 또는 GitHub Actions | $0~$3.29/월 |
| 대시보드 | Streamlit Community Cloud | 무료 |
| 컨테이너 | Docker + Compose | — |
| 언어 | Python 3.13+ | — |

---

## 빠른 시작

### 사전 요구사항

- Python 3.13+
- [DART OpenAPI 키](https://opendart.fss.or.kr) (무료 등록)
- [Cloudflare R2](https://www.cloudflare.com/developer-platform/r2/) 버킷 및 API 토큰

### 1. 저장소 클론

```bash
git clone https://github.com/zjrtw/ValueForge.git
cd ValueForge
```

### 2. 환경 설정

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

### 3. 환경 변수 설정

```bash
cp .env.example .env
```

`.env` 파일에 아래 값을 입력합니다:

```bash
# DART API (opendart.fss.or.kr에서 무료 발급)
DART_API_KEY=your_dart_api_key

# Cloudflare R2
R2_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=your_r2_access_key_id
R2_SECRET_ACCESS_KEY=your_r2_secret_access_key
R2_BUCKET_NAME=valueforge
```

→ 전체 변수 설명: [docs/ENV_VARS.md](docs/ENV_VARS.md)

### 4. 파이프라인 실행

#### Windows (run_pipeline.bat)

```bash
# 기본 실행 (오늘 날짜)
.\run_pipeline.bat

# 특정 날짜 지정
.\run_pipeline.bat --date 2026-05-25

# 소수 종목으로 빠른 테스트 (50개 종목)
set MAX_TICKERS=50
.\run_pipeline.bat --date 2026-05-25

# R2 업로드 포함
.\run_pipeline.bat --upload --date 2026-05-25

# 테스트 후 파이프라인 실행
.\run_pipeline.bat -t --date 2026-05-25
```

#### Linux/Mac (직접 실행)

```bash
# 기본 실행 (오늘 날짜)
python -m src.pipeline.runner

# 특정 날짜 지정
python -m src.pipeline.runner --date 2026-05-25

# 소수 종목으로 빠른 테스트
MAX_TICKERS=50 python -m src.pipeline.runner --date 2026-05-25 --no-upload

# R2 업로드 포함
python -m src.pipeline.runner --date 2026-05-25
```

#### 대시보드 & 테스트

```bash
# Streamlit 대시보드 로컬 실행
streamlit run src/ui/app.py

# 테스트 / 린트
pytest tests/ -v
ruff check src/ && mypy src/ --ignore-missing-imports
```

**날짜 형식**: `YYYY-MM-DD` (예: `2026-05-25`) 또는 `today`

---

## Docker로 실행

```bash
# 이미지 빌드
docker compose build pipeline

# 소규모 테스트 (50개 종목, 업로드 없음)
docker compose run --rm pipeline-test

# 전체 파이프라인
docker compose run --rm pipeline

# Streamlit 대시보드
docker compose up dashboard
# → http://localhost:8501
```

→ 상세 설명: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

---

## 배포

### GitHub Actions (무료)

저장소 → Settings → Secrets 에서 아래 시크릿을 등록합니다:

| 시크릿 | 설명 |
|---|---|
| `DART_API_KEY` | DART OpenAPI 키 |
| `KRX_AUTH_KEY` | KRX Open API 인증키 |
| `R2_ENDPOINT_URL` | R2 엔드포인트 URL |
| `R2_ACCESS_KEY_ID` | R2 읽기+쓰기 액세스 키 |
| `R2_SECRET_ACCESS_KEY` | R2 시크릿 키 |
| `R2_BUCKET_NAME` | R2 버킷 이름 |

매 거래일 17:00 KST에 `.github/workflows/daily_pipeline.yml`이 자동 실행됩니다.

### Streamlit Cloud

1. [share.streamlit.io](https://share.streamlit.io) → New app
2. 저장소 선택 → Branch: `main` → 파일: `src/ui/app.py`
3. Secrets 탭에 R2 읽기 전용 키 입력 (`.streamlit/secrets.toml.example` 참고)

### Hetzner VPS (권장)

```bash
# CX11 인스턴스 생성 후 SSH 접속
sudo bash deployment/setup.sh
sudo -u valueforge nano /home/valueforge/.env  # API 키 입력
```

→ 상세 가이드: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

---

## 프로젝트 구조

```
ValueForge/
├── src/
│   ├── collectors/          # KRX Open API, DART 데이터 수집
│   ├── db/                  # SQLite 스키마, Repository 패턴
│   ├── pipeline/            # 파이프라인 오케스트레이터
│   ├── screening/           # Stage 1~4 스크리닝 로직
│   ├── scoring/             # 5차원 점수 산출
│   ├── storage/             # R2 업로드·다운로드
│   ├── ui/                  # Streamlit 대시보드
│   │   ├── app.py           # 앱 진입점
│   │   ├── components/      # 재사용 컴포넌트 (레이더 차트, 배너)
│   │   ├── pages/           # 랭킹·상세·About 페이지
│   │   └── data_loader.py   # R2 다운로드 + 캐시 레이어
│   └── utils/               # 설정, 로깅, 재시도, 시장 캘린더
├── config/
│   └── screening_params.yaml  # 스코어링 가중치·필터 임계값
├── tests/                   # pytest 단위·통합 테스트
├── deployment/              # VPS 설정 스크립트
├── .github/workflows/       # CI/CD (test.yml, daily_pipeline.yml)
├── Dockerfile               # 파이프라인 멀티스테이지 빌드
├── Dockerfile.dashboard     # Streamlit 대시보드 이미지
├── docker-compose.yml       # 로컬 개발용 Compose
├── .env.example             # 환경 변수 템플릿
└── .streamlit/
    ├── config.toml          # Streamlit 테마·서버 설정
    └── secrets.toml.example # Streamlit Cloud Secrets 템플릿
```

---

## 스크리닝 방법론

| 단계 | 설명 | 출력 |
|---|---|---|
| Stage 1 | 시총·유동성·PER·PBR·상장기간 기준 빠른 필터 | ~400~700개 |
| Stage 2 | 5차원 백분위 점수 산출 (가치 30%·품질 25%·안전 20%·성장 15%·모멘텀 10%) | 복합 점수 0~100 |
| Stage 3 | 가치 함정 감지 (CRITICAL 1개 또는 HIGH 2개 이상 → 자동 실격) | 플래그 부여 |
| Stage 4 | 리스크 페널티 적용 후 최종 정렬 | 상위 100개 |

→ 상세 알고리즘: [docs/SCREENING.md](docs/SCREENING.md)

---

## 문서 색인

| 문서 | 내용 |
|---|---|
| [docs/PRD.md](docs/PRD.md) | 제품 요구사항 정의서 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 시스템 아키텍처 |
| [docs/SCREENING.md](docs/SCREENING.md) | 4단계 스크리닝 알고리즘 |
| [docs/DATABASE.md](docs/DATABASE.md) | SQLite 스키마 |
| [docs/STORAGE.md](docs/STORAGE.md) | Cloudflare R2 설계 |
| [docs/STREAMLIT.md](docs/STREAMLIT.md) | 대시보드 설계 |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | 배포 전략 (Docker·VPS·CI/CD) |
| [docs/HETZNER_MIGRATION.md](docs/HETZNER_MIGRATION.md) | GitHub Actions → Hetzner VPS 전환 가이드 |
| [docs/ENV_VARS.md](docs/ENV_VARS.md) | 환경 변수 레퍼런스 |
| [docs/COST_ANALYSIS.md](docs/COST_ANALYSIS.md) | 비용 분석 |
| [docs/FUTURE_UPGRADE.md](docs/FUTURE_UPGRADE.md) | 향후 개선 계획 |
| [docs/TASKS.md](docs/TASKS.md) | 마일스톤 구현 태스크 |

---

## 주요 설계 결정

- **SQLite = 전송 레이어**: 파이프라인·대시보드 간 단일 파일로 데이터 교환. API 서버 불필요.
- **에페머럴 분석 서버**: 파이프라인 실행 후 즉시 종료. 상시 가동 서버 없음.
- **읽기 전용 대시보드**: Streamlit Cloud는 R2에서 읽기만 수행. 무거운 연산 일체 없음.
- **R2 자격증명 분리**: 파이프라인은 읽기+쓰기 토큰, Streamlit은 읽기 전용 토큰 사용.
- **상대 백분위 점수**: 절대 기준이 아닌 유니버스 내 상대 비교로 시장 환경 변화에 강건.

---

## 라이선스

MIT License — [LICENSE](LICENSE) 참조
