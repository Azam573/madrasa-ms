"""
utils.py — Shared theming, CSS injection, and UI helper components.
Design system: Deep teal primary, warm amber accent, clean sans-serif typography.
"""

import streamlit as st
import re
from datetime import date, datetime


# ---------------------------------------------------------------------------
# Design Tokens
# ---------------------------------------------------------------------------

PALETTE = {
    "primary":     "#0F4C5C",   # deep teal
    "primary_lt":  "#1a6b80",
    "accent":      "#E8A838",   # warm amber
    "accent_lt":   "#f5c96d",
    "success":     "#2E7D32",
    "danger":      "#C62828",
    "warning":     "#F57F17",
    "bg":          "#F7F9FA",
    "card":        "#FFFFFF",
    "border":      "#DDE3E7",
    "text":        "#1A2332",
    "muted":       "#6B7A8D",
    "sidebar_bg":  "#0F4C5C",
    "sidebar_txt": "#EAF4F8",
}


GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Amiri:wght@400;700&display=swap');

:root {
    --primary:    #0F4C5C;
    --primary-lt: #1a6b80;
    --accent:     #E8A838;
    --success:    #2E7D32;
    --danger:     #C62828;
    --warning:    #F57F17;
    --bg:         #F7F9FA;
    --card:       #FFFFFF;
    --border:     #DDE3E7;
    --text:       #1A2332;
    --muted:      #6B7A8D;
    --radius:     10px;
    --shadow:     0 2px 12px rgba(15,76,92,0.10);
}

/* ── Global resets ── */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
    color: var(--text) !important;
}

.main .block-container {
    padding: 1.5rem 2rem 4rem 2rem !important;
    max-width: 1280px !important;
    background: var(--bg) !important;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: var(--primary) !important;
    border-right: none !important;
}
section[data-testid="stSidebar"] * {
    color: #EAF4F8 !important;
}
section[data-testid="stSidebar"] .stRadio label {
    padding: 0.5rem 1rem !important;
    border-radius: 8px !important;
    transition: background 0.2s !important;
    cursor: pointer !important;
}
section[data-testid="stSidebar"] .stRadio label:hover {
    background: rgba(255,255,255,0.12) !important;
}

/* ── Cards ── */
.erp-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.25rem 1.5rem;
    box-shadow: var(--shadow);
    margin-bottom: 1rem;
}

/* ── KPI metric tiles ── */
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 1rem;
    margin-bottom: 1.5rem;
}
.kpi-tile {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1rem 1.25rem;
    text-align: center;
    box-shadow: var(--shadow);
    border-top: 3px solid var(--primary);
}
.kpi-tile .kpi-val {
    font-size: 2rem;
    font-weight: 700;
    color: var(--primary);
    line-height: 1;
}
.kpi-tile .kpi-label {
    font-size: 0.75rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 0.35rem;
}
.kpi-tile.accent { border-top-color: var(--accent); }
.kpi-tile.accent .kpi-val { color: #9a6800; }
.kpi-tile.success { border-top-color: var(--success); }
.kpi-tile.success .kpi-val { color: var(--success); }
.kpi-tile.danger { border-top-color: var(--danger); }
.kpi-tile.danger .kpi-val { color: var(--danger); }

/* ── Page header ── */
.page-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 1.5rem;
    padding-bottom: 0.75rem;
    border-bottom: 2px solid var(--border);
}
.page-header .icon {
    width: 40px; height: 40px;
    background: var(--primary);
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.3rem;
}
.page-header h1 {
    font-size: 1.4rem !important;
    font-weight: 700 !important;
    margin: 0 !important;
    padding: 0 !important;
    color: var(--text) !important;
}
.page-header .sub {
    font-size: 0.8rem;
    color: var(--muted);
    margin-top: 0.1rem;
}

