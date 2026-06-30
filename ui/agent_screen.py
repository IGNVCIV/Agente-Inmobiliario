"""Vista conversacional del agente inmobiliario.

Esta versión evita depender del chat nativo de Streamlit para el historial,
porque en algunos temas el contraste del texto se vuelve ilegible. Mantiene una
experiencia conversacional, pero con burbujas propias y formulario estable.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from ui.components import card, empty_state, html_table, message_bubble, page_header, section_title


DEFAULT_AMENITIES = [
    "Piscina",
    "Gimnasio",
    "Terraza",
    "Estacionamiento",
    "Bodega",
    "Quincho",
    "Jardín",
    "Seguridad",
]

SUGGESTION_PROMPTS = {
    "Providencia · 2D bajo 7.000 UF": "Busco departamentos de 2 dormitorios en Providencia bajo 7.000 UF.",
    "Las Condes · terraza y bodega": "Muéstrame propiedades en Las Condes con terraza, estacionamiento y bodega.",
    "Vitacura · opciones 3D": "Quiero comparar propiedades de 3 dormitorios en Vitacura.",
    "Más económicas disponibles": "Muéstrame las alternativas más económicas disponibles en la base de datos.",
}


@st.cache_resource(show_spinner=False)
def load_agent(project_root_text: str) -> Any:
    """Carga el agente una vez por sesión de Streamlit."""
    root = Path(project_root_text)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from app.main import RealEstateAgent

    return RealEstateAgent()


@st.cache_data(show_spinner=False)
def load_property_catalog(project_root_text: str) -> dict[str, Any]:
    """Lee el CSV procesado para poblar filtros y sugerencias con datos reales."""
    root = Path(project_root_text)
    path = root / "data" / "processed" / "propiedades_detalle.csv"
    if not path.exists():
        return {
            "comunas": ["Las Condes", "Providencia", "Vitacura"],
            "dormitorios": [1, 2, 3, 4],
            "precio_min": 0,
            "precio_max": 30000,
            "amenities": DEFAULT_AMENITIES,
            "rows": pd.DataFrame(),
        }

    df = pd.read_csv(path)

    comunas: list[str] = []
    if "comuna" in df.columns:
        comunas = sorted(value for value in df["comuna"].dropna().astype(str).str.strip().unique().tolist() if value)

    dormitorios: list[int] = []
    if "dormitorios" in df.columns:
        dormitorios = sorted(
            int(value)
            for value in pd.to_numeric(df["dormitorios"], errors="coerce").dropna().unique().tolist()
            if int(value) > 0
        )

    price_series = pd.Series(dtype="float64")
    if "precio_valor" in df.columns:
        price_series = pd.to_numeric(df["precio_valor"], errors="coerce").dropna()
    elif "precio_uf" in df.columns:
        price_series = pd.to_numeric(df["precio_uf"], errors="coerce").dropna()

    amenities_set: set[str] = set()
    if "amenities" in df.columns:
        for value in df["amenities"].dropna().astype(str):
            for item in value.split(","):
                cleaned = item.strip().capitalize()
                if cleaned:
                    amenities_set.add(cleaned)

    return {
        "comunas": comunas or ["Las Condes", "Providencia", "Vitacura"],
        "dormitorios": dormitorios or [1, 2, 3, 4],
        "precio_min": int(price_series.min()) if not price_series.empty else 0,
        "precio_max": int(price_series.max()) if not price_series.empty else 30000,
        "amenities": sorted(amenities_set) if amenities_set else DEFAULT_AMENITIES,
        "rows": df,
    }


def init_chat_state() -> None:
    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = [
            {
                "role": "assistant",
                "content": (
                    "Hola. Puedo ayudarte a buscar propiedades reales desde la base local. "
                    "Para partir, dime comuna, presupuesto, dormitorios o características importantes."
                ),
            }
        ]
    if "pending_agent_prompt" not in st.session_state:
        st.session_state["pending_agent_prompt"] = None


def set_pending_prompt(prompt: str) -> None:
    st.session_state["pending_agent_prompt"] = prompt
    st.rerun()


def build_suggestions(catalog: dict[str, Any]) -> list[str]:
    """Mantiene 4 sugerencias alineadas con la base actual."""
    comunas = set(catalog.get("comunas") or [])
    suggestions: list[str] = []
    if "Providencia" in comunas:
        suggestions.append("Providencia · 2D bajo 7.000 UF")
    if "Las Condes" in comunas:
        suggestions.append("Las Condes · terraza y bodega")
    if "Vitacura" in comunas:
        suggestions.append("Vitacura · opciones 3D")
    suggestions.append("Más económicas disponibles")

    for fallback in SUGGESTION_PROMPTS:
        if fallback not in suggestions:
            suggestions.append(fallback)
    return suggestions[:4]


def render_suggestions(project_root: Path) -> None:
    catalog = load_property_catalog(str(project_root))
    suggestions = build_suggestions(catalog)
    section_title("Acciones sugeridas", "Consultas rápidas basadas en las comunas disponibles de la base actual.")
    st.markdown('<div class="suggestion-anchor"></div>', unsafe_allow_html=True)
    cols = st.columns(4, gap="medium")
    for index, suggestion in enumerate(suggestions):
        with cols[index]:
            if st.button(suggestion, key=f"suggestion_{index}", use_container_width=True):
                set_pending_prompt(SUGGESTION_PROMPTS.get(suggestion, suggestion))


def render_filters(project_root: Path) -> str:
    """Renderiza filtros visibles y retorna un resumen para anexar al prompt."""
    catalog = load_property_catalog(str(project_root))
    comunas = ["Todas", *catalog["comunas"]]
    dormitorios_options = ["Cualquiera", *[str(value) for value in catalog["dormitorios"]]]
    amenities_options = catalog.get("amenities") or DEFAULT_AMENITIES
    max_price = max(int(catalog.get("precio_max") or 30000), 1000)

    st.markdown(
        """
        <div class="filter-panel">
            <div class="filter-title-row">
                <div>
                    <div class="section-title" style="margin-bottom:2px;">Filtros rápidos</div>
                    <div class="body-copy">Opcionales. Se agregan a la consulta sin reemplazar lo que escribes.</div>
                </div>
                <span class="badge badge-blue">Dataset local</span>
            </div>
        """,
        unsafe_allow_html=True,
    )

    col_a, col_b, col_c, col_d = st.columns([1.2, 0.9, 0.8, 0.9], gap="medium")
    with col_a:
        comuna = st.selectbox("Comuna", comunas, index=0, key="filter_comuna")
    with col_b:
        presupuesto = st.number_input(
            "Máx. UF",
            min_value=0,
            max_value=max_price + 5000,
            value=0,
            step=500,
            key="filter_uf",
            help="Déjalo en 0 si no quieres aplicar tope de presupuesto.",
        )
    with col_c:
        dormitorios = st.selectbox("Dormitorios", dormitorios_options, index=0, key="filter_dorms")
    with col_d:
        tipo = st.selectbox("Tipo", ["Cualquiera", "Departamento", "Casa"], index=0, key="filter_tipo")

    amenities = st.multiselect(
        "Características",
        amenities_options,
        placeholder="Selecciona características disponibles en la base",
        key="filter_amenities",
    )
    st.markdown("</div>", unsafe_allow_html=True)

    parts: list[str] = []
    if comuna and comuna != "Todas":
        parts.append(f"comuna {comuna}")
    if presupuesto:
        parts.append(f"presupuesto máximo {int(presupuesto)} UF")
    if dormitorios and dormitorios != "Cualquiera":
        parts.append(f"mínimo {dormitorios} dormitorios")
    if tipo and tipo != "Cualquiera":
        parts.append(f"tipo {tipo.lower()}")
    if amenities:
        parts.append("características: " + ", ".join(amenities))
    return "; ".join(parts)


def render_chat_history() -> None:
    st.markdown('<div class="chat-panel">', unsafe_allow_html=True)
    for message in st.session_state["chat_messages"]:
        message_bubble(message.get("role", "assistant"), message.get("content", ""))
    st.markdown("</div>", unsafe_allow_html=True)


def ask_agent(project_root: Path, prompt: str) -> str:
    with st.status("Procesando búsqueda local", expanded=False) as status:
        agent = load_agent(str(project_root))
        response = agent.respond(prompt.strip())
        status.update(label="Respuesta generada", state="complete", expanded=False)
    return str(response)


def render_input_form(default_prompt: str | None = None) -> str | None:
    st.markdown('<div class="chat-form-card">', unsafe_allow_html=True)
    with st.form("agent_query_form", clear_on_submit=True):
        query = st.text_area(
            "Consulta inmobiliaria",
            value=default_prompt or "",
            placeholder="Ej. Busco un departamento de 2 dormitorios en Providencia bajo 7.000 UF",
            height=92,
            label_visibility="collapsed",
        )
        submit_col, clear_col = st.columns([0.78, 0.22])
        with submit_col:
            submitted = st.form_submit_button("Consultar agente", type="primary", use_container_width=True)
        with clear_col:
            clear_clicked = st.form_submit_button("Limpiar", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if clear_clicked:
        st.session_state.pop("pending_agent_prompt", None)
        return "__CLEAR_INPUT__"
    if submitted:
        return query.strip()
    return None


def render_dataset_preview(project_root: Path) -> None:
    catalog = load_property_catalog(str(project_root))
    df = catalog.get("rows")
    if not isinstance(df, pd.DataFrame) or df.empty:
        return
    cols = [col for col in ["comuna", "precio_valor", "dormitorios", "banos", "amenities"] if col in df.columns]
    if not cols:
        return
    with st.expander("Ver muestra de propiedades disponibles", expanded=False):
        html_table(df[cols].head(5), max_rows=5, max_chars=70)


def render_agent_screen(project_root: Path | None = None) -> None:
    resolved_root = project_root or Path(__file__).resolve().parents[1]
    init_chat_state()

    page_header(
        "AI Agent · Conversational search",
        "Asistente inmobiliario",
        "Busca propiedades con lenguaje natural, filtros claros y respuestas basadas en datos recuperados desde SQLite/RAG.",
    )

    left, right = st.columns([0.70, 0.30], gap="large")

    with left:
        render_suggestions(resolved_root)
        filter_context = render_filters(resolved_root)
        render_chat_history()

        pending = st.session_state.pop("pending_agent_prompt", None)
        user_prompt = render_input_form(pending)

        if user_prompt == "__CLEAR_INPUT__":
            st.rerun()

        if user_prompt:
            final_prompt = user_prompt
            if filter_context:
                final_prompt = f"{user_prompt}\n\nFiltros seleccionados: {filter_context}"

            st.session_state["chat_messages"].append({"role": "user", "content": user_prompt})
            try:
                answer = ask_agent(resolved_root, final_prompt)
            except Exception as exc:
                answer = (
                    "No fue posible consultar al agente en este momento.\n\n"
                    f"Detalle técnico: {exc}\n\n"
                    "Revisa que Docker/Ollama esté activo y que las dependencias del proyecto estén instaladas."
                )
            st.session_state["chat_messages"].append({"role": "assistant", "content": answer})
            st.rerun()

    with right:
        section_title("Panel de trabajo")
        card(
            "Modo local",
            "La generación usa Ollama local como proveedor principal. Permite conversaciones más largas sin costo de API externo.",
            badge="Ollama",
            badge_kind="success",
        )
        card(
            "Datos disponibles",
            "La base actual contiene propiedades en Las Condes, Providencia y Vitacura. Las sugerencias evitan comunas fuera del dataset.",
            badge="Dataset",
            badge_kind="blue",
        )
        card(
            "Uso responsable",
            "El agente debe basarse en propiedades recuperadas. Si no hay resultados, corresponde decirlo y no inventar alternativas.",
            badge="Auditable",
            badge_kind="warning",
        )

        if st.button("Limpiar conversación", use_container_width=True):
            st.session_state.pop("chat_messages", None)
            st.session_state.pop("pending_agent_prompt", None)
            st.rerun()

        if len(st.session_state["chat_messages"]) <= 1:
            empty_state("Sin búsquedas todavía", "Usa una sugerencia o escribe tu primera consulta para comenzar.")

        render_dataset_preview(resolved_root)
