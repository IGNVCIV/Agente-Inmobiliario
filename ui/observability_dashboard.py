"""Vista de Dashboard técnico y trazabilidad del agente.

Este módulo reemplaza el dashboard largo por una interfaz auditable y compacta:
- timeline de ejecuciones
- logs resumidos
- tool calls inferidos
- métricas de calidad/costos
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from ui.components import badge, card, empty_state, html_table, metric_row, page_header, section_title, timeline_item
from ui.data_access import (
    ERROR_COLS,
    EXECUTION_COLS,
    LATENCY_COLS,
    MODEL_COLS,
    PROVIDER_COLS,
    QUERY_COLS,
    STATUS_COLS,
    TIMESTAMP_COLS,
    compact_log_table,
    compute_summary,
    fmt_int,
    fmt_ms,
    fmt_pct,
    fmt_usd,
    get_col,
    is_success,
    latest_rows,
    load_observability_bundle,
)
from ui.styles import apply_theme


def _value(row: pd.Series, col: str | None, default: str = "N/D") -> str:
    if not col or col not in row.index:
        return default
    value = row.get(col)
    if value is None or pd.isna(value):
        return default
    text = str(value).strip()
    return text if text else default


def _status_kind(status: str) -> str:
    return "success" if is_success(status) else "error"


def _infer_tool_steps(row: pd.Series) -> list[tuple[str, str, str]]:
    """Crea una trazabilidad legible aun cuando el log no tenga tabla de tool calls."""
    query_col = next((col for col in QUERY_COLS if col in row.index), None)
    model_col = next((col for col in MODEL_COLS if col in row.index), None)
    provider_col = next((col for col in PROVIDER_COLS if col in row.index), None)

    query = _value(row, query_col, "consulta registrada")
    provider = _value(row, provider_col, "proveedor local")
    model = _value(row, model_col, "modelo no especificado")

    return [
        ("Input recibido", f"Query: {query[:140]}", "success"),
        ("Extracción de criterios", "Se interpretan comuna, presupuesto, dormitorios y preferencias conversacionales.", "success"),
        ("Búsqueda SQLite/RAG", "Se recuperan propiedades desde la base local y el índice semántico.", "success"),
        ("Generación LLM", f"Proveedor: {provider} · Modelo: {model}", "success"),
        ("Respuesta auditada", "La respuesta debe basarse en propiedades recuperadas y evitar inventar datos.", "success"),
    ]


def render_timeline(db_df: pd.DataFrame) -> None:
    section_title("Línea de tiempo de ejecuciones", "Últimas consultas registradas por el agente.")

    if db_df.empty:
        empty_state("Sin trazas disponibles", "Ejecuta una consulta desde AI Agent para generar registros de observabilidad.")
        return

    rows = latest_rows(db_df, limit=8)
    ts_col = get_col(rows, TIMESTAMP_COLS)
    query_col = get_col(rows, QUERY_COLS)
    status_col = get_col(rows, STATUS_COLS)
    latency_col = get_col(rows, LATENCY_COLS)
    exec_col = get_col(rows, EXECUTION_COLS)

    for idx, row in rows.iterrows():
        status = _value(row, status_col, "success")
        title = _value(row, exec_col, f"Ejecución {idx + 1}")
        meta = f"{_value(row, ts_col)} · {fmt_ms(row.get(latency_col)) if latency_col else 'latencia N/D'}"
        body = _value(row, query_col, "Consulta sin preview disponible")
        timeline_item(title=title, meta=meta, body=body, status="success" if is_success(status) else "error")


def render_execution_cards(db_df: pd.DataFrame) -> None:
    section_title("Detalle auditable", "Expande una ejecución para revisar pasos, logs y proceso de búsqueda.")

    if db_df.empty:
        empty_state("No hay ejecuciones para auditar", "La tabla observability_log todavía no tiene filas.")
        return

    rows = latest_rows(db_df, limit=10)
    ts_col = get_col(rows, TIMESTAMP_COLS)
    query_col = get_col(rows, QUERY_COLS)
    status_col = get_col(rows, STATUS_COLS)
    latency_col = get_col(rows, LATENCY_COLS)
    exec_col = get_col(rows, EXECUTION_COLS)
    error_col = get_col(rows, ERROR_COLS)

    for idx, row in rows.iterrows():
        status = _value(row, status_col, "success")
        kind = _status_kind(status)
        exec_id = _value(row, exec_col, f"run-{idx + 1}")
        query = _value(row, query_col, "Consulta no disponible")
        latency = fmt_ms(row.get(latency_col)) if latency_col else "N/D"

        with st.expander(f"{exec_id} · {query[:80]}", expanded=idx == rows.index[0]):
            st.markdown(
                f"{badge(status, kind)} &nbsp; {badge(latency, 'blue')} &nbsp; {badge(_value(row, ts_col), 'blue')}",
                unsafe_allow_html=True,
            )
            if error_col and not is_success(row.get(error_col)):
                st.error(_value(row, error_col))

            st.markdown("#### Pasos del agente y proceso")
            for label, detail, step_status in _infer_tool_steps(row):
                with st.status(label, state="complete" if step_status == "success" else "error", expanded=False):
                    st.write(detail)

            st.markdown("#### Registro original")
            html_table(row.to_frame("valor").reset_index().rename(columns={"index": "campo"}), max_rows=80, max_chars=120)


def render_logs_table(db_df: pd.DataFrame, eval_df: pd.DataFrame) -> None:
    section_title("Registros de ejecución")
    if not db_df.empty:
        html_table(compact_log_table(db_df, limit=30), max_rows=30, max_chars=100)
    elif not eval_df.empty:
        st.info("No hay observability_log. Se muestran resultados de evaluación.")
        html_table(eval_df.tail(30).iloc[::-1], max_rows=30, max_chars=100)
    else:
        empty_state("Sin logs", "No se encontraron fuentes de observabilidad ni evaluación.")


def render_quality_tab(eval_df: pd.DataFrame, summary: dict[str, Any]) -> None:
    section_title("Calidad y evaluación")
    if eval_df.empty and not summary:
        empty_state("Sin evaluación controlada", "Agrega eval_results.csv o eval_summary.json para visualizar calidad.")
        return

    if summary:
        st.json(summary)

    if not eval_df.empty:
        html_table(eval_df, max_rows=30, max_chars=100)


def render_traceability_screen(project_root: Path | None = None) -> None:
    root = project_root or Path(__file__).resolve().parents[1]
    page_header(
        "Trazabilidad del agente · Auditoría",
        "Trazabilidad del agente",
        "Línea de tiempo, registros, pasos inferidos y estado de ejecución para revisar cómo el agente procesó cada búsqueda.",
    )

    bundle = load_observability_bundle(root)
    db_df = bundle["db_df"]
    eval_df = bundle["eval_df"]
    summary = compute_summary(db_df, eval_df, bundle["summary"])

    metric_row(
        [
            ("Ejecuciones", fmt_int(summary["executions"]), None),
            ("Latencia promedio", fmt_ms(summary["latency_avg"]), None),
            ("Errores", fmt_int(summary["errors"]), None),
            ("Proveedor", str(summary["provider"]), None),
            ("Modelo", str(summary["model"]), None),
            ("Costo real API", fmt_usd(summary["actual_cost"]), "Ollama local"),
            ("Costo simulado", fmt_usd(summary["sim_cost"]), None),
            ("Precisión", fmt_pct(summary["precision"]), None),
        ],
        columns=4,
    )

    if bundle["errors"]:
        with st.expander("Estado de fuentes", expanded=False):
            for error in bundle["errors"]:
                st.warning(error)
            st.write(bundle["paths"])

    st.divider()
    tab_timeline, tab_detail, tab_logs, tab_quality = st.tabs(
        ["Línea de tiempo", "Proceso", "Registros", "Calidad"]
    )

    with tab_timeline:
        render_timeline(db_df)

    with tab_detail:
        render_execution_cards(db_df)

    with tab_logs:
        render_logs_table(db_df, eval_df)

    with tab_quality:
        render_quality_tab(eval_df, bundle["summary"])


def main() -> None:
    st.set_page_config(page_title="Trazabilidad | Agente inmobiliario IA", page_icon="📊", layout="wide")
    apply_theme()
    render_traceability_screen()


if __name__ == "__main__":
    main()
