/**
 * Cloudflare Workers — ValueForge 파이프라인 스케줄러 (전담)
 *
 * 동작:
 *   1. 매 영업일 23:00 UTC (08:00 KST+1, 즉 다음 날 오전 8시) 실행
 *   2. GitHub Actions의 workflow_dispatch API를 직접 호출하여 파이프라인 트리거
 *   3. KRX 익일 데이터 공개 후 파이프라인 실행
 */

const REPO          = "zjrtw/ValueForge";
const WORKFLOW_FILE = "daily_pipeline.yml";
const KST_OFFSET_MS = 9 * 60 * 60 * 1000; // UTC+9

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(runScheduler(env));
  },
};

async function runScheduler(env) {
  const PAT = env.GITHUB_PAT;
  if (!PAT) {
    console.error("GITHUB_PAT secret이 설정되지 않았습니다.");
    return;
  }

  const kstToday = getKstDate();
  const runDate = getKstDateOffset(-1);
  console.log(`[${kstToday}] Cloudflare 스케줄러: ${runDate} 기준 파이프라인 실행 명령 전송 중...`);

  try {
    await triggerWorkflow(PAT, kstToday, runDate);
  } catch (err) {
    console.error(`[${kstToday}] 오류: ${err.message}`);
  }
}

/**
 * workflow_dispatch 트리거
 */
async function triggerWorkflow(pat, kstToday, runDate) {
  const url =
    `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW_FILE}/dispatches`;

  const res = await ghFetch(url, pat, {
    method: "POST",
    body: JSON.stringify({
      ref: "main",
      inputs: {
        date_override: runDate,
      },
    }),
  });

  // 204 No Content = 성공
  if (res.status === 204 || res.ok) {
    console.log(`[${kstToday}] ✅ GitHub Actions 파이프라인 트리거 성공 (date_override=${runDate})`);
  } else {
    const body = await res.text();
    throw new Error(`트리거 실패 (${res.status}): ${body}`);
  }
}

/**
 * GitHub API 공통 fetch 래퍼
 */
function ghFetch(url, pat, options = {}) {
  return fetch(url, {
    method: options.method ?? "GET",
    headers: {
      Authorization:          `Bearer ${pat}`,
      Accept:                 "application/vnd.github+json",
      "Content-Type":         "application/json",
      "User-Agent":           "cf-worker-valueforge",
      "X-GitHub-Api-Version": "2022-11-28",
    },
    body: options.body,
  });
}

/**
 * KST(UTC+9) 기준 오늘 날짜 반환 (YYYY-MM-DD)
 */
function getKstDate() {
  return getKstDateOffset(0);
}

/**
 * KST(UTC+9) 기준 날짜에 dayOffset을 더해 반환 (YYYY-MM-DD)
 */
function getKstDateOffset(dayOffset) {
  const dayMs = 24 * 60 * 60 * 1000;
  return new Date(Date.now() + KST_OFFSET_MS + dayOffset * dayMs).toISOString().slice(0, 10);
}
