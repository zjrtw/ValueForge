import re
import sqlite3
import time
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from src.analysis.ai_analyst import generate_investment_analysis
from src.collectors.dart_news import summarize_disclosure_news
from src.collectors.gemini_client import GeminiClient
from src.collectors.news_collector import NewsArticle, fetch_stock_news
from src.db.repository import Repository
from src.utils.config import screening_params
from src.utils.logger import get_logger

log = get_logger(__name__)


def stage5_ai_analysis(
    ranked_df: pd.DataFrame,
    conn: sqlite3.Connection,
    run_date: str,
    *,
    params: dict[str, Any] | None = None,
    gemini_client: GeminiClient | None = None,
) -> int:
    """Stage 5 AI 정성 분석.

    Stage 4 순위 DataFrame에서 상위 N개 종목을 선택해
    1. AI 투자 가이드 (뉴스 기반, ai_insights 테이블)
    2. AI 종합 분석 (재무 기반, ai_analysis 테이블)
    을 생성하고 저장한다.

    Returns:
        저장된 ai_insights 행 수
    """
    p = params or screening_params.ai_analysis

    if not p.get("enabled", True):
        log.info("stage5_disabled", reason="ai_analysis.enabled=false in config")
        return 0

    client = gemini_client or GeminiClient(
        model=str(p.get("model", "gemini-1.5-flash")),
        rate_limit_sleep=float(p.get("rate_limit_sleep", 4.0)),
    )

    # API 키가 없어도 ai_analyst의 fallback 기능을 사용하기 위해 skip하지 않음
    # (GeminiClient.is_available()은 client.generate 호출 시 체크됨)

    if ranked_df.empty or "stock_name" not in ranked_df.columns:
        log.info("stage5_skipped", reason="no ranked stocks")
        return 0

    top_n = int(p.get("top_n", 30))
    # '홀딩스'가 포함된 종목 제외 필터링 추가
    analysis_candidates = ranked_df[~ranked_df["stock_name"].str.contains("홀딩스", na=False)]
    top_stocks = analysis_candidates.head(top_n)
    model_name = str(p.get("model", "gemini-1.5-flash"))

    repo = Repository(conn)
    insights: list[dict[str, Any]] = []

    for idx, (_, row) in enumerate(top_stocks.iterrows()):
        stock_code = str(row.get("stock_code", "")).zfill(6)
        stock_name = str(row.get("stock_name", ""))

        log.info("stage5_processing", stock_code=stock_code, stock_name=stock_name)

        # 1. AI 투자 가이드 (뉴스 기반)
        if client.is_available():
            news_articles = fetch_stock_news(stock_code, company_name=stock_name, max_articles=10)
            prompt = _build_prompt(row, news_articles)

            try:
                guide_text = client.generate(prompt)
                sentiment = _parse_sentiment(guide_text)

                insights.append({
                    "ticker": stock_code,
                    "run_date": run_date,
                    "guide_text": guide_text,
                    "sentiment": sentiment,
                    "generated_at": _utc_now(),
                    "model_used": model_name,
                })
                log.info("stage5_insight_generated", stock_code=stock_code, sentiment=sentiment)
            except Exception as exc:
                log.warning("stage5_insight_failed", stock_code=stock_code, error=str(exc))
        
        # 2. AI 종합 분석 (재무/공시 기반)
        try:
            # 점수 정보
            scores = {
                "composite_score": _as_float(row.get("composite_score")),
                "value_score": _as_float(row.get("value_score")),
                "quality_score": _as_float(row.get("quality_score")),
                "safety_score": _as_float(row.get("safety_score")),
                "growth_score": _as_float(row.get("growth_score")),
                "momentum_score": _as_float(row.get("momentum_score")),
            }
            # 위험 플래그
            risk_flags = str(row.get("risk_flags", "")).split(",") if row.get("risk_flags") else []
            # 재무 정보
            fundamentals = {
                "per": row.get("per"),
                "pbr": row.get("pbr"),
                "roe": row.get("roe"),
                "debt_ratio": row.get("debt_to_equity"),
                "dividend_yield": row.get("dividend_yield"),
                "market_cap_b": row.get("market_cap_b"),
            }
            # 시장 정보
            market_info = {"market": row.get("market"), "sector": row.get("sector")}
            # 공시 요약
            disclosure_summary = summarize_disclosure_news(stock_code, stock_name, days=30)

            analysis_text = generate_investment_analysis(
                stock_code, stock_name, scores, risk_flags, fundamentals, market_info, disclosure_summary
            )
            repo.upsert_ai_analysis(stock_code, run_date, analysis_text)
            log.info("stage5_analysis_generated", stock_code=stock_code)
        except Exception as exc:
            log.warning("stage5_analysis_failed", stock_code=stock_code, error=str(exc))

    if insights:
        repo.upsert_ai_insights(insights)
        log.info("stage5_complete", saved_insights=len(insights), top_n=top_n)
    
    return len(insights)


