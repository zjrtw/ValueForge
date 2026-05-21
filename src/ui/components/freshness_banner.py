"""데이터 최신성 배너 컴포넌트.

run_date를 표시하고, 2일 이상 경과 시 경고 배너를 렌더링한다.
"""
from __future__ import annotations

from datetime import date

import streamlit as st

from src.ui.data_loader import load_metadata

_STALE_DAYS = 2    # 이 이상이면 경고
_CRITICAL_DAYS = 5 # 이 이상이면 오류 수준 경고


def get_data_age_days(run_date_str: str, today: date | None = None) -> int:
    """run_date 문자열(YYYY-MM-DD)과 오늘 날짜 사이의 캘린더 일수를 반환한다."""
    ref = today or date.today()
    run = date.fromisoformat(run_date_str)
    return (ref - run).days


def get_freshness_level(age_days: int) -> str:
    """경과 일수로 신선도 레벨을 반환한다.

    Returns:
        "fresh"      — 1일 이하 (최신)
        "stale"      — 2–4일 (경고)
        "very_stale" — 5일 이상 (심각)
    """
    if age_days < _STALE_DAYS:
        return "fresh"
    if age_days < _CRITICAL_DAYS:
        return "stale"
    return "very_stale"


def render() -> None:
    """데이터 최신성 배너를 렌더링한다.

    메타데이터를 조회할 수 없으면 조용히 실패하고 경고만 표시한다.
    """
    try:
        meta = load_metadata()
    except Exception:
        st.warning("⚠️ 데이터 메타데이터를 불러올 수 없습니다.")
        return

    run_date_str: str | None = meta.get("run_date")
    if not run_date_str:
        st.warning("⚠️ 최신 실행 날짜 정보가 없습니다.")
        return

    try:
        age = get_data_age_days(run_date_str)
    except ValueError:
        st.warning(f"⚠️ 날짜 형식 오류: {run_date_str}")
        return

    level = get_freshness_level(age)
    candidates: int = meta.get("final_candidates", 0)

    if level == "fresh":
        st.success(
            f"✅ 데이터 최신 상태 — 기준일: **{run_date_str}** "
            f"(어제 또는 오늘) · 후보 종목: {candidates}개"
        )
    elif level == "stale":
        st.warning(
            f"⚠️ 데이터가 **{age}일** 전 기준입니다 (마지막 실행: {run_date_str}). "
            f"파이프라인이 지연되고 있을 수 있습니다."
        )
    else:
        st.error(
            f"🚨 데이터가 **{age}일** 동안 갱신되지 않았습니다 (마지막 실행: {run_date_str}). "
            f"파이프라인 오류를 확인하세요."
        )
