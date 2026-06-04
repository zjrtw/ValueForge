from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Any

import pandas as pd

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

    Stage 4 순위 DataFrame에서 상위 N개 종목을 선택해 뉴스를 수집하고,
    Gemini API로 투자 가이드를 생성 후 ai_insights 테이블에 저장한다.
    AI_API_KEY 미설정 시 0 반환 후 건너뜀.

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

    if not client.is_available():
        log.info("stage5_skipped", reason="AI_API_KEY not set")
        return 0

    top_n = int(p.get("top_n", 30))
    top_stocks = ranked_df.head(top_n)
    model_name = str(p.get("model", "gemini-1.5-flash"))

    repo = Repository(conn)
    saved_count = 0

    for _, row in top_stocks.iterrows():
        stock_code = str(row.get("stock_code", "")).zfill(6)
        stock_name = str(row.get("stock_name", ""))

        news_articles = fetch_stock_news(stock_code, company_name=stock_name, max_articles=10)
        prompt = _build_prompt(row, news_articles)

        try:
            guide_text = client.generate(prompt)
        except Exception as exc:
            log.warning("stage5_gemini_failed", stock_code=stock_code, error=str(exc))
            continue

        sentiment = _parse_sentiment(guide_text)

        repo.upsert_ai_insights([{
            "ticker": stock_code,
            "run_date": run_date,
            "guide_text": guide_text,
            "sentiment": sentiment,
            "generated_at": _utc_now(),
            "model_used": model_name,
        }])
        saved_count += 1
        log.info("stage5_insight_saved", stock_code=stock_code, stock_name=stock_name, sentiment=sentiment)

    log.info("stage5_complete", saved=saved_count, top_n=top_n)
    return saved_count


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
