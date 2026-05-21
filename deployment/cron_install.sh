#!/usr/bin/env bash
# ValueForge cron 작업 등록 스크립트
#
# 사용법:
#   bash cron_install.sh [사용자명] [앱 디렉터리]
#
# 기본값:
#   사용자: valueforge
#   앱 디렉터리: /home/valueforge/app

set -euo pipefail

APP_USER="${1:-valueforge}"
APP_DIR="${2:-/home/${APP_USER}/app}"
COMPOSE_FILE="${APP_DIR}/docker-compose.yml"
LOG_DIR="${APP_DIR}/logs"
CRON_LOG="${LOG_DIR}/cron.log"

# 로그 디렉터리 생성
mkdir -p "${LOG_DIR}"
chown "${APP_USER}:${APP_USER}" "${LOG_DIR}" 2>/dev/null || true

# cron 표현식: 08:00 UTC = 17:00 KST, 월~금
# runner.py 내부에서 is_trading_day() 체크를 수행하므로
# 공휴일에는 파이프라인이 자동으로 건너뜁니다.
CRON_EXPR="0 8 * * 1-5"
CRON_CMD="cd ${APP_DIR} && docker compose -f ${COMPOSE_FILE} run --rm pipeline >> ${CRON_LOG} 2>&1"
CRON_LINE="${CRON_EXPR} ${CRON_CMD}"

# 기존 valueforge cron 항목 제거 후 재등록 (멱등)
TMPFILE=$(mktemp)
crontab -u "${APP_USER}" -l 2>/dev/null | grep -v "docker compose.*pipeline" > "${TMPFILE}" || true
echo "${CRON_LINE}" >> "${TMPFILE}"
crontab -u "${APP_USER}" "${TMPFILE}"
rm -f "${TMPFILE}"

echo "cron 등록 완료:"
crontab -u "${APP_USER}" -l | grep pipeline
