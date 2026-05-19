# 배포 전략

> **ValueForge** | 스케줄러, Docker, VPS, Streamlit Cloud, CI/CD

## 목차

1. [스케줄러 설계](#1-스케줄러-설계)
2. [로컬 개발 워크플로우](#2-로컬-개발-워크플로우)
3. [Docker 설정](#3-docker-설정)
4. [Hetzner VPS 설정 (권장)](#4-hetzner-vps-설정-권장)
5. [GitHub Actions 설정 (무료 대안)](#5-github-actions-설정-무료-대안)
6. [Streamlit Cloud 배포](#6-streamlit-cloud-배포)
7. [환경 변수 레퍼런스](#7-환경-변수-레퍼런스)
8. [CI/CD](#8-cicd)
9. [추천 Python 라이브러리](#9-추천-python-라이브러리)

---

## 1. 스케줄러 설계

### 실행 타이밍

```
한국 장 마감: 15:30 KST
데이터 전파 완료: ~16:30 KST
파이프라인 실행: 17:00 KST (08:00 UTC)
```

### 한국 장 휴장일 처리

```python
# src/utils/market_calendar.py

import holidays
from datetime import date
import sys

KR_HOLIDAYS = holidays.KoreaStockExchange(years=range(2024, 2030))

def is_trading_day(d: date | None = None) -> bool:
    d = d or date.today()
    return d.weekday() < 5 and d not in KR_HOLIDAYS

def check_today_and_exit():
    """GitHub Actions / cron에서 휴장일 자동 skip"""
    if not is_trading_day():
        print(f"오늘({date.today()})은 한국 거래일이 아닙니다. 파이프라인 건너뜀.")
        sys.exit(0)  # 정상 종료 (실패 아님)
```

### 재시도 전략

```python
# src/utils/retry.py

from functools import wraps
import time, logging

log = logging.getLogger(__name__)

def with_retry(max_attempts: int = 3, delay: float = 2.0, backoff: float = 2.0,
               exceptions: tuple = (Exception,)):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt, current_delay = 0, delay
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt == max_attempts:
                        raise
                    log.warning(
                        f"{func.__name__} 실패 ({attempt}/{max_attempts}): {e}. "
                        f"{current_delay:.1f}초 후 재시도..."
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff
        return wrapper
    return decorator
```

---

## 2. 로컬 개발 워크플로우

```bash
# 1. 저장소 클론 및 환경 설정
git clone https://github.com/yourname/valueforge
cd valueforge
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# 2. 환경 변수 설정
cp .env.example .env
# .env 파일에 다음 항목 입력:
# DART_API_KEY, R2_ACCOUNT_ID, R2_ACCESS_KEY_ID,
# R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME

# 3. 파이프라인 로컬 실행 (테스트용 소규모)
MAX_TICKERS=50 python -m src.pipeline.runner --date 2025-01-15

# 4. Streamlit 로컬 실행
streamlit run src/ui/app.py

# 5. 테스트 실행
pytest tests/ -v
pytest tests/test_screening/ -v   # 특정 모듈
pytest -k "test_stage1"           # 특정 테스트

# 6. 타입 체크 및 린팅
mypy src/ --ignore-missing-imports
ruff check src/
ruff format src/
```

---

## 3. Docker 설정

```dockerfile
# deployment/Dockerfile

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY config/ ./config/

CMD ["python", "-m", "src.pipeline.runner"]
```

```yaml
# deployment/docker-compose.yml

services:
  pipeline:
    build:
      context: ..
      dockerfile: deployment/Dockerfile
    environment:
      - DART_API_KEY=${DART_API_KEY}
      - R2_ACCOUNT_ID=${R2_ACCOUNT_ID}
      - R2_ACCESS_KEY_ID=${R2_ACCESS_KEY_ID}
      - R2_SECRET_ACCESS_KEY=${R2_SECRET_ACCESS_KEY}
      - R2_BUCKET_NAME=${R2_BUCKET_NAME}
    volumes:
      - ./logs:/app/logs
```

```bash
# Docker 로컬 실행
docker-compose -f deployment/docker-compose.yml up pipeline
```

---

## 4. Hetzner VPS 설정 (권장)

**왜 Hetzner인가**: GitHub Actions 무료 티어는 월 2,000분. 파이프라인 90분 × 22거래일 = 1,980분으로 한도에 매우 근접. Hetzner CX11은 $3.29/월에 제약 없는 실행 환경 제공.

```bash
# 1. Hetzner Cloud에서 CX11 인스턴스 생성
#    (Ubuntu 22.04, 2 vCPU, 2GB RAM)

# 2. SSH 접속 후 기본 설정
sudo apt update && sudo apt install -y python3.11 python3-pip python3-venv git

# 3. 전용 사용자 생성
sudo useradd -m -s /bin/bash valueforge
sudo -u valueforge bash

# 4. 저장소 클론 및 환경 설정 (valueforge 사용자로)
git clone https://github.com/yourname/valueforge /home/valueforge/app
cd /home/valueforge/app
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 5. 환경 변수 설정
cat > /home/valueforge/.env << 'EOF'
DART_API_KEY=your_dart_key
R2_ACCOUNT_ID=your_account_id
R2_ACCESS_KEY_ID=your_rw_access_key
R2_SECRET_ACCESS_KEY=your_rw_secret_key
R2_BUCKET_NAME=valueforge-bucket
EOF
chmod 600 /home/valueforge/.env

# 6. cron 설정 (한국 시간 17:00 = UTC 08:00, 월-금)
(crontab -l 2>/dev/null; echo "0 8 * * 1-5 cd /home/valueforge/app && source .venv/bin/activate && set -a && source /home/valueforge/.env && set +a && python -m src.pipeline.runner >> /home/valueforge/pipeline.log 2>&1") | crontab -

# 7. 로그 로테이션
sudo tee /etc/logrotate.d/valueforge << 'EOF'
/home/valueforge/pipeline.log {
    daily
    rotate 30
    compress
    missingok
    notifempty
}
EOF
```

---

## 5. GitHub Actions 설정 (무료 대안)

```yaml
# .github/workflows/daily_pipeline.yml

name: 일일 스크리닝 파이프라인

on:
  schedule:
    # 08:00 UTC = 17:00 KST (월-금)
    - cron: '0 8 * * 1-5'
  workflow_dispatch:
    inputs:
      date_override:
        description: '날짜 오버라이드 (YYYY-MM-DD). 비워두면 오늘 날짜.'
        required: false

jobs:
  run-pipeline:
    runs-on: ubuntu-latest
    timeout-minutes: 120

    steps:
      - name: 코드 체크아웃
        uses: actions/checkout@v4

      - name: Python 설정
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: pip

      - name: 의존성 설치
        run: pip install -r requirements.txt

      - name: 한국 거래일 확인
        run: python -m src.utils.market_calendar --check-today

      - name: 파이프라인 실행
        env:
          R2_ACCOUNT_ID:        ${{ secrets.R2_ACCOUNT_ID }}
          R2_ACCESS_KEY_ID:     ${{ secrets.R2_ACCESS_KEY_ID }}
          R2_SECRET_ACCESS_KEY: ${{ secrets.R2_SECRET_ACCESS_KEY }}
          R2_BUCKET_NAME:       ${{ secrets.R2_BUCKET_NAME }}
          DART_API_KEY:         ${{ secrets.DART_API_KEY }}
          DATE_OVERRIDE:        ${{ github.event.inputs.date_override }}
        run: python -m src.pipeline.runner

      - name: 파이프라인 로그 아티팩트 업로드
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: pipeline-log-${{ github.run_id }}
          path: logs/pipeline_*.log
          retention-days: 30
```

**GitHub Actions Secrets 설정**:
저장소 → Settings → Secrets and variables → Actions → New repository secret

---

## 6. Streamlit Cloud 배포

```bash
# 1. 코드를 GitHub 저장소에 Push
git push origin main

# 2. share.streamlit.io 접속
#    → New app
#    → 저장소 선택, branch: main, 파일: src/ui/app.py

# 3. Secrets 설정 (앱 설정 → Secrets 탭)
```

```toml
# Streamlit Cloud Secrets 형식
[r2]
account_id = "your_account_id"
access_key_id = "ro_access_key"      # 읽기 전용 토큰
secret_access_key = "ro_secret_key"
bucket_name = "valueforge-bucket"
```

**배포 후 자동화**: `main` 브랜치 push 시 Streamlit Cloud가 자동 재배포.

---

## 7. 환경 변수 레퍼런스

```bash
# 파이프라인 서버 필수
DART_API_KEY=           # opendart.fss.or.kr 무료 등록
R2_ACCOUNT_ID=          # Cloudflare 계정 ID
R2_ACCESS_KEY_ID=       # R2 API 토큰 (읽기+쓰기)
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=valueforge-bucket

# 선택사항
LOG_LEVEL=INFO          # DEBUG, INFO, WARNING, ERROR
PIPELINE_VERSION=1.0.0
MAX_TICKERS=0           # 0=무제한, 50=테스트용 소규모 실행
```

`.env.example` 파일을 저장소에 포함하되 실제 값은 절대 커밋하지 않는다.

---

## 8. CI/CD

```yaml
# .github/workflows/test.yml

name: 테스트
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.11', cache: pip}
      - run: pip install -r requirements-dev.txt
      - run: pytest tests/ -v --tb=short
      - run: mypy src/ --ignore-missing-imports
      - run: ruff check src/
```

**정책**:
- `main` 브랜치 직접 push 금지; PR을 통한 머지만 허용
- PR은 테스트 통과 필수
- Streamlit Cloud는 `main` 머지 시 자동 재배포

---

## 9. 추천 Python 라이브러리

### 데이터 수집

| 라이브러리 | 목적 | 선택 이유 |
|---|---|---|
| `pykrx` | 한국 주가 데이터 | KRX 공식 데이터 스크래퍼; KOSPI·KOSDAQ 유일한 무료 라이브러리 |
| `open-dart-reader` | DART API 재무 데이터 | 금감원 공식 공시 데이터; 손익계산서·재무상태표·현금흐름표 무료 |
| `yfinance` | 폴백 데이터 소스 | pykrx 데이터 누락 시 보완 |
| `requests-cache` | HTTP 응답 디스크 캐싱 | 개발 중 DART API 반복 호출 방지 |

### 데이터 처리

| 라이브러리 | 목적 |
|---|---|
| `pandas` | 모든 스크리닝 로직의 기반 |
| `numpy` | 백분위 랭킹, 정규화 연산 |

### 클라우드 스토리지

| 라이브러리 | 목적 |
|---|---|
| `boto3` | R2 업로드·다운로드 (S3 호환) |

### 신뢰성

| 라이브러리 | 목적 | 선택 이유 |
|---|---|---|
| `tenacity` | 재시도 로직 | 대기 전략, 정지 조건 등 표현력 있는 재시도 설정 |
| `structlog` | 구조화 로깅 | JSON 출력; 향후 로그 수집기 연동 대비 |
| `holidays` | 한국 공휴일 캘린더 | `KoreaStockExchange` 클래스로 KRX 거래 캘린더 정확히 반영 |

### 프론트엔드

| 라이브러리 | 목적 |
|---|---|
| `streamlit` | 웹 대시보드 (Python 네이티브, 무료 클라우드 호스팅) |
| `plotly` | 인터랙티브 차트 (WebGL 클라이언트 렌더링) |

### 설정

| 라이브러리 | 목적 |
|---|---|
| `python-dotenv` | 로컬 `.env` 파일 로드 |
| `pydantic-settings` | 타입 안전 설정, env var 자동 파싱 |

### 개발/테스트

| 라이브러리 | 목적 |
|---|---|
| `pytest` | 테스트 러너 |
| `pytest-mock` | pykrx·DART API 모킹 |
| `moto` | AWS/R2 S3 API 모킹 |
| `mypy` | 타입 체크 |
| `ruff` | 린터 + 포매터 (flake8 + isort + black 대체) |

**`requirements.txt`**:
```
pykrx>=1.0.47
open-dart-reader>=0.0.14
yfinance>=0.2.38
requests>=2.31.0
requests-cache>=1.2.0
pandas>=2.1.0
numpy>=1.26.0
boto3>=1.34.0
tenacity>=8.2.3
structlog>=23.3.0
holidays>=0.46
python-dotenv>=1.0.0
pydantic-settings>=2.1.0
streamlit>=1.31.0
plotly>=5.18.0
```

**`requirements-dev.txt`**:
```
-r requirements.txt
pytest>=7.4.0
pytest-mock>=3.12.0
moto[s3]>=5.0.0
mypy>=1.8.0
ruff>=0.2.0
```
