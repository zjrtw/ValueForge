"""Gemini AI를 사용한 투자 대상 종합 분석."""

from typing import Any

from src.utils.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)


def generate_investment_analysis(
    stock_code: str,
    stock_name: str,
    scores: dict[str, float],
    risk_flags: list[str],
    fundamentals: dict[str, Any],
    market_info: dict[str, Any],
    disclosure_summary: str = "",
) -> str:
    """Gemini AI를 사용해 종목의 종합 투자 분석을 생성한다.

    Args:
        stock_code: 종목 코드
        stock_name: 종목명
        scores: 점수 딕셔너리 (composite_score, value_score, quality_score, etc.)
        risk_flags: 위험 플래그 리스트
        fundamentals: 재무 정보 (per, pbr, roe, debt_ratio, etc.)
        market_info: 시장 정보 (market, sector, market_cap, dividend_yield)
        disclosure_summary: 최근 공시 요약

    Returns:
        Gemini가 생성한 종합 분석 텍스트
    """
    if not settings.AI_API_KEY:
        log.warning("ai_analysis_skipped: no API key configured")
        return _generate_fallback_analysis(stock_name, scores, risk_flags)

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        log.warning("gemini library not installed, using fallback analysis")
        return _generate_fallback_analysis(stock_name, scores, risk_flags)

    # Rate Limit 에러 대응: 최대 3회 재시도
    max_retries = 3
    retry_delay = 2  # 초 단위

    for attempt in range(max_retries):
        try:
            import time
            client = genai.Client(api_key=settings.AI_API_KEY)

            prompt = _build_analysis_prompt(
                stock_code, stock_name, scores, risk_flags, fundamentals, market_info, disclosure_summary
            )

            # 새 SDK 설정 형식
            config = types.GenerateContentConfig(
                safety_settings=[
                    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
                ]
            )

            response = client.models.generate_content(
                model=settings.AI_MODEL,
                contents=prompt,
                config=config
            )

            analysis = response.text
            log.info("ai_analysis_generated", stock_code=stock_code, model=settings.AI_MODEL, length=len(analysis))
            return analysis

        except Exception as exc:
            error_msg = str(exc)
            is_rate_limit = "rate_limit" in error_msg.lower() or "quota" in error_msg.lower()

            if is_rate_limit and attempt < max_retries - 1:
                wait_time = retry_delay * (attempt + 1)
                log.warning(
                    "gemini_rate_limit_retry",
                    stock_code=stock_code,
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    wait_seconds=wait_time,
                    error=error_msg,
                )
                time.sleep(wait_time)
                continue
            else:
                log.warning("gemini_analysis_failed", stock_code=stock_code, error=error_msg)
                return _generate_fallback_analysis(stock_name, scores, risk_flags)

    return _generate_fallback_analysis(stock_name, scores, risk_flags)


def _build_analysis_prompt(
    stock_code: str,
    stock_name: str,
    scores: dict[str, float],
    risk_flags: list[str],
    fundamentals: dict[str, Any],
    market_info: dict[str, Any],
    disclosure_summary: str,
) -> str:
    """Gemini 프롬프트를 구성한다."""

    flags_text = "없음" if not risk_flags else ", ".join(risk_flags[:5])

    prompt = f"""당신은 한국 주식 시장을 깊이 이해하는 투자 전문가입니다.

다음 종목에 대해 한국인 개인투자자를 위한 종합 투자 판단 가이드를 작성해주세요.

## 종목 정보
- 종목: {stock_name} ({stock_code})
- 시장: {market_info.get('market', 'N/A')}
- 섹터: {market_info.get('sector', 'N/A')}

## 재무 지표
- 복합 점수: {scores.get('composite_score', 0):.1f}/100
- 가치 점수: {scores.get('value_score', 0):.1f}/100
- 품질 점수: {scores.get('quality_score', 0):.1f}/100
- 안전성 점수: {scores.get('safety_score', 0):.1f}/100
- 성장성 점수: {scores.get('growth_score', 0):.1f}/100
- 모멘텀 점수: {scores.get('momentum_score', 0):.1f}/100

## 주요 지표
- PER: {fundamentals.get('per', 'N/A')}
- PBR: {fundamentals.get('pbr', 'N/A')}
- ROE: {fundamentals.get('roe', 'N/A')}%
- 부채비율: {fundamentals.get('debt_ratio', 'N/A')}%
- 배당수익률: {fundamentals.get('dividend_yield', 'N/A')}%
- 시가총액: {fundamentals.get('market_cap_b', 'N/A')}억원

## 위험 신호
{flags_text}

## 최근 공시
{disclosure_summary}

다음 형식으로 답변해주세요:

### 📊 시장 평가
(현재 평가가 저평가/적정/고평가인지 3-4문장)

### 💪 강점
- (2-3개의 긍정적 요소)

### ⚠️ 위험 요소
- (2-3개의 위험 요소)

### 🎯 투자 판단
(최종 투자 의견: 강력 매수/매수/보유/팔이/ 강력 매도)

### 💡 투자자 가이드
- 진입 전 확인사항
- 보유 시 주의사항
- 목표가 또는 손절 기준

마크다운 형식으로 명확하고 직관적으로 작성해주세요."""

    return prompt


def _generate_fallback_analysis(stock_name: str, scores: dict[str, float], risk_flags: list[str]) -> str:
    """Gemini가 불가능할 때 기본 분석을 생성한다."""

    composite = scores.get("composite_score", 0)
    opinion = "강력 매수" if composite >= 80 else "매수" if composite >= 70 else "보유" if composite >= 50 else "약세"

    analysis = f"""## {stock_name} 투자 분석 (자동 생성)

### 📊 시장 평가
복합 점수 {composite:.1f}점 기준으로 현재 종목의 가치투자 관점에서의 평가를 나타냅니다.

### 💪 강점
- 선별된 스크리닝 기준을 통과한 종목
- 다각적인 평가 지표 검토 완료

### ⚠️ 위험 요소
{("- " + chr(10) + "- ".join(risk_flags[:3])) if risk_flags else "- 현재 감지된 주요 위험 요소 없음"}

### 🎯 투자 판단
**{opinion}**

종목 선정 시스템의 점수를 참고하여 개인의 투자 목표와 위험 선호도에 맞춰 판단하시기 바랍니다.

### 💡 투자자 가이드
- 개별 재무제표 검토 필수
- 최근 공시 정보 확인
- 섹터 및 시장 동향 모니터링

**주의: 이 분석은 자동 생성되었으며, 투자 결정의 참고용입니다.**"""

    return analysis
