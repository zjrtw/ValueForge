# 환경 변수 레퍼런스

ValueForge에서 사용하는 모든 환경 변수를 정의합니다.

---

## 빠른 설정

```bash
cp .env.example .env
# .env 파일에 실제 값 입력
```

---

## 필수 변수

### DART_API_KEY

| 항목 | 내용 |
|---|---|
| 필수 여부 | **필수** (파이프라인) |
| 기본값 | 없음 |
| 발급 | [opendart.fss.or.kr](https://opendart.fss.or.kr) → 인증키 신청 (무료) |
| 한도 | 일 10,000건 |

```bash
DART_API_KEY=a1b2c3d4e5f6...
```

---

### KRX_AUTH_KEY

| 항목 | 내용 |
|---|---|
| 필수 여부 | **필수** (파이프라인) |
| 기본값 | 없음 |
| 발급 | [KRX Open API](https://openapi.krx.co.kr) → API 신청 (무료) |
| 용도 | KOSPI/KOSDAQ 종목 정보, 일별매매 데이터 조회 |

```bash
KRX_AUTH_KEY=your_krx_auth_key_here
```

---

### R2_ENDPOINT_URL

| 항목 | 내용 |
|---|---|
| 필수 여부 | **필수** (파이프라인 + 대시보드) |
| 형식 | `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` |
| 위치 | Cloudflare 대시보드 → R2 → 버킷 → 설정 → S3 API |

```bash
R2_ENDPOINT_URL=https://abc123def456.r2.cloudflarestorage.com
```

---

### R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY

| 항목 | 내용 |
|---|---|
| 필수 여부 | **필수** (파이프라인 + 대시보드) |
| 발급 | Cloudflare 대시보드 → R2 → 개요 → R2 API 토큰 관리 |

> **보안 원칙**: 파이프라인 서버에는 읽기+쓰기 토큰, Streamlit Cloud·대시보드에는 읽기 전용 토큰을 별도로 사용하세요.

```bash
R2_ACCESS_KEY_ID=your_access_key_id
R2_SECRET_ACCESS_KEY=your_secret_access_key
```

---

### R2_BUCKET_NAME

| 항목 | 내용 |
|---|---|
| 필수 여부 | 선택 |
| 기본값 | `valueforge` |

```bash
R2_BUCKET_NAME=valueforge
```

---

## 선택 변수

### MAX_TICKERS

| 항목 | 내용 |
|---|---|
| 필수 여부 | 선택 |
| 기본값 | `0` (제한 없음) |
| 용도 | 파이프라인 수집 종목 수 제한 |

| 값 | 동작 |
|---|---|
| `0` | 전체 종목 (~2,600개). 프로덕션 운영 |
| `50` | 50개 종목만 수집. 빠른 개발·테스트 |
| `200` | 200개 종목. 통합 검증용 |

```bash
MAX_TICKERS=0        # 프로덕션
MAX_TICKERS=50       # 테스트
```

---

### MARKETS

| 항목 | 내용 |
|---|---|
| 필수 여부 | 선택 |
| 기본값 | `KOSPI,KOSDAQ` |
| 용도 | 파이프라인 실행 시장 범위 선택 |

| 값 | 동작 |
|---|---|
| `KOSPI` | 코스피만 실행 |
| `KOSDAQ` | 코스닥만 실행 |
| `KOSPI,KOSDAQ` | 코스피와 코스닥 모두 실행 |
| `ALL` | 코스피와 코스닥 모두 실행 |

```bash
MARKETS=KOSPI          # 코스피만
MARKETS=KOSDAQ         # 코스닥만
MARKETS=KOSPI,KOSDAQ   # 둘 다
```

---

### LOG_LEVEL

| 항목 | 내용 |
|---|---|
| 필수 여부 | 선택 |
| 기본값 | `INFO` |
| 유효값 | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` |

```bash
LOG_LEVEL=INFO    # 운영
LOG_LEVEL=DEBUG   # 개발 (상세 로그, 느림)
```

---

### DB_PATH

| 항목 | 내용 |
|---|---|
| 필수 여부 | 선택 |
| 기본값 | `/tmp/valueforge.db` |
| 용도 | 파이프라인 실행 중 SQLite 임시 경로. R2 업로드 후 자동 삭제 |

```bash
DB_PATH=/tmp/valueforge.db
```

---

## 환경별 설정 요약

| 변수 | 파이프라인 서버 | Streamlit Cloud | 로컬 개발 |
|---|---|---|---|
| `DART_API_KEY` | ✅ 필수 | ❌ 불필요 | ✅ 필수 |
| `KRX_AUTH_KEY` | ✅ 필수 | ❌ 불필요 | ✅ 필수 |
| `R2_ENDPOINT_URL` | ✅ 필수 | ✅ 필수 | ✅ 필수 |
| `R2_ACCESS_KEY_ID` | ✅ 읽기+쓰기 | ✅ 읽기 전용 | ✅ 읽기+쓰기 |
| `R2_SECRET_ACCESS_KEY` | ✅ 필수 | ✅ 필수 | ✅ 필수 |
| `R2_BUCKET_NAME` | 선택 | 선택 | 선택 |
| `MAX_TICKERS` | 선택 (`0`) | ❌ 불필요 | 권장 (`50`) |
| `LOG_LEVEL` | 선택 (`INFO`) | ❌ 불필요 | 선택 (`DEBUG`) |
| `DB_PATH` | 선택 | ❌ 불필요 | 선택 |

---

## 시크릿 저장 위치

| 환경 | 저장 방법 |
|---|---|
| 로컬 개발 | `.env` 파일 (`.gitignore` 등록됨) |
| GitHub Actions | 저장소 → Settings → Secrets and variables → Actions |
| Streamlit Cloud | 앱 설정 → Secrets 탭 (TOML 형식) |
| Hetzner VPS | `/home/valueforge/.env` (`chmod 600`) |
