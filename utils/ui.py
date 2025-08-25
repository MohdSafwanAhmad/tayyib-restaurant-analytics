# utils/ui.py
from __future__ import annotations
import altair as alt

# Typography / colors used across charts & UI
BASE_FONT = "Inter, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial"

PALETTE = {
    "primary": "#4ECDC4",   # teal
    "secondary": "#FF6B6B", # reddish-orange
    "accent": "#45B7D1",    # light blue
    "muted": "#6c757d",     # gray
}

def chart_frame(c: alt.Chart, *, height: int = 300, label_angle: int = 0) -> alt.Chart:
    """
    Apply consistent look-and-feel to any Altair chart.
    - No chart-level titles (we'll title via Streamlit sections)
    - Horizontal axis labels by default
    - Respect Streamlit theme
    """
    return (
        c.properties(width="container", height=height)
         .configure_axis(
            grid=True,
            tickSize=3,
            labelFont=BASE_FONT,
            titleFont=BASE_FONT,
            labelAngle=label_angle,  # keep horizontal unless overridden
         )
         .configure_legend(
            labelFont=BASE_FONT,
            titleFont=BASE_FONT,
            orient="top",
         )
         # No .properties(title=...) here – titles live in Streamlit, not on the chart image
         .interactive()
    )
