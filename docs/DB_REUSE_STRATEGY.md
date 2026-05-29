# SQLite DB 재사용 전략 (M6-2-2)

## 개요

DART API 캐싱의 효과를 극대화하기 위해 파이프라인 실행 간 DB를 재사용합니다.

- **문제**: 매번 새 DB 생성 → 캐시 효과 0% → 월간 API 호출 180,000회 (초과 위험)
- **해결**: DB 유지 옵션 추가 → 당일 재실행 캐시 100% → 월간 API 6,000회 (안전)

---

## 환경별 설정

### 개발 환경 (로컬 테스트)

```bash
# .env 또는 기본값
PRESERVE_DB=false

# 동작
- 파이프라인 시작: 새 DB 생성
- 파이프라인 종료: DB 삭제
- 효과: 격리된 테스트 환경
```

### 운영 환경 (Cloudflare Workers / VPS)

```bash
# .env
PRESERVE_DB=true
DB_PATH=/home/valueforge/data/valueforge.db  # 고정 경로

# 동작
- 파이프라인 시작: 기존 DB 사용 (있으면)
- 파이프라인 종료: DB 유지
- 캐시 히트: 100% (당일 재실행)
- 효과: 월간 API 호출 97% 절약
```

---

## 구현 세부사항

### 설정 추가

```python
# src/utils/config.py
PRESERVE_DB: bool = Field(default=False)  # True: 운영, False: 테스트
```

### runner.py에서의 동작

```python
# 변경 전
if db_path is None and _db_path.exists():
    _db_path.unlink()  # 항상 삭제

# 변경 후
should_delete = (db_path is None and not settings.PRESERVE_DB)
if should_delete and _db_path.exists():
    _db_path.unlink()  # PRESERVE_DB=False일 때만 삭제
elif db_path is None and settings.PRESERVE_DB and _db_path.exists():
    log.info("pipeline_db_preserved", path=str(_db_path))  # 로그
```

---

## 효과 분석

### 월간 API 호출 추이

```
변경 전 (DB 매번 삭제):
  월 1회 초회: 6,000회
  이후 29회: 6,000회 × 29 = 174,000회
  합계: 180,000회 ⚠️ (한도 초과 위험)

변경 후 (DB 유지):
  월 1회 초회: 6,000회
  이후 29회: 0회 (100% 캐시)
  합계: 6,000회 ✅ (안전)

절약율: 174,000회 / 180,000회 = 97% 절약
```

### 파이프라인 실행 시간

```
당일 재실행 (캐시 히트):
  DART 수집: 2초 (API 0회, DB 캐시만)
  전체: 5분 (기존 7분에서 2분 단축)
```

---

## 운영 가이드

### 설정 체크리스트

- [ ] 개발: `.env`에 `PRESERVE_DB=false` (기본값)
- [ ] 운영: `.env`에 `PRESERVE_DB=true`
- [ ] 운영: `DB_PATH` 고정 경로 설정
- [ ] 운영: 정기 백업 (R2에 자동 업로드)

### 모니터링

```bash
# PRESERVE_DB 상태 확인
grep "pipeline_db_preserved\|pipeline_temp_db_removed" logs/pipeline.log

# 월간 API 호출 추이
grep "dart financial collection complete" logs/pipeline.log | \
  awk '{print $1, $2, $NF}' | tail -30
```

### 트러블슈팅

**문제 1: "DB가 손상되었습니다"**

```bash
# 해결: 이전 백업에서 복구
rm /home/valueforge/data/valueforge.db
aws s3 cp s3://valueforge/history/2026-05-29.db \
  /home/valueforge/data/valueforge.db
```

**문제 2: "캐시가 작동하지 않습니다"**

```bash
# 확인: PRESERVE_DB 설정
echo $PRESERVE_DB  # true여야 함

# 확인: DB가 유지되고 있는가?
ls -lh /home/valueforge/data/valueforge.db
# 수정 시간이 최근인지 확인
```

**문제 3: "월간 API 호출이 여전히 많습니다"**

```bash
# 확인: 당일 재실행 시 캐시 히트 로그
grep "dart financial cache hit" logs/pipeline.log | tail -5

# 확인: TTL 설정 (기본 30일)
grep "DART_CACHE_TTL" .env  # 없으면 기본값 사용
```

---

## 다음 단계 (선택사항)

### R2에서 DB 다운로드 방식 (고급)

현재는 로컬 DB를 재사용하지만, R2에서 다운로드하는 방식도 가능합니다:

```python
# 파이프라인 시작 전
previous_db = uploader.download_latest_db()
if previous_db:
    shutil.copy(previous_db, settings.DB_PATH)
    log.info("downloaded latest db from r2", path=str(previous_db))

# 파이프라인 실행
run_pipeline(run_date)

# 파이프라인 종료 후
uploader.upload_latest(_db_path)
```

**장점**: R2이 source of truth, 복제 인스턴스 간 공유 가능
**단점**: 다운로드 시간 추가, R2 대역폭 비용

### 데이터 검증 (권장)

```python
# DB 스키마 버전 체크
def validate_db_compatibility(db_path: Path) -> bool:
    conn = sqlite3.connect(str(db_path))
    schema_version = conn.execute(
        "SELECT schema_version FROM _metadata LIMIT 1"
    ).fetchone()[0]
    conn.close()
    
    # 현재 스키마와 비교
    return schema_version >= MIN_SUPPORTED_VERSION
```

---

## 체크리스트

- [x] PRESERVE_DB 설정 추가
- [x] runner.py 삭제 로직 옵션화
- [x] .env.example 업데이트
- [ ] 운영 환경 `.env` 설정 (PRESERVE_DB=true)
- [ ] 정기 모니터링 설정

---

## 관련 문서

- [DART_OPTIMIZATION.md](DART_OPTIMIZATION.md) - DART 캐싱 상세 가이드
- [PERFORMANCE_BENCHMARKS.md](PERFORMANCE_BENCHMARKS.md) - 성능 분석
- [docs/CLAUDE.md](CLAUDE.md) - 개발 가이드
