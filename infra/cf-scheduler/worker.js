/**
 * Cloudflare Workers — ValueForge 파이프라인 백업 스케줄러
 *
 * 동작:
 *   1. 매 영업일 08:30 UTC (17:30 KST) 실행
 *   2. GitHub Actions가 오늘 이미 성공/진행 중이면 → 스킵
 *   3. 오늘 실행 기록이 없으면 → workflow_dispatch 트리거
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

  // KST 기준 오늘 날짜
  const kstToday = getKstDate();
  console.log(`[${kstToday}] 파이프라인 실행 여부 확인 중...`);

  try {
    const alreadyRan = await checkTodayRun(PAT, kstToday);

    if (alreadyRan) {
      console.log(`[${kstToday}] 이미 실행됨 → 스킵`);
      return;
    }

    console.log(`[${kstToday}] 오늘 실행 기록 없음 → 트리거`);
    await triggerWorkflow(PAT, kstToday);

  } catch (err) {
    console.error(`[${kstToday}] 오류: ${err.message}`);
  }
}

/**
 * 오늘(KST) 실행된 run 중 성공·진행 중인 것이 있는지 확인
 * @returns {Promise<boolean>}
 */
async function checkTodayRun(pat, kstToday) {
  const url =
    `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW_FILE}/runs?per_page=10`;

  const res = await ghFetch(url, pat);

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`GitHub API 조회 실패 (${res.status}): ${body}`);
  }

  const { workflow_runs } = await res.json();

  const todayRuns = workflow_runs.filter((run) => {
    const runKst = new Date(new Date(run.created_at).getTime() + KST_OFFSET_MS);
    return runKst.toISOString().slice(0, 10) === kstToday;
  });

  if (todayRuns.length === 0) {
    console.log(`[${kstToday}] 오늘 실행 기록 없음`);
    return false;
  }

  // 상태별 요약 로그
  for (const run of todayRuns) {
    console.log(
      `[${kstToday}] run #${run.id}: status=${run.status}, conclusion=${run.conclusion ?? "—"}, event=${run.event}`
    );
  }

  // 성공했거나 현재 진행 중이면 트리거 불필요
  const shouldSkip = todayRuns.some(
    (r) =>
      r.conclusion === "success" ||
      r.status   === "in_progress" ||
      r.status   === "queued" ||
      r.status   === "waiting"
  );

  return shouldSkip;
}

/**
 * workflow_dispatch 트리거
 */
async function triggerWorkflow(pat, kstToday) {
  const url =
    `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW_FILE}/dispatches`;

  const res = await ghFetch(url, pat, {
    method: "POST",
    body: JSON.stringify({ ref: "main" }),
  });

  // 204 No Content = 성공
  if (res.status === 204 || res.ok) {
    console.log(`[${kstToday}] ✅ 파이프라인 트리거 성공`);
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
  return new Date(Date.now() + KST_OFFSET_MS).toISOString().slice(0, 10);
}
