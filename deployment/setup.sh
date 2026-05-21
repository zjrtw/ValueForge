#!/usr/bin/env bash
# ValueForge VPS 초기 설정 스크립트 (Hetzner CX11 / Ubuntu 22.04)
#
# 사용법:
#   sudo bash setup.sh [--repo-url <url>] [--branch <branch>]
#
# 이 스크립트는 멱등(idempotent)합니다. 재실행해도 안전합니다.
# 루트 권한으로 실행하세요.

set -euo pipefail

# ── 설정 변수 ────────────────────────────────────────────────────────────────
REPO_URL="${REPO_URL:-https://github.com/zjrtw/ValueForge.git}"
BRANCH="${BRANCH:-main}"
APP_USER="valueforge"
APP_HOME="/home/${APP_USER}"
APP_DIR="${APP_HOME}/app"
LOG_FILE="/var/log/valueforge_setup.log"

# ── 로깅 헬퍼 ────────────────────────────────────────────────────────────────
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }
log_ok()   { log "  ✓ $*"; }
log_skip() { log "  - $* (이미 완료됨, 건너뜀)"; }

# ── 루트 권한 확인 ───────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    echo "오류: 루트 권한으로 실행하세요 (sudo bash setup.sh)" >&2
    exit 1
fi

log "=== ValueForge VPS 설정 시작 ==="

# ── 1. 시스템 패키지 업데이트 ────────────────────────────────────────────────
log "1. 시스템 패키지 업데이트"
apt-get update -qq
apt-get install -y --no-install-recommends \
    curl \
    git \
    ca-certificates \
    gnupg \
    lsb-release \
    logrotate
log_ok "시스템 패키지 설치 완료"

# ── 2. Docker 설치 ──────────────────────────────────────────────────────────
log "2. Docker 설치 확인"
if command -v docker &>/dev/null; then
    log_skip "Docker $(docker --version)"
else
    log "Docker 설치 중..."
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/ubuntu \
        $(lsb_release -cs) stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -qq
    apt-get install -y --no-install-recommends \
        docker-ce docker-ce-cli containerd.io docker-compose-plugin
    systemctl enable docker
    systemctl start docker
    log_ok "Docker 설치 완료"
fi

# ── 3. 전용 사용자 생성 ──────────────────────────────────────────────────────
log "3. 전용 사용자 '${APP_USER}' 생성"
if id "${APP_USER}" &>/dev/null; then
    log_skip "사용자 ${APP_USER}"
else
    useradd -m -s /bin/bash -G docker "${APP_USER}"
    log_ok "사용자 ${APP_USER} 생성 완료 (docker 그룹 포함)"
fi

# ── 4. 저장소 클론 ───────────────────────────────────────────────────────────
log "4. 저장소 클론: ${REPO_URL} (${BRANCH})"
if [[ -d "${APP_DIR}/.git" ]]; then
    log "  저장소 업데이트 중..."
    sudo -u "${APP_USER}" git -C "${APP_DIR}" fetch origin
    sudo -u "${APP_USER}" git -C "${APP_DIR}" checkout "${BRANCH}"
    sudo -u "${APP_USER}" git -C "${APP_DIR}" pull origin "${BRANCH}"
    log_ok "저장소 업데이트 완료"
else
    sudo -u "${APP_USER}" git clone --branch "${BRANCH}" "${REPO_URL}" "${APP_DIR}"
    log_ok "저장소 클론 완료: ${APP_DIR}"
fi

# ── 5. 환경 변수 파일 생성 ───────────────────────────────────────────────────
log "5. 환경 변수 파일 설정"
ENV_FILE="${APP_HOME}/.env"
if [[ -f "${ENV_FILE}" ]]; then
    log_skip ".env 파일 (기존 파일 유지)"
else
    cp "${APP_DIR}/.env.example" "${ENV_FILE}"
    chmod 600 "${ENV_FILE}"
    chown "${APP_USER}:${APP_USER}" "${ENV_FILE}"
    log_ok ".env 파일 생성 완료 (${ENV_FILE})"
    log "  !! .env 파일에 실제 값을 입력하세요:"
    log "     sudo -u ${APP_USER} nano ${ENV_FILE}"
fi

# ── 6. .env 심볼릭 링크 ──────────────────────────────────────────────────────
log "6. .env 심볼릭 링크 설정"
APP_ENV_LINK="${APP_DIR}/.env"
if [[ -L "${APP_ENV_LINK}" ]] || [[ -f "${APP_ENV_LINK}" ]]; then
    log_skip ".env 링크 (이미 존재)"
else
    sudo -u "${APP_USER}" ln -sf "${ENV_FILE}" "${APP_ENV_LINK}"
    log_ok ".env 심볼릭 링크 생성: ${APP_ENV_LINK} → ${ENV_FILE}"
fi

# ── 7. Docker 이미지 빌드 ────────────────────────────────────────────────────
log "7. Docker 이미지 빌드"
sudo -u "${APP_USER}" docker compose -f "${APP_DIR}/docker-compose.yml" build pipeline
log_ok "파이프라인 이미지 빌드 완료"

# ── 8. cron 등록 ─────────────────────────────────────────────────────────────
log "8. cron 등록"
bash "${APP_DIR}/deployment/cron_install.sh" "${APP_USER}" "${APP_DIR}"

# ── 9. 로그 로테이션 설정 ────────────────────────────────────────────────────
log "9. 로그 로테이션 설정"
cp "${APP_DIR}/deployment/logrotate.conf" /etc/logrotate.d/valueforge
log_ok "로그 로테이션 설정 완료"

log ""
log "=== 설정 완료 ==="
log ""
log "다음 단계:"
log "  1. .env 파일에 API 키 입력:"
log "       sudo -u ${APP_USER} nano ${ENV_FILE}"
log "  2. 파이프라인 수동 테스트 실행:"
log "       sudo -u ${APP_USER} docker compose -f ${APP_DIR}/docker-compose.yml run --rm pipeline-test"
log "  3. cron 등록 확인:"
log "       crontab -u ${APP_USER} -l"
