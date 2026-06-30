"""Estilos premium compartidos para la UI Streamlit.

La prioridad de este archivo es estabilidad visual: modo claro forzado,
contraste legible, padding controlado y componentes que no dependan del tema
oscuro/claro configurado por Streamlit.
"""

from __future__ import annotations

import streamlit as st


THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Arimo:ital,wght@0,400..700;1,400..700&family=Montserrat:ital,wght@0,100..900;1,100..900&display=swap');

:root {
    --bg: #F8FAFC;
    --card: #FFFFFF;
    --primary: #2563EB;
    --primary-hover: #1D4ED8;
    --text: #0F172A;
    --muted: #64748B;
    --muted-strong: #475569;
    --border: #E2E8F0;
    --border-strong: #CBD5E1;
    --success: #16A34A;
    --warning: #F59E0B;
    --error: #DC2626;
    --surface-soft: #F1F5F9;
    --blue-soft: #EFF6FF;
    --shadow: 0 1px 2px rgba(15, 23, 42, 0.04), 0 12px 30px rgba(15, 23, 42, 0.035);
}

html, body, .stApp, [data-testid="stAppViewContainer"] {
    background: var(--bg) !important;
    color: var(--text) !important;
    font-family: 'Arimo', system-ui, -apple-system, BlinkMacSystemFont, sans-serif !important;
}

.block-container {
    max-width: 1420px;
    padding: 18px 32px 44px !important;
}

