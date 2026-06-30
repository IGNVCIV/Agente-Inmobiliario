from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SearchPlan:
    """Configuración de búsqueda seleccionada por el planner."""

    use_sql: bool = True
    use_rag: bool = False
    use_rag_first: bool = False
    cantidad: int = 5
    fetch_uf: bool = False
    strict_matching: bool = True
    reason: str = ""

    # Campos adicionales para un agente más conversacional.
    intent: str = "busqueda"
    response_style: str = "asesor_conversacional"
    use_memory_context: bool = False
    allow_relaxed_fallback: bool = True
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    rag_fetch_k: int = 20
    max_properties_to_show: int = 3
    ranking_strategy: str = "balanced"
    ranking_weights: Dict[str, float] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)


class SearchPlanner:
    """
    Planner adaptativo para decidir cómo buscar propiedades.

    La lógica asume un LLM local mediante Ollama, por lo que puede permitirse
    una respuesta más rica y con más contexto sin preocuparse por costo de API.
    Aun así, mantiene SQL para filtros duros y RAG para interpretación semántica.
    """

    URGENT_KEYWORDS = ["urgente", "rápido", "rapido", "hoy", "inmediato", "lo antes posible"]
    DISTANCE_KEYWORDS = ["cerca", "distancia", "kilómetros", "kilometros", "cuadras", "metro"]
    UF_KEYWORDS = ["uf", "unidad de fomento"]
    CLP_KEYWORDS = ["clp", "pesos", "$", "millones"]
    FOLLOWUP_KEYWORDS = [
        "también", "tambien", "además", "ademas", "ahora", "ese", "esa", "esos", "esas",
        "parecido", "similar", "otra opción", "otra opcion", "más barato", "mas barato",
        "más grande", "mas grande", "con piscina", "sin piscina", "cerca del metro",
    ]
    COMPARISON_KEYWORDS = ["comparar", "conviene", "mejor opción", "mejor opcion", "cuál es mejor", "cual es mejor"]
    FAVORITE_KEYWORDS = ["favorito", "favorita", "guardar", "guardadas", "lista de favoritos"]
    NEGOTIATION_KEYWORDS = ["negociar", "oferta", "rebaja", "descuento"]

    HARD_CRITERIA = [
        "presupuesto_min",
        "presupuesto_max",
        "moneda",
        "comuna",
        "dormitorios_min",
        "banos_min",
    ]
    SOFT_CRITERIA = ["caracteristicas_adicionales", "tipo_propiedad", "tipo_operacion"]

    def plan(
        self,
        query: str,
        criteria: Dict[str, Optional[object]],
        memory_context: str | None = None,
        preferences: Dict[str, Any] | None = None,
    ) -> SearchPlan:
        """Genera un plan de búsqueda a partir de consulta, criterios y memoria."""
        normalized_query = self._normalize(query)
        criteria = criteria or {}
        preferences = preferences or {}

        plan = SearchPlan()
        hard_fields = self._present_fields(criteria, self.HARD_CRITERIA)
        soft_fields = self._present_fields(criteria, self.SOFT_CRITERIA)
        total_fields = hard_fields + soft_fields

        plan.intent = self._detect_intent(normalized_query)
        plan.use_memory_context = bool(memory_context) or self._contains_any(normalized_query, self.FOLLOWUP_KEYWORDS)

        # Base: con Ollama local conviene usar SQL + RAG de forma complementaria.
        plan.use_sql = True
        plan.use_rag = True
        plan.use_rag_first = False
        plan.strict_matching = True
        plan.rag_fetch_k = 20
        plan.max_properties_to_show = 3
        plan.response_style = "asesor_conversacional"
        plan.ranking_strategy = "balanced"
        plan.ranking_weights = {
            "hard_criteria": 0.45,
            "semantic_match": 0.30,
            "price_fit": 0.15,
            "amenities": 0.10,
        }
        plan.reason = "estrategia híbrida local: SQL para filtros duros y RAG para matices semánticos"

        # Consultas vagas o descriptivas: RAG primero para entender intención.
        if len(total_fields) <= 1 or self._is_descriptive_query(normalized_query):
            plan.use_rag_first = True
            plan.strict_matching = False
            plan.cantidad = 7
            plan.rag_fetch_k = 30
            plan.ranking_strategy = "semantic_first"
            plan.ranking_weights.update({"semantic_match": 0.45, "hard_criteria": 0.25})
            plan.reason = self._append_reason(plan.reason, "consulta descriptiva; se prioriza RAG")

        # Consultas específicas: SQL primero, pero RAG queda activo para reranking/respuesta.
        if len(hard_fields) >= 2:
            plan.use_rag_first = False
            plan.strict_matching = True
            plan.cantidad = 5
            plan.rag_fetch_k = 15
            plan.ranking_strategy = "sql_then_rag_rerank"
            plan.reason = self._append_reason(plan.reason, f"criterios duros detectados: {hard_fields}")

        # Follow-up: usar memoria y relajar lo suficiente para que entienda cambios incrementales.
        if plan.use_memory_context:
            plan.use_rag = True
            plan.use_rag_first = True
            plan.strict_matching = False if len(hard_fields) < 3 else plan.strict_matching
            plan.cantidad = max(plan.cantidad, 6)
            plan.rag_fetch_k = max(plan.rag_fetch_k, 25)
            plan.ranking_strategy = "memory_aware"
            plan.reason = self._append_reason(plan.reason, "consulta de seguimiento con memoria conversacional")

        # Urgencia: más resultados, menos conversación y respuesta accionable.
        if self._contains_any(normalized_query, self.URGENT_KEYWORDS):
            plan.cantidad = max(plan.cantidad, 10)
            plan.max_properties_to_show = 5
            plan.response_style = "directo_accionable"
            plan.reason = self._append_reason(plan.reason, "búsqueda urgente; se amplía cantidad de resultados")

        # Comparaciones: menos propiedades, más explicación de trade-offs.
        if self._contains_any(normalized_query, self.COMPARISON_KEYWORDS):
            plan.intent = "comparacion"
            plan.cantidad = min(max(plan.cantidad, 3), 5)
            plan.max_properties_to_show = 3
            plan.response_style = "comparativo"
            plan.ranking_strategy = "tradeoff_comparison"
            plan.reason = self._append_reason(plan.reason, "el usuario pide comparación entre alternativas")

        # Favoritos: probablemente se resuelve con herramienta de favoritos.
        if self._contains_any(normalized_query, self.FAVORITE_KEYWORDS):
            plan.intent = "favoritos"
            plan.response_style = "gestion_favoritos"
            plan.reason = self._append_reason(plan.reason, "intención relacionada con favoritos")

        # UF y presupuesto: obtener UF si hay que interpretar UF/CLP.
        if self._should_fetch_uf(normalized_query, criteria):
            plan.fetch_uf = True
            plan.reason = self._append_reason(plan.reason, "requiere referencia de UF")

        presupuesto_max = criteria.get("presupuesto_max") or preferences.get("precio_maximo_uf")
        if isinstance(presupuesto_max, (int, float)):
            if presupuesto_max < 3000:
                plan.cantidad = max(plan.cantidad, 10)
                plan.allow_relaxed_fallback = True
                plan.reason = self._append_reason(
                    plan.reason,
                    "presupuesto acotado; se amplía búsqueda sin romper el máximo indicado",
                )
            elif presupuesto_max >= 7000:
                plan.ranking_weights.update({"amenities": 0.18, "semantic_match": 0.34})
                plan.reason = self._append_reason(plan.reason, "presupuesto alto; se valoran atributos diferenciales")

        if self._contains_any(normalized_query, self.DISTANCE_KEYWORDS):
            plan.ranking_weights.update({"location_fit": 0.20})
            plan.notes.append("considerar cercanía declarada en texto; calcular distancia solo si hay coordenadas")
            plan.reason = self._append_reason(plan.reason, "criterio de cercanía detectado")

        if self._contains_any(normalized_query, self.NEGOTIATION_KEYWORDS):
            plan.response_style = "asesor_negociacion"
            plan.notes.append("recordar que recomendaciones de negociación requieren validación humana")
            plan.reason = self._append_reason(plan.reason, "consulta con posible recomendación inmobiliaria")

        # Clarificación solo cuando casi no hay intención útil. No bloquea la búsqueda.
        if self._needs_clarification(normalized_query, criteria, preferences):
            plan.needs_clarification = True
            plan.clarification_question = (
                "¿Prefieres que priorice comuna, presupuesto máximo o número de dormitorios?"
            )
            plan.strict_matching = False
            plan.use_rag_first = True
            plan.reason = self._append_reason(plan.reason, "faltan criterios clave; conviene pedir precisión si la respuesta queda débil")

        return plan

    def explain(self, plan: SearchPlan) -> str:
        """Retorna una explicación legible de las decisiones tomadas en el plan."""
        reason = plan.reason.strip() or "Decisiones por defecto sin reglas específicas aplicadas"

        flags: List[str] = [
            f"intent={plan.intent}",
            f"use_sql={plan.use_sql}",
            f"use_rag={plan.use_rag}",
            f"use_rag_first={plan.use_rag_first}",
            f"cantidad={plan.cantidad}",
            f"fetch_uf={plan.fetch_uf}",
            f"strict_matching={plan.strict_matching}",
            f"ranking_strategy={plan.ranking_strategy}",
            f"response_style={plan.response_style}",
        ]

        if plan.needs_clarification and plan.clarification_question:
            flags.append(f"clarification='{plan.clarification_question}'")

        return f"{reason}. Estrategia: {', '.join(flags)}."

    def _detect_intent(self, query: str) -> str:
        if self._contains_any(query, self.FAVORITE_KEYWORDS):
            return "favoritos"
        if self._contains_any(query, self.COMPARISON_KEYWORDS):
            return "comparacion"
        if self._contains_any(query, self.FOLLOWUP_KEYWORDS):
            return "seguimiento"
        if any(term in query for term in ["busco", "quiero", "necesito", "tienes", "encuentra"]):
            return "busqueda"
        return "busqueda"

    def _should_fetch_uf(self, query: str, criteria: Dict[str, Optional[object]]) -> bool:
        moneda = criteria.get("moneda")
        if moneda and str(moneda).strip().upper() in {"UF", "CLP", "PESOS"}:
            return True
        if self._contains_any(query, self.UF_KEYWORDS + self.CLP_KEYWORDS):
            return True
        return False

    def _is_descriptive_query(self, query: str) -> bool:
        descriptive_terms = [
            "lindo", "bonito", "moderno", "tranquilo", "seguro", "familiar", "luminoso",
            "vista", "cerca", "metro", "universidad", "colegio", "parque", "inversión", "inversion",
            "buena conectividad", "plusvalía", "plusvalia", "económico", "economico",
        ]
        return self._contains_any(query, descriptive_terms)

    def _needs_clarification(
        self,
        query: str,
        criteria: Dict[str, Optional[object]],
        preferences: Dict[str, Any],
    ) -> bool:
        if not query or len(query.split()) <= 2:
            return True

        has_location = bool(criteria.get("comuna") or preferences.get("comunas"))
        has_budget = bool(criteria.get("presupuesto_max") or preferences.get("precio_maximo_uf"))
        has_size = bool(criteria.get("dormitorios_min") or preferences.get("dormitorios"))
        has_soft = bool(criteria.get("caracteristicas_adicionales") or preferences.get("amenities"))

        return not any([has_location, has_budget, has_size, has_soft]) and len(query.split()) < 6

    @staticmethod
    def _present_fields(criteria: Dict[str, Optional[object]], keys: List[str]) -> List[str]:
        present = []
        for key in keys:
            value = criteria.get(key)
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            if isinstance(value, (list, tuple, set, dict)) and not value:
                continue
            present.append(key)
        return present

    @staticmethod
    def _normalize(text: str) -> str:
        return (text or "").lower().strip()

    @staticmethod
    def _contains_any(text: str, keywords: List[str]) -> bool:
        return any(keyword in text for keyword in keywords)

    @staticmethod
    def _append_reason(current: str, addition: str) -> str:
        if not current:
            return addition
        if addition in current:
            return current
        return f"{current}; {addition}"


