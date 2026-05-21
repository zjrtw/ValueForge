"""재사용 가능한 Plotly 극좌표 레이더 차트 컴포넌트.

사용 예:
    from src.ui.components.radar_chart import render_radar

    fig = render_radar({"가치": 85, "품질": 70, "안전": 60, "성장": 75, "모멘텀": 50})
    st.plotly_chart(fig, use_container_width=True)

    # 두 종목 비교
    fig = render_radar(
        values_a,
        label="삼성전자",
        overlay=values_b,
        overlay_label="SK하이닉스",
    )
"""
from __future__ import annotations

import plotly.graph_objects as go

# 기본 색상 팔레트 (메인 / 오버레이)
_DEFAULT_LINE = "rgba(99, 110, 250, 0.85)"
_DEFAULT_FILL = "rgba(99, 110, 250, 0.18)"
_OVERLAY_LINE = "rgba(239, 85, 59, 0.85)"
_OVERLAY_FILL = "rgba(239, 85, 59, 0.15)"


def prepare_radar_coords(
    values: dict[str, float],
) -> tuple[list[str], list[float]]:
    """레이더 폴리곤을 닫기 위해 첫 카테고리·값을 끝에 반복한 (theta, r) 쌍을 반환한다."""
    categories = list(values.keys())
    vals = [float(v) for v in values.values()]
    return categories + [categories[0]], vals + [vals[0]]


def _make_trace(
    values: dict[str, float],
    name: str,
    line_color: str,
    fill_color: str,
) -> go.Scatterpolar:
    theta, r = prepare_radar_coords(values)
    return go.Scatterpolar(
        r=r,
        theta=theta,
        fill="toself",
        fillcolor=fill_color,
        line=dict(color=line_color, width=2),
        name=name,
    )


def render_radar(
    values: dict[str, float],
    *,
    label: str = "점수",
    line_color: str = _DEFAULT_LINE,
    fill_color: str = _DEFAULT_FILL,
    overlay: dict[str, float] | None = None,
    overlay_label: str = "비교",
    overlay_line_color: str = _OVERLAY_LINE,
    overlay_fill_color: str = _OVERLAY_FILL,
    max_value: float = 100.0,
    height: int = 320,
) -> go.Figure:
    """Plotly 극좌표 레이더 차트 Figure를 반환한다.

    Args:
        values:            카테고리 → 값 딕셔너리 (0–max_value 범위 권장).
        label:             메인 트레이스 범례 레이블.
        line_color:        메인 트레이스 선 색상 (rgba 문자열).
        fill_color:        메인 트레이스 채우기 색상 (rgba 문자열).
        overlay:           두 번째(비교용) 트레이스 값 딕셔너리. None이면 단일 트레이스.
        overlay_label:     오버레이 트레이스 범례 레이블.
        overlay_line_color: 오버레이 선 색상.
        overlay_fill_color: 오버레이 채우기 색상.
        max_value:         방사축 최대값.
        height:            차트 높이(px).

    Returns:
        go.Figure
    """
    if not values:
        raise ValueError("values가 비어 있습니다.")

    traces: list[go.Scatterpolar] = [
        _make_trace(values, label, line_color, fill_color)
    ]

    if overlay is not None:
        if set(overlay.keys()) != set(values.keys()):
            raise ValueError("overlay의 카테고리가 values와 일치하지 않습니다.")
        traces.append(
            _make_trace(overlay, overlay_label, overlay_line_color, overlay_fill_color)
        )

    fig = go.Figure(data=traces)
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, max_value],
                tickfont=dict(size=10),
            ),
            angularaxis=dict(tickfont=dict(size=12)),
        ),
        showlegend=overlay is not None,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2),
        margin=dict(l=40, r=40, t=40, b=40),
        height=height,
    )
    return fig