[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stToolbar"] { right: 1rem !important; }

h1, h2, h3, h4,
.app-title, .page-title, .section-title, .action-title,
.nav-title, .timeline-title, .chat-role, .table-title {
    font-family: 'Montserrat', system-ui, sans-serif !important;
    color: var(--text) !important;
    letter-spacing: -0.025em;
}

p, label, span, div {
    font-family: 'Arimo', system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Sidebar remains optional: main screen also has top navigation. */
[data-testid="stSidebar"] {
    background: #FFFFFF !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] * { color: var(--text) !important; }
[data-testid="stSidebar"] .stCaptionContainer,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    color: var(--muted) !important;
}

/* Buttons */
.stButton > button {
    min-height: 44px !important;
    border-radius: 10px !important;
    border: 1px solid var(--border) !important;
    background: #FFFFFF !important;
    color: var(--text) !important;
    box-shadow: none !important;
    font-weight: 750 !important;
    white-space: normal !important;
    text-align: center !important;
    line-height: 20px !important;
    padding: 9px 14px !important;
    transition: background 120ms ease, border-color 120ms ease, color 120ms ease;
}
.stButton > button p,
.stButton > button span,
.stButton > button div {
    color: inherit !important;
    font-weight: inherit !important;
}
.stButton > button:hover {
    background: #F8FAFC !important;
    border-color: var(--primary) !important;
    color: var(--primary) !important;
}
.stButton > button[kind="primary"],
.stButton > button[data-testid="baseButton-primary"] {
    background: var(--primary) !important;
    border-color: var(--primary) !important;
    color: #FFFFFF !important;
}
.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid="baseButton-primary"]:hover {
    background: var(--primary-hover) !important;
    border-color: var(--primary-hover) !important;
    color: #FFFFFF !important;
}

/* Suggested action buttons */
.suggestion-anchor + div .stButton > button,
div[data-testid="column"] .stButton > button {
    min-height: 54px !important;
}

/* Metric cards */
div[data-testid="stMetric"] {
    background: #FFFFFF !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    padding: 16px 18px 14px !important;
    box-shadow: var(--shadow) !important;
}
div[data-testid="stMetricLabel"], div[data-testid="stMetricLabel"] * {
    color: var(--muted-strong) !important;
    font-size: 12px !important;
    line-height: 16px !important;
    font-weight: 850 !important;
}
div[data-testid="stMetricValue"], div[data-testid="stMetricValue"] * {
    color: var(--text) !important;
    font-family: 'Montserrat', system-ui, sans-serif !important;
    font-size: 29px !important;
    line-height: 36px !important;
    font-weight: 820 !important;
    letter-spacing: -0.035em !important;
}
div[data-testid="stMetricDelta"], div[data-testid="stMetricDelta"] * {
    color: var(--success) !important;
    font-size: 13px !important;
    font-weight: 800 !important;
}


/* Custom KPI cards: do not depend on st.metric internals. */
.metric-grid {
    display: grid;
    gap: 14px;
    margin: 8px 0 18px;
}
.metric-card {
    background: #FFFFFF !important;
    border: 1px solid var(--border) !important;
    border-radius: 14px !important;
    padding: 16px 18px 14px !important;
    box-shadow: var(--shadow) !important;
    min-height: 106px;
    display: flex;
    flex-direction: column;
    justify-content: center;
}
.metric-card-label {
    color: #334155 !important;
    font-size: 12px !important;
    line-height: 16px !important;
    font-weight: 900 !important;
    letter-spacing: 0.045em !important;
    text-transform: uppercase !important;
    margin-bottom: 9px !important;
}
.metric-card-value {
    color: var(--text) !important;
    font-family: 'Montserrat', system-ui, sans-serif !important;
    font-size: clamp(24px, 2.4vw, 34px) !important;
    line-height: 1.08 !important;
    font-weight: 880 !important;
    letter-spacing: -0.045em !important;
    word-break: break-word;
}
.metric-card-badge {
    display: inline-flex;
    align-self: flex-start;
    margin-top: 10px;
    padding: 4px 10px;
    border-radius: 999px;
    background: #F0FDF4;
    border: 1px solid #BBF7D0;
    color: var(--success) !important;
    font-size: 12px;
    line-height: 16px;
    font-weight: 850;
}

/* Clean top navigation */
.top-nav-title-row {
    background: #FFFFFF;
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 12px 16px;
    box-shadow: var(--shadow);
    margin: 0 0 10px;
}
.top-nav-help {
    color: var(--muted-strong) !important;
    font-size: 13px;
    line-height: 19px;
    margin-top: 2px;
}
.top-nav-spacer { height: 16px; }

/* Shared surfaces */
.page-shell, .card, .action-card, .empty-state, .filter-panel, .chat-panel, .insight-card {
    background: var(--card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    box-shadow: var(--shadow) !important;
    color: var(--text) !important;
}
.page-shell {
    padding: 24px 28px;
    margin-bottom: 18px;
}
.kicker {
    color: var(--primary) !important;
    font-size: 12px;
    line-height: 16px;
    font-weight: 850;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    margin-bottom: 8px;
}
.app-title {
    font-size: clamp(28px, 3vw, 38px);
    line-height: 1.14;
    font-weight: 850;
    margin: 0 0 8px;
    max-width: 1120px;
}
.page-title {
    font-size: clamp(24px, 2.1vw, 30px);
    line-height: 1.18;
    font-weight: 830;
    margin: 0 0 8px;
}
.section-title {
    font-size: 18px;
    line-height: 26px;
    font-weight: 820;
    margin: 0 0 8px;
}
.body-copy {
    color: var(--muted-strong) !important;
    font-size: 15px;
    line-height: 24px;
    max-width: 940px;
}
.card {
    padding: 18px 20px;
    margin-bottom: 14px;
}
.action-card {
    padding: 18px 20px;
    min-height: 128px;
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
}
.action-card:hover { border-color: var(--border-strong) !important; }
.action-title {
    font-size: 16px;
    line-height: 23px;
    font-weight: 820;
    margin: 0 0 8px;
}
.action-text {
    color: var(--muted-strong) !important;
    font-size: 13px;
    line-height: 20px;
}

/* Navigation pills in the main canvas */
.top-nav {
    background: rgba(255,255,255,0.86);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 10px;
    box-shadow: var(--shadow);
    margin-bottom: 16px;
}
.nav-brand { padding: 6px 2px 14px; }
.nav-logo {
    width: 36px;
    height: 36px;
    border-radius: 10px;
    background: var(--primary);
    color: #FFFFFF !important;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-weight: 900;
}
.nav-title { font-weight: 850; font-size: 16px; line-height: 20px; }
.nav-subtitle { color: var(--muted) !important; font-size: 12px; margin-top: 2px; }

.badge {
    display: inline-flex;
    align-items: center;
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 3px 9px;
    font-size: 12px;
    line-height: 16px;
    font-weight: 800;
    background: #F8FAFC;
    color: var(--muted-strong) !important;
}
.badge-success { color: var(--success) !important; background: #F0FDF4; border-color: #BBF7D0; }
.badge-warning { color: #B45309 !important; background: #FFFBEB; border-color: #FDE68A; }
.badge-error { color: var(--error) !important; background: #FEF2F2; border-color: #FECACA; }
.badge-blue { color: var(--primary) !important; background: #EFF6FF; border-color: #BFDBFE; }

/* Filters */
.filter-panel {
    padding: 18px 20px 16px;
    margin-bottom: 18px;
}
.filter-title-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 12px;
}
.small-label {
    color: var(--muted) !important;
    font-size: 12px;
    font-weight: 850;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
[data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] * {
    color: var(--muted-strong) !important;
    font-size: 13px !important;
    font-weight: 850 !important;
}
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea {
    background: #FFFFFF !important;
    color: var(--text) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    box-shadow: none !important;
}
[data-testid="stNumberInput"] button {
    background: #F8FAFC !important;
    color: var(--muted-strong) !important;
    border-color: var(--border) !important;
}
[data-baseweb="select"] > div,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stMultiSelect"] div[data-baseweb="select"] > div {
    background: #FFFFFF !important;
    color: var(--text) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    box-shadow: none !important;
}
[data-baseweb="select"] span, [data-baseweb="select"] div { color: var(--text) !important; }
[data-baseweb="tag"] {
    background: #EFF6FF !important;
    border: 1px solid #BFDBFE !important;
    border-radius: 999px !important;
}
[data-baseweb="tag"] span { color: var(--primary) !important; font-weight: 700 !important; }
[role="listbox"], [role="option"] { background: #FFFFFF !important; color: var(--text) !important; }

/* Chat: custom bubbles instead of relying on Streamlit's default chat colors. */
.chat-panel {
    padding: 18px 18px 12px;
    margin-bottom: 14px;
}
.chat-empty-note {
    color: var(--muted-strong);
    font-size: 14px;
    line-height: 22px;
    padding: 10px 2px;
}
.message-row {
    display: flex;
    gap: 12px;
    align-items: flex-start;
    margin: 12px 0;
}
.message-row.user { flex-direction: row-reverse; }
.avatar {
    width: 34px;
    height: 34px;
    border-radius: 10px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex: 0 0 34px;
    color: #FFFFFF;
    font-size: 15px;
    font-weight: 900;
    box-shadow: 0 1px 2px rgba(15,23,42,0.08);
}
.avatar.assistant { background: #F59E0B; color: #0F172A; }
.avatar.user { background: var(--primary); }
.bubble {
    max-width: min(880px, 100%);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 12px 14px;
    background: #FFFFFF;
    color: var(--text) !important;
    box-shadow: 0 1px 2px rgba(15,23,42,0.035);
}
.message-row.user .bubble {
    background: #EFF6FF;
    border-color: #BFDBFE;
}
.chat-role {
    color: var(--muted) !important;
    font-size: 12px;
    font-weight: 850;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 5px;
}
.chat-content {
    color: var(--text) !important;
    font-size: 15px;
    line-height: 24px;
    white-space: pre-wrap;
}
.chat-form-card {
    background: #FFFFFF;
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 14px;
    box-shadow: var(--shadow);
    margin-top: 10px;
}
.chat-form-card textarea {
    min-height: 86px !important;
    background: #FFFFFF !important;
    color: var(--text) !important;
}

/* Tables rendered as HTML to avoid dark dataframe styling. */
.clean-table-wrap {
    background: #FFFFFF;
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
    box-shadow: var(--shadow);
}
table.clean-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    color: var(--text);
}
table.clean-table thead th {
    background: #F8FAFC;
    color: var(--muted-strong);
    font-weight: 850;
    text-align: left;
    padding: 11px 12px;
    border-bottom: 1px solid var(--border);
}
table.clean-table tbody td {
    padding: 11px 12px;
    border-bottom: 1px solid #EEF2F7;
    vertical-align: top;
}
table.clean-table tbody tr:last-child td { border-bottom: 0; }
table.clean-table tbody tr:hover td { background: #F8FAFC; }

.timeline-item {
    border-left: 2px solid var(--border);
    padding-left: 16px;
    padding-bottom: 18px;
    margin-left: 8px;
    color: var(--text) !important;
}
.timeline-dot {
    width: 10px;
    height: 10px;
    border-radius: 999px;
    background: var(--primary);
    margin-left: -22px;
    margin-bottom: -10px;
}
.timeline-title { font-weight: 850; margin-bottom: 4px; }
.timeline-meta { color: var(--muted) !important; font-size: 12px; }
.empty-state {
    border-style: dashed !important;
    padding: 28px;
    text-align: center;
    color: var(--muted-strong) !important;
}
.section-spacer { height: 18px; }
hr { border-color: var(--border) !important; margin: 18px 0 20px !important; }
[data-testid="stExpander"] {
    background: #FFFFFF !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
}
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary * {
    color: var(--text) !important;
    font-weight: 800 !important;
}
[data-testid="stStatusWidget"] {
    background: #FFFFFF !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
}
[data-testid="stStatusWidget"] * { color: var(--text) !important; }

@media (max-width: 960px) {
    .block-container { padding: 16px 18px 36px !important; }
    .metric-grid { grid-template-columns: 1fr !important; }
    .page-shell { padding: 22px; }
    div[data-testid="stMetricValue"], div[data-testid="stMetricValue"] * {
        font-size: 25px !important;
        line-height: 32px !important;
    }
    .bubble { max-width: 100%; }
}

/* Ajuste final:navegación principal como sección nativa de Streamlit */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: #FFFFFF !important;
    border: 1px solid var(--border) !important;
    border-radius: 14px !important;
    box-shadow: var(--shadow) !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] p {
    color: var(--muted-strong) !important;
    font-size: 12px !important;
    font-weight: 900 !important;
    letter-spacing: 0.08em !important;
}
.top-nav-spacer { height: 14px; }
.metric-grid { width: 100%; }
.metric-card * { color: inherit; }
</style>
"""


def apply_theme() -> None:
    """Inyecta CSS global una vez por render."""
    st.markdown(THEME_CSS, unsafe_allow_html=True)
