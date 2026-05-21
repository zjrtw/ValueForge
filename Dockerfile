# ── Stage 1: 의존성 빌드 ────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# 빌드 도구 설치 (일부 패키지 컴파일 필요)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# 가상환경 생성 후 의존성 설치 (레이어 캐시 최대화)
COPY requirements-pipeline.txt .
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --upgrade pip --quiet \
 && pip install --no-cache-dir -r requirements-pipeline.txt


# ── Stage 2: 런타임 이미지 ─────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# 보안: 비루트 사용자
RUN groupadd --gid 1000 appgroup \
 && useradd  --uid 1000 --gid appgroup --no-create-home --shell /bin/bash appuser

# 빌드 스테이지에서 가상환경만 복사
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# 소스코드 복사 (최소 범위)
COPY src/     ./src/
COPY config/  ./config/

# 로그 디렉터리 생성 및 권한 설정
RUN mkdir -p /app/logs && chown -R appuser:appgroup /app

USER appuser

# PATH에 가상환경 등록
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# 컨테이너 기본 실행: 파이프라인 러너
ENTRYPOINT ["python", "-m", "src.pipeline.runner"]
CMD []
