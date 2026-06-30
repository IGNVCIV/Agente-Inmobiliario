"""Componentes visuales reutilizables para la UI Streamlit."""

from __future__ import annotations

from html import escape
from typing import Iterable

import pandas as pd
import streamlit as st


def page_header(kicker: str, title: str, description: str) -> None:
    st.markdown(
        f"""
        <div class="page-shell">
            <div class="kicker">{escape(kicker)}</div>
            <div class="page-title">{escape(title)}</div>
            <div class="body-copy">{escape(description)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def hero(title: str, description: str, kicker: str = "Real Estate AI Agent") -> None:
    st.markdown(
        f"""
        <div class="page-shell">
            <div class="kicker">{escape(kicker)}</div>
            <div class="app-title">{escape(title)}</div>
            <div class="body-copy">{escape(description)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(title: str, subtitle: str | None = None) -> None:
    subtitle_html = f'<div class="body-copy">{escape(subtitle)}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div style="margin: 4px 0 14px;">
            <div class="section-title">{escape(title)}</div>
            {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_spacer(size: int = 18) -> None:
    st.markdown(f'<div style="height:{size}px;"></div>', unsafe_allow_html=True)


def badge(text: str, kind: str = "blue") -> str:
    return f'<span class="badge badge-{kind}">{escape(str(text))}</span>'


def card(title: str, body: str, badge_text: str | None = None, badge_kind: str = "blue", **kwargs) -> None:
    """Card informativa. Acepta también `badge=` por compatibilidad."""
    if badge_text is None and "badge" in kwargs:
        badge_text = kwargs.get("badge")
    badge_html = badge(badge_text, badge_kind) if badge_text else ""
    title_margin = "10px" if badge_text else "0"
    st.markdown(
        f"""
        <div class="card">
            {badge_html}
            <div class="action-title" style="margin-top: {title_margin};">{escape(title)}</div>
            <div class="action-text">{escape(body)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def action_card(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="action-card">
            <div class="action-title">{escape(title)}</div>
            <div class="action-text">{escape(body)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def empty_state(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="empty-state">
            <div class="section-title">{escape(title)}</div>
            <div class="body-copy" style="margin: 0 auto;">{escape(body)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def timeline_item(title: str, meta: str, body: str, status: str = "success") -> None:
    kind = "success" if str(status).lower() in {"ok", "success", "completed", "exitoso", "éxito"} else "error"
    st.markdown(
        f"""
        <div class="timeline-item">
            <div class="timeline-dot"></div>
            <div class="timeline-title">{escape(title)} {badge(status, kind)}</div>
            <div class="timeline-meta">{escape(meta)}</div>
            <div class="action-text" style="margin-top: 6px;">{escape(body)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_row(metrics: Iterable[tuple[str, str, str | None]], columns: int = 4) -> None:
    """Renderiza KPIs como cards HTML propias, sin depender de st.metric.

    Importante: el HTML se genera sin indentación inicial para evitar que
    Markdown lo interprete como bloque de código.
    """
    items = list(metrics)
    if not items:
        return

    try:
        safe_columns = max(1, min(int(columns), 4))
    except (TypeError, ValueError):
        safe_columns = 4

    cards: list[str] = []
    for label, value, delta in items:
        delta_html = f'<div class="metric-card-badge">{escape(str(delta))}</div>' if delta else ""
        cards.append(
            '<div class="metric-card">'
            f'<div class="metric-card-label">{escape(str(label))}</div>'
            f'<div class="metric-card-value">{escape(str(value))}</div>'
            f'{delta_html}'
            '</div>'
        )

    html = (
        f'<div class="metric-grid" style="grid-template-columns: repeat({safe_columns}, minmax(0, 1fr));">'
        + "".join(cards)
        + '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def nav_brand() -> None:
    st.markdown(
        """
        <div class="nav-brand">
            <div style="display:flex; align-items:center; gap: 10px;">
                <div class="nav-logo">AI</div>
                <div>
                    <div class="nav-title">Real Estate Agent</div>
                    <div class="nav-subtitle">Ollama local · Enterprise UI</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def message_bubble(role: str, content: str) -> None:
    """Burbuja de chat propia para evitar problemas de contraste del chat nativo."""
    role_key = "user" if role == "user" else "assistant"
    label = "Usuario" if role_key == "user" else "Agente"
    icon = "U" if role_key == "user" else "AI"
    st.markdown(
        f"""
        <div class="message-row {role_key}">
            <div class="avatar {role_key}">{escape(icon)}</div>
            <div class="bubble">
                <div class="chat-role">{escape(label)}</div>
                <div class="chat-content">{escape(content)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def html_table(df: pd.DataFrame, max_rows: int = 10, max_chars: int = 90) -> None:
    """Tabla HTML clara para evitar que st.dataframe herede tema oscuro."""
    if df is None or df.empty:
        empty_state("Sin datos", "No hay registros disponibles para mostrar.")
        return

    show_df = df.head(max_rows).copy()
    headers = "".join(f"<th>{escape(str(col))}</th>" for col in show_df.columns)
    rows: list[str] = []
    for _, row in show_df.iterrows():
        cells: list[str] = []
        for value in row.tolist():
            if pd.isna(value):
                text = "N/D"
            else:
                text = str(value)
            if len(text) > max_chars:
                text = text[: max_chars - 1] + "…"
            cells.append(f"<td>{escape(text)}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")

    st.markdown(
        f"""
        <div class="clean-table-wrap">
            <table class="clean-table">
                <thead><tr>{headers}</tr></thead>
                <tbody>{''.join(rows)}</tbody>
            </table>
        </div>
        """,
        unsafe_allow_html=True,
    )