/* ── Status badges ── */
.badge {
    display: inline-block;
    padding: 0.2rem 0.65rem;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.03em;
    text-transform: uppercase;
}
.badge-success { background: #E8F5E9; color: var(--success); }
.badge-warning { background: #FFF8E1; color: #9a6800; }
.badge-danger  { background: #FFEBEE; color: var(--danger); }
.badge-info    { background: #E3F2FD; color: #1565C0; }
.badge-muted   { background: #ECEFF1; color: #546E7A; }

/* ── Step indicator ── */
.step-bar {
    display: flex;
    align-items: center;
    margin-bottom: 1.5rem;
}
.step-item {
    display: flex; align-items: center; gap: 0.4rem;
}
.step-dot {
    width: 28px; height: 28px;
    border-radius: 50%;
    background: var(--border);
    color: var(--muted);
    font-size: 0.8rem;
    font-weight: 700;
    display: flex; align-items: center; justify-content: center;
}
.step-dot.active   { background: var(--primary); color: white; }
.step-dot.done     { background: var(--success); color: white; }
.step-label { font-size: 0.78rem; color: var(--muted); }
.step-label.active { color: var(--primary); font-weight: 600; }
.step-connector {
    flex: 1;
    height: 2px;
    background: var(--border);
    margin: 0 0.5rem;
}
.step-connector.done { background: var(--success); }

/* ── Table tweaks ── */
.stDataFrame { border-radius: var(--radius) !important; overflow: hidden; }

/* ── Form labels ── */
.stTextInput > label, .stSelectbox > label,
.stNumberInput > label, .stDateInput > label,
.stTextArea > label { font-weight: 500; font-size: 0.85rem; }

/* ── Primary button ── */
.stButton > button[kind="primary"],
.stFormSubmitButton > button {
    background: var(--primary) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    padding: 0.5rem 1.5rem !important;
    transition: background 0.2s !important;
}
.stButton > button[kind="primary"]:hover {
    background: var(--primary-lt) !important;
}

/* ── Divider ── */
.section-divider {
    border: none;
    border-top: 1px solid var(--border);
    margin: 1.25rem 0;
}

/* ── Voucher print area ── */
.voucher {
    border: 2px solid var(--primary);
    border-radius: var(--radius);
    padding: 1.5rem;
    font-family: 'Inter', sans-serif;
    max-width: 400px;
}
.voucher .vch-header {
    text-align: center;
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.75rem;
    margin-bottom: 0.75rem;
}
.voucher .vch-row {
    display: flex;
    justify-content: space-between;
    font-size: 0.85rem;
    padding: 0.2rem 0;
}
.voucher .vch-total {
    font-weight: 700;
    font-size: 1.1rem;
    color: var(--primary);
    border-top: 1px solid var(--border);
    margin-top: 0.5rem;
    padding-top: 0.5rem;
}

/* ── Alert boxes ── */
.alert {
    padding: 0.75rem 1rem;
    border-radius: 8px;
    font-size: 0.88rem;
    margin-bottom: 1rem;
}
.alert-info    { background: #E3F2FD; border-left: 4px solid #1565C0; }
.alert-success { background: #E8F5E9; border-left: 4px solid var(--success); }
.alert-warning { background: #FFF8E1; border-left: 4px solid var(--warning); }
.alert-danger  { background: #FFEBEE; border-left: 4px solid var(--danger); }
</style>
"""


def inject_css():
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# UI components
# ---------------------------------------------------------------------------

def page_header(icon: str, title: str, subtitle: str = ""):
    st.markdown(
        f"""<div class="page-header">
            <div class="icon">{icon}</div>
            <div><h1>{title}</h1>
            {"<div class='sub'>" + subtitle + "</div>" if subtitle else ""}
            </div>
        </div>""",
        unsafe_allow_html=True,
    )


def kpi_row(metrics: list[dict]):
    """
    metrics = [{"label": "Total Students", "value": 120, "cls": ""}]
    cls options: accent | success | danger | ""
    """
    tiles = ""
    for m in metrics:
        cls = m.get("cls", "")
        tiles += f"""<div class="kpi-tile {cls}">
            <div class="kpi-val">{m['value']}</div>
            <div class="kpi-label">{m['label']}</div>
        </div>"""
    st.markdown(f'<div class="kpi-grid">{tiles}</div>', unsafe_allow_html=True)


def badge(text: str, kind: str = "info"):
    """kind: success | warning | danger | info | muted"""
    return f'<span class="badge badge-{kind}">{text}</span>'


def card(content_html: str):
    st.markdown(f'<div class="erp-card">{content_html}</div>', unsafe_allow_html=True)


def step_bar(steps: list[str], current: int):
    """current is 0-indexed."""
    html = '<div class="step-bar">'
    for i, label in enumerate(steps):
        if i > 0:
            done_cls = "done" if i <= current else ""
            html += f'<div class="step-connector {done_cls}"></div>'
        if i < current:
            dot_cls, lbl_cls = "done", ""
            num = "✓"
        elif i == current:
            dot_cls, lbl_cls = "active", "active"
            num = str(i + 1)
        else:
            dot_cls, lbl_cls = "", ""
            num = str(i + 1)
        html += f"""<div class="step-item">
            <div class="step-dot {dot_cls}">{num}</div>
            <span class="step-label {lbl_cls}">{label}</span>
        </div>"""
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def alert(msg: str, kind: str = "info"):
    """kind: info | success | warning | danger"""
    st.markdown(f'<div class="alert alert-{kind}">{msg}</div>', unsafe_allow_html=True)


def divider():
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def get_tenant_id() -> int:
    return st.session_state.get("tenant_id", 1)


def get_active_session_id() -> int | None:
    return st.session_state.get("active_session_id")


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

def validate_mobile(m: str) -> bool:
    return bool(re.match(r"^(\+?880|0)?1[3-9]\d{8}$", m.strip())) if m else True


def validate_required(fields: dict) -> list[str]:
    """Returns list of missing field names."""
    return [k for k, v in fields.items() if not v and v != 0]


# ---------------------------------------------------------------------------
# Grade utilities
# ---------------------------------------------------------------------------

GRADE_TABLE = [
    (80, "A+", 5.0),
    (70, "A",  4.0),
    (60, "A-", 3.5),
    (50, "B",  3.0),
    (40, "C",  2.0),
    (33, "D",  1.0),
    (0,  "F",  0.0),
]


def get_grade(percent: float) -> tuple[str, float]:
    for threshold, letter, gpa in GRADE_TABLE:
        if percent >= threshold:
            return letter, gpa
    return "F", 0.0


def months_list():
    return [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]


def current_year():
    return datetime.now().year
