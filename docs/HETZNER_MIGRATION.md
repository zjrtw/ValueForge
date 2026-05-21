# GitHub Actions → Hetzner VPS 전환 가이드

> 현재 파이프라인은 **GitHub Actions**(`ubuntu-latest` 러너)로 실행됩니다.
> 이 문서는 **Hetzner CX11 VPS**로 전환하는 전 과정을 단계별로 안내합니다.

---

## 전환을 고려해야 할 시점

| 상황 | 설명 |
|---|---|
| GitHub Actions 분 한도 근접 | 무료 2,000분/월. 파이프라인 90분 × 22거래일 ≈ 1,980분으로 한도에 거의 도달 |
| 실행 시간 단축 필요 | GitHub Actions 러너 Cold start(~1분) + 의존성 설치(~5분) 오버헤드 제거 |
| 안정적인 실행 환경 필요 | GitHub Actions는 가끔 러너 부족으로 지연 발생 |
| 비용 투자 가능 | Hetzner CX11 = **$3.29/월** (연 ~$40) |

> **지금 당장 전환이 불필요하다면**: GitHub Actions를 그대로 유지하면서 이 문서를 참고용으로 보관하세요.

---

## 전환 전 체크리스트

- [ ] Hetzner Cloud 계정 생성 ([hetzner.com/cloud](https://www.hetzner.com/cloud))
- [ ] 로컬 머신에 SSH 키 쌍 존재 확인 (`~/.ssh/id_ed25519`)
- [ ] 현재 GitHub Actions 파이프라인이 정상 동작 확인
- [ ] R2에 최신 `latest.db` 존재 확인

---

## 1단계: SSH 키 준비

### 기존 키 확인

```bash
ls ~/.ssh/id_ed25519.pub
```

### 없으면 새로 생성

```bash
ssh-keygen -t ed25519 -C "valueforge-hetzner" -f ~/.ssh/id_ed25519
```

공개키 내용을 복사해 둡니다:

```bash
cat ~/.ssh/id_ed25519.pub
```

---

## 2단계: Hetzner 인스턴스 생성

### Hetzner Cloud 콘솔에서 진행

1. [console.hetzner.cloud](https://console.hetzner.cloud) 접속
2. **New Project** → 프로젝트명: `valueforge`
3. **Add Server** 클릭:

| 항목 | 선택값 |
|---|---|
| Location | Nuremberg (nbg1) 또는 Helsinki (hel1) |
| Image | **Ubuntu 22.04** |
| Type | **CX11** (2 vCPU, 2GB RAM, 20GB SSD) |
| SSH Key | 1단계에서 복사한 공개키 추가 |
| Name | `valueforge-pipeline` |

4. **Create & Buy** 클릭 → 약 30초 후 서버 IP 할당

### IP 주소 확인 및 접속 테스트

```bash
# <SERVER_IP>를 실제 IP로 교체
ssh root@<SERVER_IP>
```

> 첫 접속 시 `Are you sure you want to continue connecting?` → `yes` 입력

---

## 3단계: VPS 자동 설정 스크립트 실행

아래 명령을 **VPS에서** 루트 권한으로 실행합니다.

```bash
# 저장소 클론 (setup.sh 실행을 위해)
apt-get install -y git
git clone https://github.com/zjrtw/ValueForge.git /tmp/valueforge-setup
cd /tmp/valueforge-setup

# 설정 스크립트 실행 (약 5~10분 소요)
sudo bash deployment/setup.sh
```

스크립트가 자동으로 수행하는 작업:
- Docker 설치
- `valueforge` 전용 사용자 생성
- 저장소를 `/home/valueforge/app`에 클론
- `/home/valueforge/.env` 생성 (빈 템플릿)
- Docker 파이프라인 이미지 빌드
- cron 등록 (매 거래일 08:00 UTC = 17:00 KST)
- 로그 로테이션 설정

---

## 4단계: API 키 입력

```bash
sudo -u valueforge nano /home/valueforge/.env
```

아래 값을 실제 키로 채웁니다:

```bash
DART_API_KEY=실제_DART_API_키
R2_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=실제_R2_액세스_키
R2_SECRET_ACCESS_KEY=실제_R2_시크릿_키
R2_BUCKET_NAME=valueforge
MAX_TICKERS=0
LOG_LEVEL=INFO
DB_PATH=/tmp/valueforge.db
```

저장: `Ctrl+O` → `Enter` → `Ctrl+X`

→ 환경변수 전체 설명: [ENV_VARS.md](ENV_VARS.md)

---

## 5단계: 파이프라인 수동 테스트

실제 전환 전에 VPS에서 파이프라인이 정상 동작하는지 확인합니다.

```bash
# 소규모 테스트 (50개 종목, R2 업로드 없음) — 약 5분
sudo -u valueforge docker compose \
  -f /home/valueforge/app/docker-compose.yml \
  run --rm pipeline-test

# 성공 시 로그 확인
tail -50 /home/valueforge/app/logs/cron.log
```

**예상 출력:**
```json
{"event": "pipeline_start", "run_date": "2025-01-20", ...}
{"event": "stage1_done", "pass_count": 42, ...}
{"event": "stage4_done", "final_count": 42, ...}
{"event": "pipeline_success", ...}
```

### 전체 파이프라인 + R2 업로드 테스트 (선택)

```bash
sudo -u valueforge docker compose \
  -f /home/valueforge/app/docker-compose.yml \
  run --rm pipeline
```

R2 버킷에 `latest.db`, `latest_metadata.json` 업로드 여부를 Cloudflare 대시보드에서 확인합니다.

---

## 6단계: cron 등록 확인

```bash
crontab -u valueforge -l
```

**예상 출력:**
```
0 8 * * 1-5 cd /home/valueforge/app && docker compose -f /home/valueforge/app/docker-compose.yml run --rm pipeline >> /home/valueforge/app/logs/cron.log 2>&1
```

cron이 없으면 수동 등록:

```bash
sudo bash /home/valueforge/app/deployment/cron_install.sh valueforge /home/valueforge/app
```

---

## 7단계: GitHub Actions 비활성화

VPS가 정상 동작을 확인한 후 GitHub Actions 스케줄을 비활성화합니다.

### 방법 A — 워크플로우 파일에서 schedule 주석 처리 (권장)

```yaml
# .github/workflows/daily_pipeline.yml
on:
  # schedule:                    # ← VPS로 전환하여 비활성화
  #   - cron: "0 8 * * 1-5"
  workflow_dispatch:             # ← 수동 트리거는 유지 (비상시 사용)
    inputs:
      date_override:
        required: false
```

변경 후 커밋·푸시합니다.

### 방법 B — GitHub 콘솔에서 비활성화

저장소 → **Actions** → `일일 스크리닝 파이프라인` → ⋯ → **Disable workflow**

> **`workflow_dispatch`는 유지하세요.** VPS 장애 시 수동으로 GitHub Actions를 긴급 실행할 수 있습니다.

---

## 운영 관리

### 로그 확인

```bash
# 실시간 로그
tail -f /home/valueforge/app/logs/cron.log

# 최근 100줄
tail -100 /home/valueforge/app/logs/cron.log

# 특정 날짜 검색
grep "2025-01-20" /home/valueforge/app/logs/cron.log
```

### 코드 업데이트 배포

`main` 브랜치 push 후 VPS에서:

```bash
sudo -u valueforge git -C /home/valueforge/app pull origin main
sudo -u valueforge docker compose \
  -f /home/valueforge/app/docker-compose.yml \
  build pipeline
```

### Docker 이미지 정리

```bash
# 사용하지 않는 이미지 제거
docker image prune -f
```

### 수동 파이프라인 즉시 실행

```bash
sudo -u valueforge docker compose \
  -f /home/valueforge/app/docker-compose.yml \
  run --rm pipeline --date 2025-01-20
```

---

## 장애 대응

### VPS 파이프라인 실패 시

1. 로그 확인: `tail -100 /home/valueforge/app/logs/cron.log`
2. 컨테이너 상태 확인: `docker ps -a`
3. 수동 재실행: 위 명령 참조
4. **긴급 대안**: GitHub Actions `workflow_dispatch`로 수동 트리거

### VPS 접속 불가 시

1. Hetzner Console → 서버 → **Console**(웹 콘솔)로 접속
2. 또는 서버 재시작: Hetzner Console → **Power** → Restart
3. 복구 불가 시: GitHub Actions 일시 재활성화 후 VPS 재구성

---

## 비용 비교

| 항목 | GitHub Actions | Hetzner VPS |
|---|---|---|
| 월 비용 | $0 (무료 한도 내) | $3.29 |
| 연 비용 | $0 | ~$40 |
| 분 한도 | 2,000분/월 | 무제한 |
| Cold start | 매 실행마다 ~6분 | 없음 |
| 안정성 | 가끔 러너 지연 | 자체 제어 |
| 관리 부담 | 없음 | OS 업데이트 필요 |

> **결론**: 월 $3.29로 실행 시간을 단축하고 한도 걱정을 없앨 수 있습니다. GitHub Actions 한도에 근접하면 전환을 권장합니다.

---

## 롤백 방법 (VPS → GitHub Actions 재활성화)

1. `.github/workflows/daily_pipeline.yml`에서 `schedule` 주석 해제
2. 커밋·푸시
3. VPS cron 중단 (선택):
   ```bash
   crontab -u valueforge -r   # 모든 cron 삭제
   ```

---

## 관련 파일

| 파일 | 역할 |
|---|---|
| `deployment/setup.sh` | VPS 원클릭 초기화 스크립트 |
| `deployment/cron_install.sh` | cron 등록 스크립트 |
| `deployment/logrotate.conf` | 로그 로테이션 설정 |
| `.github/workflows/daily_pipeline.yml` | GitHub Actions 워크플로우 |
| `docker-compose.yml` | 로컬·VPS 실행용 Compose |
| `docs/ENV_VARS.md` | 환경 변수 전체 레퍼런스 |
