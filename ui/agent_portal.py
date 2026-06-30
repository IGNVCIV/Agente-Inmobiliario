"""Portal principal Streamlit del Agente Inmobiliario IA.

Entrada recomendada desde la raíz del proyecto:
    python -m streamlit run ui/agent_portal.py

La pantalla inicial es Home. Además del sidebar, cada pantalla tiene navegación
superior para que el usuario pueda moverse aunque cierre la barra lateral.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ui.agent_screen import render_agent_screen
from ui.components import action_card, card, hero, html_table, metric_row, nav_brand, page_header, section_spacer, section_title
from ui.data_access import (
    compact_log_table,
    compute_summary,
    fmt_int,
    fmt_ms,
    fmt_pct,
    fmt_usd,
    load_observability_bundle,
)
from ui.observability_dashboard import render_traceability_screen
from ui.styles import apply_theme


SCREENS = {
    "home": "Inicio",
    "agent": "Agente IA",
    "dashboard": "Dashboard",
    "traceability": "Trazabilidad",
}


st.set_page_config(
    page_title="Real Estate Agente IA",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)


def set_screen(screen: str) -> None:
    st.session_state["active_screen"] = screen


def active_screen() -> str:
    return st.session_state.get("active_screen", "home")


def route_to(screen: str) -> None:
    set_screen(screen)
    st.rerun()


def render_top_nav() -> None:
    """Navegación superior estable y con apariencia de sección productiva."""
    current = active_screen()

    with st.container(border=True):
        st.markdown("**NAVEGACIÓN PRINCIPAL**")
        cols = st.columns(4, gap="small")
        for col, (key, label) in zip(cols, SCREENS.items()):
            with col:
                button_type = "primary" if key == current else "secondary"
                if st.button(label, key=f"top_nav_{key}_{current}", type=button_type, use_container_width=True):
                    route_to(key)

    st.markdown('<div class="top-nav-spacer"></div>', unsafe_allow_html=True)


def render_sidebar() -> None:
    with st.sidebar:
        nav_brand()
        st.divider()

        current = active_screen()
        selected_label = st.radio(
            "Navegación",
            options=list(SCREENS.keys()),
            format_func=lambda key: SCREENS[key],
            index=list(SCREENS.keys()).index(current) if current in SCREENS else 0,
            label_visibility="collapsed",
        )
        if selected_label != current:
            route_to(selected_label)

        st.divider()
        st.caption("Inicio del sistema")
        st.code("python -m streamlit run ui/agent_portal.py", language="powershell")

        st.divider()
        st.caption("Estado")
        st.success("Proveedor principal: Ollama local")
        st.caption("Interfaz local de evaluación y auditoría.")


def render_home() -> None:
    hero(
        title="Centro operativo inmobiliario con IA",
        description=(
            "Una interfaz única para conversar con el agente, revisar indicadores ejecutivos "
            "y auditar cada ejecución. El flujo principal comienza aquí."
        ),
        kicker="Inicio · Punto de entrada",
    )

    section_title("¿Qué quieres hacer?", "Elige una vista para operar, monitorear o auditar el agente.")
    col_agent, col_dash, col_trace = st.columns(3, gap="medium")

    with col_agent:
        action_card(
            "Conversar con el agente",
            "Buscar propiedades con lenguaje natural, filtros compactos y seguimiento conversacional.",
        )
        if st.button("Abrir agente IA", type="primary", use_container_width=True):
            route_to("agent")

    with col_dash:
        action_card(
            "Revisar dashboard",
            "Ver KPIs, actividad reciente, costos simulados y resumen operativo del sistema.",
        )
        if st.button("Abrir dashboard", use_container_width=True):
            route_to("dashboard")

    with col_trace:
        action_card(
            "Auditar trazabilidad",
            "Inspeccionar ejecuciones, tool calls, logs, estados y proceso de búsqueda.",
        )
        if st.button("Abrir trazabilidad", use_container_width=True):
            route_to("traceability")

    section_spacer(18)
    bundle = load_observability_bundle(PROJECT_ROOT)
    summary = compute_summary(bundle["db_df"], bundle["eval_df"], bundle["summary"])

    section_title("Resumen ejecutivo", "Indicadores principales para entender el estado del agente.")
    metric_row(
        [
            ("Ejecuciones", fmt_int(summary["executions"]), None),
            ("Latencia promedio", fmt_ms(summary["latency_avg"]), None),
            ("Errores", fmt_int(summary["errors"]), None),
            ("Costo API real", fmt_usd(summary["actual_cost"]), "Ollama local"),
        ],
        columns=4,
    )

    left, right = st.columns([1.18, 0.82], gap="large")
    with left:
        section_title("Actividad reciente")
        table = compact_log_table(bundle["db_df"], limit=6)
        if table.empty:
            st.info("Aún no hay ejecuciones registradas en observability_log.")
        else:
            html_table(table, max_rows=6, max_chars=80)

    with right:
        section_title("Notas operativas")
        card(
            "Proveedor local activo",
            "Ollama local se considera el proveedor principal. El costo de API externo es 0 USD; la comparación OpenAI es simulación referencial.",
            badge="Local first",
            badge_kind="success",
        )
        card(
            "Validación humana",
            "Las recomendaciones inmobiliarias deben revisarse antes de tomar decisiones reales de inversión, arriendo o compra.",
            badge="Responsible AI",
            badge_kind="warning",
        )


def render_dashboard() -> None:
    page_header(
        "Dashboard · Vista ejecutiva",
        "Indicadores ejecutivos del agente",
        "Vista compacta para revisar estado operativo, costos referenciales, calidad y actividad reciente.",
    )

    bundle = load_observability_bundle(PROJECT_ROOT)
    db_df = bundle["db_df"]
    eval_df = bundle["eval_df"]
    summary = compute_summary(db_df, eval_df, bundle["summary"])

    metric_row(
        [
            ("Ejecuciones", fmt_int(summary["executions"]), None),
            ("Latencia promedio", fmt_ms(summary["latency_avg"]), None),
            ("Latencia p95", fmt_ms(summary["latency_p95"]), None),
            ("Errores", fmt_int(summary["errors"]), None),
            ("Precisión", fmt_pct(summary["precision"]), None),
            ("Consistencia", fmt_pct(summary["consistency"]), None),
            ("Tokens", fmt_int(summary["tokens"]), None),
            ("Costo simulado", fmt_usd(summary["sim_cost"]), None),
        ],
        columns=4,
    )

    section_spacer(18)
    left, right = st.columns([1.25, 0.75], gap="large")

    with left:
        section_title("Actividad reciente", "Últimas ejecuciones registradas por el agente.")
        table = compact_log_table(db_df, limit=10)
        if table.empty:
            st.info("No hay logs disponibles todavía.")
        else:
            html_table(table, max_rows=10, max_chars=90)

    with right:
        section_title("Resumen de propiedades")
        property_path = PROJECT_ROOT / "data" / "processed" / "propiedades_detalle.csv"
        if property_path.exists():
            df = pd.read_csv(property_path)
            comuna_count = df["comuna"].nunique() if "comuna" in df.columns else "N/D"
            property_metrics = [
                ("Propiedades indexables", fmt_int(len(df)), None),
                ("Comunas", fmt_int(comuna_count) if isinstance(comuna_count, int) else "N/D", None),
            ]
            price_col = "precio_valor" if "precio_valor" in df.columns else "precio_uf" if "precio_uf" in df.columns else None
            if price_col:
                price = pd.to_numeric(df[price_col], errors="coerce").dropna()
                property_metrics.append(("Precio UF promedio", fmt_int(price.mean()) if not price.empty else "N/D", None))
            metric_row(property_metrics, columns=1)
        else:
            st.info("No se encontró data/processed/propiedades_detalle.csv.")

        section_title("Acciones rápidas")
        if st.button("Nueva búsqueda", type="primary", use_container_width=True):
            route_to("agent")
        if st.button("Ver trazabilidad", use_container_width=True):
            route_to("traceability")
        if st.button("Actualizar datos", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    if bundle["errors"]:
        with st.expander("Fuentes con advertencias", expanded=False):
            for error in bundle["errors"]:
                st.warning(error)


def main() -> None:
    apply_theme()
    render_sidebar()
    render_top_nav()

    screen = active_screen()
    if screen == "home":
        render_home()
    elif screen == "agent":
        render_agent_screen(PROJECT_ROOT)
    elif screen == "dashboard":
        render_dashboard()
    elif screen == "traceability":
        render_traceability_screen(PROJECT_ROOT)
    else:
        set_screen("home")
        st.rerun()


if __name__ == "__main__":
    main()
