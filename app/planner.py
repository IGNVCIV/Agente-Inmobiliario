from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class SearchPlan:
    """Representa la configuración de búsqueda seleccionada por el planner."""
    use_sql: bool = True
    use_rag: bool = False
    use_rag_first: bool = False
    cantidad: int = 5
    fetch_uf: bool = False
    strict_matching: bool = True
    reason: str = ""


class SearchPlanner:
    """Planner adaptativo para decidir la estrategia de búsqueda de propiedades."""

    URGENT_KEYWORDS = ["urgente", "rápido", "hoy", "inmediato"]
    DISTANCE_KEYWORDS = ["cerca", "distancia", "kilómetros", "kilometros", "cuadras"]
    UF_KEYWORDS = ["uf"]

    def plan(self, query: str, criteria: Dict[str, Optional[object]]) -> SearchPlan:
        """Genera un plan de búsqueda a partir de la consulta y los criterios extraídos."""
        plan = SearchPlan()
        normalized_query = query.lower() if query else ""

        criteria_keys = [
            "presupuesto_min",
            "presupuesto_max",
            "moneda",
            "comuna",
            "dormitorios_min",
            "banos_min",
            "caracteristicas_adicionales",
        ]
        non_none_fields = [key for key in criteria_keys if criteria.get(key) is not None]

        if self._contains_any(normalized_query, self.URGENT_KEYWORDS):
            plan.cantidad = 10
            plan.use_rag = False
            plan.use_rag_first = False
            plan.reason = "búsqueda urgente"

        if len(non_none_fields) >= 2:
            plan.use_sql = True
            plan.use_rag = False
            plan.use_rag_first = False
            plan.strict_matching = True
            plan.reason = self._append_reason(
                plan.reason,
                f"criterios específicos detectados: {non_none_fields}",
            )

        if len(non_none_fields) <= 1:
            plan.use_rag_first = True
            plan.use_sql = True
            plan.use_rag = True
            plan.strict_matching = False
            plan.reason = self._append_reason(
                plan.reason,
                "consulta descriptiva, priorizando RAG semántico",
            )

        if self._should_fetch_uf(normalized_query, criteria):
            plan.fetch_uf = True
            plan.reason = self._append_reason(plan.reason, "fetching valor UF actual")

        presupuesto_max = criteria.get("presupuesto_max")
        if isinstance(presupuesto_max, (int, float)) and presupuesto_max < 3000:
            plan.cantidad = max(plan.cantidad, 10)
            plan.reason = self._append_reason(
                plan.reason,
                "presupuesto acotado, ampliando resultados",
            )

        if self._contains_any(normalized_query, self.DISTANCE_KEYWORDS):
            plan.reason = self._append_reason(plan.reason, "considerar calcular distancias")

        return plan

    def explain(self, plan: SearchPlan) -> str:
        """Retorna una explicación legible de las decisiones tomadas en el plan."""
        reason = plan.reason.strip()
        if not reason:
            reason = "Decisiones por defecto sin reglas específicas aplicadas."

        flags: List[str] = []
        flags.append(f"use_sql={plan.use_sql}")
        flags.append(f"use_rag={plan.use_rag}")
        flags.append(f"use_rag_first={plan.use_rag_first}")
        flags.append(f"cantidad={plan.cantidad}")
        flags.append(f"fetch_uf={plan.fetch_uf}")
        flags.append(f"strict_matching={plan.strict_matching}")

        return f"{reason}. Estrategia: {', '.join(flags)}."

    def _should_fetch_uf(self, query: str, criteria: Dict[str, Optional[object]]) -> bool:
        """Determina si se debe obtener el valor UF actual."""
        if criteria.get("moneda") and str(criteria.get("moneda")).strip().upper() == "UF":
            return True
        if any(keyword in query for keyword in self.UF_KEYWORDS):
            return True
        return False

    @staticmethod
    def _contains_any(text: str, keywords: List[str]) -> bool:
        """Verifica si el texto contiene cualquiera de las palabras clave dadas."""
        return any(keyword in text for keyword in keywords)

    @staticmethod
    def _append_reason(current: str, addition: str) -> str:
        """Concatena frases de razón sin duplicar texto innecesario."""
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
            "Quiero un inmueble económico en Vitacura",
            {
                "presupuesto_min": None,
                "presupuesto_max": 2800,
                "moneda": "UF",
                "comuna": "Vitacura",
                "dormitorios_min": None,
                "banos_min": None,
                "caracteristicas_adicionales": None,
            },
        ),
    ]

    for query, criteria in examples:
        plan = planner.plan(query, criteria)
        print("Consulta:", query)
        print("Plan:", plan)
        print("Explicación:", planner.explain(plan))
        print("---")
