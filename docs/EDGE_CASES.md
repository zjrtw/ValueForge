# ValueForge 예외 상황(Edge Case) 분석 리포트

본 문서는 ValueForge 프로젝트에서 발생할 수 있는 주요 예외 상황(Edge Case)들을 식별하고 대응 방안을 정리한 리포트입니다.

## 1. 분석된 주요 예외 상황 (Edge Cases)

### 1.1 데이터 수집 단계 (Data Collection)

- **빈 종목 리스트 (Zero Total)**: API 장애 또는 휴장일 오류 등으로 인해 수집 대상 종목이 0개로 조회되는 경우. 파이프라인이 즉시 `PipelineAbortError`를 발생시켜 잘못된 데이터 덮어쓰기를 방지해야 합니다.
- **수집 임계값 미달 (Threshold Failure)**: DART API의 일 10,000건 한도 초과 또는 일시적 네트워크 장애로 인해 수집 성공률이 50% 미만으로 떨어지는 경우. 무의미한 랭킹 생성을 막기 위해 파이프라인을 중단합니다.
- **개별 종목 수집 예외**: 특정 종목 데이터가 누락되어 KeyError 등이 발생하는 경우. 파이프라인 전체를 멈추지 않고, `collect_with_skip` 로직을 통해 해당 종목만 안전하게 건너뛰고 오류를 로깅해야 합니다.

### 1.2 스크리닝 및 스코어링 단계 (Screening & Scoring)

- **Zero Division 및 NaN 처리**: 부채비율, PER, PBR 등을 계산할 때 분모가 0이거나 데이터가 누락(None)된 경우. `pandas` 처리 과정에서 무한대(inf)나 NaN이 발생할 수 있으며, Stage 1 필터에서 이러한 종목을 제외하거나 최하점으로 처리해야 합니다.
- **가치 함정(Value Trap) 플래그 기준치 극단값**: 이익률이 -100% 미만이거나 부채비율이 극단적으로 높은 경우 예기치 않은 오버플로우나 스코어 왜곡이 발생할 수 있습니다.

### 1.3 데이터베이스 및 R2 저장소 (Database & Storage)

- **SQLite 동시 쓰기 잠금 (Database locked)**: `latest.db` 파일에 대해 파이프라인 쓰기와 Streamlit의 읽기가 동시에 발생할 때 파일 락이 걸릴 수 있습니다. (Streamlit 읽기 전용 접근 `mode=ro` 준수 필수)
- **R2 업로드 실패**: 외부 네트워크 오류 시 업로드가 부분적으로만 완료되어 `latest.db` 파일이 손상될 가능성. (boto3 재시도 로직 `with_retry` 적용 필수)

---

## 2. 테스트 실행 방법

위의 주요 예외 상황 중 **데이터 수집 중단 및 스킵 로직**에 대한 검증을 수행하는 테스트 파일(`tests/test_edge_cases.py`)이 작성되었습니다.

아래 명령어를 통해 테스트 코드를 실행하고 Edge Case에 대한 방어 로직이 정상 작동하는지 확인할 수 있습니다.

```bash
# 가상환경 활성화 (필요시)
source .venv/bin/activate

# Edge Case 테스트 코드 실행
pytest tests/test_edge_cases.py -v
```

**예상 실행 결과:**

```text
============================= test session starts ==============================
collected 5 items

tests/test_edge_cases.py::test_check_collection_threshold_zero_total PASSED [ 20%]
tests/test_edge_cases.py::test_check_collection_threshold_below_threshold PASSED [ 40%]
tests/test_edge_cases.py::test_check_collection_threshold_success PASSED [ 60%]
tests/test_edge_cases.py::test_collect_with_skip_exception PASSED        [ 80%]
tests/test_edge_cases.py::test_collect_with_skip_success PASSED          [100%]

============================== 5 passed in 0.05s ===============================

```