if __name__ == "__main__":
    planner = SearchPlanner()

    examples = [
        (
            "Necesito urgente un departamento en Las Condes, 3 dormitorios, presupuesto 2500 UF",
            {
                "presupuesto_min": None,
                "presupuesto_max": 2500,
                "moneda": "UF",
                "comuna": "Las Condes",
                "dormitorios_min": 3,
                "banos_min": None,
                "caracteristicas_adicionales": None,
            },
        ),
        (
            "Busco algo cerca del metro con piscina",
            {
                "presupuesto_min": None,
                "presupuesto_max": None,
                "moneda": None,
                "comuna": None,
                "dormitorios_min": None,
                "banos_min": None,
                "caracteristicas_adicionales": "piscina",
            },
        ),
        (
            "¿Y algo parecido pero más barato y con terraza?",
            {
                "presupuesto_min": None,
                "presupuesto_max": None,
                "moneda": None,
                "comuna": None,
                "dormitorios_min": None,
                "banos_min": None,
                "caracteristicas_adicionales": "terraza",
            },
        ),
    ]

    for query, criteria in examples:
        plan = planner.plan(query, criteria, memory_context="Última búsqueda en Ñuñoa", preferences={"comunas": ["Ñuñoa"]})
        print("Consulta:", query)
        print("Plan:", plan)
        print("Explicación:", planner.explain(plan))
        print("---")