def _as_float(val: Any) -> float:
    try:
        return float(val) if pd.notna(val) else 0.0
    except (ValueError, TypeError):
        return 0.0


def _build_prompt(row: pd.Series, news_articles: list[NewsArticle]) -> str:
    stock_code = str(row.get("stock_code", "")).zfill(6)
    stock_name = str(row.get("stock_name", ""))
    market = str(row.get("market", ""))
    sector = str(row.get("sector", "") or "")

    composite_score = _fmt(row.get("composite_score"))
    per = _fmt(row.get("per"))
    pbr = _fmt(row.get("pbr"))
    roe = _fmt(row.get("roe"))
    dividend_yield = _fmt(row.get("dividend_yield"))
    final_rank = int(row.get("final_rank", 0)) if row.get("final_rank") is not None else "-"

    if news_articles:
        headlines = "\n".join(
            f"- [{a.published_at}] {a.title}" for a in news_articles
        )
        news_section = f"\n\n## 최근 뉴스 헤드라인\n{headlines}"
    else:
        news_section = "\n\n## 최근 뉴스 헤드라인\n(수집된 뉴스 없음)"

    return f"""당신은 한국 주식 투자 전문가입니다. 다음 종목 정보와 최근 뉴스를 바탕으로 투자 가이드를 작성하세요.

## 종목 정보
- 종목명: {stock_name} ({stock_code})
- 시장: {market} | 섹터: {sector}
- 가치 스크리닝 종합점수: {composite_score}점 (순위: {final_rank}위)
- PER: {per}배 | PBR: {pbr}배
- ROE: {roe}% | 배당수익률: {dividend_yield}%{news_section}

## 작성 지침
1. 위 재무 지표와 뉴스를 종합하여 투자 판단을 서술하세요 (200자 이내).
2. 마지막 줄에 반드시 다음 형식으로 투자 의견을 명시하세요:
   투자의견: 긍정 / 투자의견: 중립 / 투자의견: 부정 (셋 중 하나만 선택)
3. 투기적 조언이나 구체적인 가격 예측은 하지 마세요."""


def _parse_sentiment(text: str) -> str:
    """텍스트에서 '투자의견: [긍정/중립/부정]' 패턴을 찾아 감성을 추출한다."""
    match = re.search(r"투자의견\s*:\s*(긍정|중립|부정)", text)
    if match:
        return match.group(1)
    
    # 예외 상황: 명시적인 형식이 없을 경우 텍스트 기반 fallback
    if "투자의견: 긍정" in text or "투자의견:긍정" in text:
        return "긍정"
    if "투자의견: 부정" in text or "투자의견:부정" in text:
        return "부정"
    return "중립"


def _fmt(value: Any) -> str:
    if value is None:
        return "N/A"
    try:
        f = float(value)
        if f != f:  # NaN check
            return "N/A"
        return f"{f:.2f}"
    except (TypeError, ValueError):
        return "N/A"


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
