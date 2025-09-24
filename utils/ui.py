# utils/ui.py
from __future__ import annotations
import streamlit as st
import altair as alt
from datetime import date, time

# Typography / colors used across charts & UI
BASE_FONT = "Inter, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial"

PALETTE = {
    "primary": "#4ECDC4",   # teal
    "secondary": "#FF6B6B", # reddish-orange
    "accent": "#45B7D1",    # light blue
    "muted": "#6c757d",     # gray
}

# Status colors for consistent theming
STATUS_COLORS = {
    "active": "#28a745",    # green
    "pending": "#ffc107",   # yellow
    "inactive": "#dc3545",  # red
    "approved": "#28a745",  # green
    "rejected": "#dc3545",  # red
}

STATUS_ICONS = {
    "active": "🟢",
    "pending": "🟡", 
    "inactive": "🔴",
    "approved": "✅",
    "rejected": "❌"
}

# ============================================================================
# CHART STYLING
# ============================================================================

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

# ============================================================================
# DB ERROR DISPLAY
# ============================================================================

def show_db_error(err: Exception, context: str | None = None):
    """
    Render a clear, user-friendly DB error. Detects common cases like
    missing tables (SQLSTATE 42P01) and shows a helpful message, with
    technical details tucked in an expander.
    """
    msg = str(err)
    code = getattr(err, "pgcode", None)  # psycopg2 attaches SQLSTATE here

    # Missing relation/table: SQLSTATE 42P01
    is_missing_table = (code == "42P01") or ("relation" in msg and "does not exist" in msg)

    if is_missing_table:
        human = "Feature coming soon.."
        if context:
            human = f"{context}: {human}"
        show_error(human + " (database tables are missing).")

        with st.expander("Technical details"):
            st.code(f"{type(err).__name__}: {msg}")
        return

    # Generic fallback
    human = "A database error occurred."
    if context:
        human = f"{context}: {human}"
    show_error(human)

    with st.expander("Technical details"):
        # If driver provides code, include it
        if code:
            st.code(f"SQLSTATE {code} · {type(err).__name__}: {msg}")
        else:
            st.code(f"{type(err).__name__}: {msg}")

# ============================================================================
# FORM COMPONENTS
# ============================================================================

def render_date_range_picker(label, default_start=None, default_end=None):
    """Render a date range picker with consistent styling"""
    default_start = default_start or date.today()
    default_end = default_end or date.today()
    
    return st.date_input(
        label, 
        value=(default_start, default_end),
        format="MM.DD.YYYY"
    )

def render_time_picker(label, default_time=None):
    """Render a time picker with default"""
    default_time = default_time or time(0, 0)
    return st.time_input(label, value=default_time)

def render_days_multiselect(label, default=None):
    """Render days of week multiselect"""
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return st.multiselect(label, days, default=default or [])

# ============================================================================
# MESSAGE COMPONENTS
# ============================================================================

def show_success(message):
    """Render a success message with consistent styling"""
    st.success(f"✅ {message}")

def show_error(message):
    """Render an error message with consistent styling"""
    st.error(f"❌ {message}")

def show_info(message):
    """Render an info message with consistent styling"""
    st.info(f"ℹ️ {message}")

def show_warning(message):
    """Render a warning message with consistent styling"""
    st.warning(f"⚠️ {message}")

# ============================================================================
# STATUS & DISPLAY COMPONENTS
# ============================================================================

def render_status_badge(status):
    """Render a status badge with appropriate color and icon"""
    icon = STATUS_ICONS.get(status.lower(), "⚪")
    return f"{icon} {status.title()}"

def render_metric_card(title, value, delta=None, help_text=None):
    """Render a metric card with consistent styling"""
    st.metric(
        label=title,
        value=value,
        delta=delta,
        help=help_text
    )

def render_colored_metric(title, value, status="neutral", delta=None):
    """Render a metric with status-based coloring"""
    color = STATUS_COLORS.get(status, PALETTE["muted"])
    
    # Use columns to add colored border effect
    with st.container():
        st.markdown(f"""
        <div style="
            border-left: 4px solid {color}; 
            padding-left: 10px; 
            margin-bottom: 10px;
        ">
        """, unsafe_allow_html=True)
        
        st.metric(title, value, delta=delta)
        
        st.markdown("</div>", unsafe_allow_html=True)

# ============================================================================
# INTERACTIVE COMPONENTS
# ============================================================================

def render_confirmation_dialog(message, key):
    """Render a confirmation dialog for destructive actions"""
    if st.button("Delete", key=f"delete_{key}", type="secondary"):
        st.session_state[f"confirm_{key}"] = True
    
    if st.session_state.get(f"confirm_{key}", False):
        st.warning(f"⚠️ {message}")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Yes, Delete", key=f"confirm_yes_{key}", type="primary"):
                st.session_state[f"confirmed_{key}"] = True
                st.session_state[f"confirm_{key}"] = False
                return True
        with col2:
            if st.button("Cancel", key=f"confirm_no_{key}"):
                st.session_state[f"confirm_{key}"] = False
    
    return False

def render_expandable_section(title, content_func, default_expanded=False):
    """Render an expandable section with consistent styling"""
    with st.expander(title, expanded=default_expanded):
        content_func()

# ============================================================================
# LAYOUT HELPERS
# ============================================================================

def create_two_column_layout():
    """Create a standard two-column layout"""
    return st.columns(2)

def create_three_column_layout():
    """Create a standard three-column layout"""
    return st.columns(3)

def create_sidebar_layout(sidebar_content_func, main_content_func):
    """Create a layout with sidebar and main content"""
    with st.sidebar:
        sidebar_content_func()
    
    main_content_func()

# ============================================================================
# SPECIALIZED COMPONENTS FOR YOUR APP
# ============================================================================

def render_offer_status_indicator(status, count=None):
    """Render an offer status with optional count"""
    icon = STATUS_ICONS.get(status.lower(), "⚪")
    color = STATUS_COLORS.get(status.lower(), PALETTE["muted"])
    
    if count is not None:
        display_text = f"{icon} {status.title()} ({count})"
    else:
        display_text = f"{icon} {status.title()}"
    
    st.markdown(f"""
    <span style="color: {color}; font-weight: bold;">
        {display_text}
    </span>
    """, unsafe_allow_html=True)

def render_restaurant_header(restaurant_name, user_name=None):
    """Render a consistent restaurant page header"""
    st.title(f"Restaurant Dashboard")
    if user_name:
        st.caption(f"Welcome back, {user_name}")
    
    st.markdown("---")

def render_page_section(title, content_func, help_text=None):
    """Render a page section with consistent styling"""
    if help_text:
        st.subheader(title, help=help_text)
    else:
        st.subheader(title)
    
    content_func()
    st.markdown("---")

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def apply_custom_css():
    """Apply custom CSS for consistent theming across the app"""
    st.markdown(f"""
    <style>
    .main .block-container {{
        font-family: {BASE_FONT};
    }}
    
    .stMetric {{
        border-radius: 8px;
        padding: 10px;
        border: 1px solid #e0e0e0;
    }}
    
    .offer-card {{
        border-left: 4px solid {PALETTE["primary"]};
        padding: 15px;
        margin: 10px 0;
        border-radius: 0 8px 8px 0;
        background-color: rgba(78, 205, 196, 0.05);
    }}
    </style>
    """, unsafe_allow_html=True)

def format_currency(amount):
    """Format currency consistently across the app"""
    return f"${amount:,.2f}"

def format_percentage(value, decimal_places=1):
    """Format percentage consistently"""
    return f"{value:.{decimal_places}f}%"