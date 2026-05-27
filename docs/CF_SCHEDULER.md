# Cloudflare Workers 백업 스케줄러

GitHub Actions cron이 지연·스킵될 때 자동으로 파이프라인을 트리거하는 백업 스케줄러.

---

## 동작 원리

```
08:00 UTC (17:00 KST)  →  GitHub Actions 자체 cron 시도
08:30 UTC (17:30 KST)  →  Cloudflare Workers 실행
                            ├─ 오늘 성공/진행 중인 run 있음  →  스킵 ✅
                            └─ 오늘 run 없음                →  workflow_dispatch 트리거 🔁
```

**소스**: [infra/cf-scheduler/worker.js](../infra/cf-scheduler/worker.js)

---

## 초기 설정 (최초 1회)

### 1단계 — GitHub Personal Access Token 발급

1. GitHub → **Settings** → **Developer settings** → **Personal access tokens** → **Fine-grained tokens** → **Generate new token**
2. 설정:
   - **Token name**: `valueforge-cf-scheduler`
   - **Expiration**: 1 year (또는 No expiration)
   - **Repository access**: `zjrtw/ValueForge` (특정 저장소만)
   - **Permissions** → Repository permissions → **Actions**: `Read and write`
3. **Generate token** → 토큰 복사 (재확인 불가, 지금 복사 필수)

---

### 2단계 — Cloudflare 계정 및 Workers 설정

1. [dash.cloudflare.com](https://dash.cloudflare.com) 회원가입 (무료)
2. 로그인 후 대시보드 확인

---

### 3단계 — Wrangler CLI 설치 및 로그인

```bash
cd infra/cf-scheduler

# 의존성 설치
npm install

# Cloudflare 계정 로그인 (브라우저 인증)
npx wrangler login
```

---

### 4단계 — GitHub PAT를 Workers Secret으로 등록

```bash
# 토큰 입력 프롬프트가 나오면 1단계에서 복사한 토큰 붙여넣기
npx wrangler secret put GITHUB_PAT
```

---

### 5단계 — 배포

```bash
npx wrangler deploy
```

배포 완료 후 출력 예시:
```
✅ Successfully deployed valueforge-scheduler
   Triggers:
     - cron: 30 8 * * 1-5
```

---

## 운영

### 실시간 로그 확인

```bash
cd infra/cf-scheduler
npx wrangler tail
```

정상 동작 로그:
```
[2026-05-27] 파이프라인 실행 여부 확인 중...
[2026-05-27] run #26399276235: status=completed, conclusion=success, event=schedule
[2026-05-27] 이미 실행됨 → 스킵
```

백업 트리거 발동 로그:
```
[2026-05-26] 파이프라인 실행 여부 확인 중...
[2026-05-26] 오늘 실행 기록 없음
[2026-05-26] 오늘 run 없음 → 트리거
[2026-05-26] ✅ 파이프라인 트리거 성공
```

### Cloudflare 대시보드에서 확인

Workers & Pages → `valueforge-scheduler` → **Metrics** 탭에서 cron 실행 이력 확인 가능.

---

## 비용

| 항목 | 무료 플랜 한도 | 실제 사용 |
|------|-------------|---------|
| 요청 수 | 10만/일 | 1회/일 |
| CPU 시간 | 10ms/요청 | ~5ms |
| Cron 트리거 | 제한 없음 | 1회/영업일 |

→ **무료 플랜으로 충분**

---

## PAT 갱신 (만료 시)

```bash
# 새 토큰 발급 후
cd infra/cf-scheduler
npx wrangler secret put GITHUB_PAT
# 새 토큰 입력
```

---

## 관련 문서

- 워크플로우 파일: [.github/workflows/daily_pipeline.yml](../.github/workflows/daily_pipeline.yml)
- 배포 전략 전체: [DEPLOYMENT.md](DEPLOYMENT.md)
