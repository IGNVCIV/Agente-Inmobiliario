import json
import logging
import os
import sys

# Evita que CrewAI solicite confirmación interactiva de trazas durante demos.
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from crewai import Agent, Crew, Task
from crewai.tools import tool
from .planner import SearchPlanner, SearchPlan
from .rag_pipeline import RAGPipeline
from .llm_service import LLMService
from .tools import Tools
from .memory import Memoria
from .observability import (
    generate_run_id,
    now_iso,
    hash_query,
    preview_query,
    Timer,
    get_resource_usage,
    log_observability_run,
)
from backend.db import buscar_propiedades, registrar_busqueda

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# Tools para CrewAI
@tool
def get_uf_value():
    """Obtiene el valor actual de la UF desde el Banco Central."""
    return Tools.get_uf_value()


@tool
def calculate_distance(coord1: str, coord2: str):
    """Calcula la distancia entre dos coordenadas."""
    c1 = tuple(map(float, coord1.split(",")))
    c2 = tuple(map(float, coord2.split(",")))
    return Tools.calculate_distance(c1, c2)


@tool
def retrieve_properties(query: str):
    """Recupera propiedades relevantes usando RAG."""
    rag = RAGPipeline()
    return rag.retrieve_properties(query)


@tool
def retrieve_properties_db(query: str, cantidad: int = 5):
    """Recupera propiedades relevantes desde la base de datos SQLite."""
    propiedades = buscar_propiedades(texto=query, cantidad=cantidad)
    registrar_busqueda(
        consulta=query,
        sql_gen="buscar_propiedades(texto)",
        n_results=len(propiedades),
        proveedor="sqlite",
    )
    return propiedades


@tool
def save_favorite_property(propiedad_id: str, nota: str = "") -> str:
    """Guarda una propiedad como favorita para el usuario."""
    try:
        id_int = int(propiedad_id)
        return Tools.guardar_propiedad_favorita(id_int, nota)
    except ValueError:
        return "El ID de propiedad debe ser un número entero."
    except Exception as e:
        return f"Error guardando favorito: {str(e)}"


@tool
def list_favorite_properties() -> str:
    """Lista las propiedades guardadas como favoritas por el usuario."""
    try:
        return Tools.listar_propiedades_favoritas()
    except Exception as e:
        return f"Error listando favoritos: {str(e)}"


class RealEstateAgent:
    def __init__(self):
        self.memory = Memoria()
        self.llm = LLMService()
        self.rag = RAGPipeline()
        self.planner = SearchPlanner()
        self.property_search_agent = Agent(
            role="Especialista en Búsqueda de Propiedades Inmobiliarias",
            goal="Encontrar propiedades que cumplan exactamente los criterios del usuario",
            backstory=(
                "Agente experto en búsqueda inmobiliaria que utiliza datos, búsqueda SQL y RAG "
                "para ofrecer opciones relevantes al usuario."
            ),
            tools=[
                retrieve_properties_db,
                retrieve_properties,
                get_uf_value,
                save_favorite_property,
                list_favorite_properties,
            ],
            verbose=False,
            allow_delegation=False,
        )

    def search_properties(self, query: str, criteria: dict) -> list[dict]:
        if not criteria:
            return buscar_propiedades(texto=query, cantidad=5)

        propiedades = buscar_propiedades(
            cantidad=5,
            comuna=criteria.get("comuna"),
            min_dormitorios=criteria.get("dormitorios_min"),
            min_banos=criteria.get("banos_min"),
            precio_min=criteria.get("presupuesto_min"),
            precio_max=criteria.get("presupuesto_max"),
            texto=criteria.get("caracteristicas_adicionales") or query,
        )

        if propiedades:
            registrar_busqueda(
                consulta=query,
                sql_gen=str(criteria),
                n_results=len(propiedades),
                proveedor="sqlite",
            )
            return propiedades

        return []

    def fallback_rag(self, query: str, memory_context: str | None = None) -> list[dict]:
        resultados = self.rag.retrieve_properties(query, k=5, memory_context=memory_context)
        registrar_busqueda(
            consulta=query,
            sql_gen="RAG fallback",
            n_results=len(resultados),
            proveedor="rag",
        )
        return resultados

    def _extract_properties_from_crew(self, crew_output: object) -> list[dict]:
        if crew_output is None:
            return []

        if hasattr(crew_output, "model_dump"):
            crew_output = crew_output.model_dump()

        return self._find_properties_in_structure(crew_output)

    def _find_properties_in_structure(self, data: object) -> list[dict]:
        if isinstance(data, list):
            if data and all(isinstance(item, dict) for item in data):
                if any(key in data[0] for key in ["titulo", "precio_uf", "link"]):
                    return data
            for item in data:
                result = self._find_properties_in_structure(item)
                if result:
                    return result
            return []

        if isinstance(data, dict):
            for value in data.values():
                result = self._find_properties_in_structure(value)
                if result:
                    return result
            return []

        if isinstance(data, str):
            try:
                parsed = json.loads(data)
                return self._find_properties_in_structure(parsed)
            except json.JSONDecodeError:
                return []

        return []

    def _format_preferences(self, preferences: dict) -> str:
        parts = []
        if preferences.get("comunas"):
            parts.append(f"comuna: {preferences['comunas'][0]}")
        if preferences.get("dormitorios"):
            parts.append(f"dormitorios: {preferences['dormitorios']}")
        if preferences.get("precio_maximo_uf"):
            parts.append(f"presupuesto máximo: {preferences['precio_maximo_uf']} UF")
        if preferences.get("amenities"):
            parts.append(f"amenities: {', '.join(preferences['amenities'])}")
        return "; ".join(parts)

    def _merge_criteria_with_memory(self, criteria: dict, query: str) -> dict:
        merged = dict(criteria)
        if self.memory.es_followup(query):
            preferences = self.memory.extraer_preferencias()
            if not merged.get("comuna") and preferences.get("comunas"):
                merged["comuna"] = preferences["comunas"][0]
            if not merged.get("dormitorios_min") and preferences.get("dormitorios"):
                merged["dormitorios_min"] = preferences["dormitorios"]
            if not merged.get("presupuesto_max") and preferences.get("precio_maximo_uf"):
                merged["presupuesto_max"] = preferences["precio_maximo_uf"]
            if not merged.get("caracteristicas_adicionales") and preferences.get("amenities"):
                merged["caracteristicas_adicionales"] = ", ".join(preferences["amenities"])
        return merged

    def _build_memory_context(self, query: str) -> str:
        context_parts = [self.memory.resumen_contexto()] if self.memory.resumen_contexto() else []
        if self.memory.es_followup(query):
            context_parts.append("Esta consulta parece una continuación de la conversación anterior.")
            preferences = self.memory.extraer_preferencias()
            preference_text = self._format_preferences(preferences)
            if preference_text:
                context_parts.append(f"Preferencias implícitas previas: {preference_text}")
        return "\n".join(part for part in context_parts if part)

    def _summary_from_properties(self, properties: list[dict], query: str) -> str:
        if not properties:
            return f"Última búsqueda: '{query}' no arrojó resultados."

        mejor = properties[0]
        comuna = mejor.get("comuna") or mejor.get("ubicacion_raw") or "ubicación no especificada"
        dormitorios = mejor.get("dormitorios") or mejor.get("dormitorios_min") or "N/A"
        precio = mejor.get("precio_uf") or mejor.get("precio_valor") or "N/A"
        return (
            f"Última búsqueda: {query}. Propiedad principal: {dormitorios} dormitorios en {comuna}, "
            f"precio {precio} UF."
        )

    def _update_contexto_activo(self, properties: list[dict], query: str):
        if hasattr(self.memory, "actualizar_contexto_busqueda"):
            self.memory.actualizar_contexto_busqueda(query, properties)
            return

        resumen = self._summary_from_properties(properties, query)
        self.memory.set_contexto(resumen)

    def _execute_crew_search(self, query: str, plan: SearchPlan, context: str, uf_value: str | None) -> tuple[list[dict], str]:
        task_description = (
            f"Buscar propiedades para la consulta: {query}. "
            f"Plan: use_sql={plan.use_sql}, use_rag={plan.use_rag}, "
            f"use_rag_first={plan.use_rag_first}, cantidad={plan.cantidad}, "
            f"strict_matching={plan.strict_matching}."
        )

        task = Task(
            description=task_description,
            expected_output="Lista de propiedades relevantes en formato JSON",
            agent=self.property_search_agent,
            config={
                "query": query,
                "plan": plan.__dict__,
                "memory_context": context,
                "uf_value": uf_value,
            },
        )

        crew = Crew(agents=[self.property_search_agent], tasks=[task], verbose=False, memory=False)
        crew_result = crew.kickoff()
        properties = self._extract_properties_from_crew(crew_result)
        provider = "CrewAI" if properties else "CrewAI-empty"

        registrar_busqueda(
            consulta=query,
            sql_gen=f"CrewAI search plan: {plan}",
            n_results=len(properties),
            proveedor="crewai",
        )

        return properties, provider

    def _get_observability_provider(self) -> str:
        """
        Determina el proveedor real del LLM para observabilidad.

        LLMService usa Ollama mediante una API compatible con OpenAI, por eso
        se priorizan atributos explícitos del servicio y luego variables de
        entorno. Si nada existe, se asume Ollama como proveedor local.
        """
        provider = (
            getattr(self.llm, "provider", None)
            or getattr(self.llm, "llm_provider", None)
            or os.getenv("LLM_PROVIDER")
            or "ollama"
        )

        return str(provider).lower().strip()

    def _get_observability_model_name(self) -> str:
        """
        Obtiene el nombre real del modelo usado por el servicio LLM.

        Mantiene fallback a OLLAMA_MODEL para que el log no quede vacío si el
        servicio cambia internamente o si todavía no expone model_name.
        """
        model_name = (
            getattr(self.llm, "model_name", None)
            or getattr(self.llm, "model", None)
            or os.getenv("OLLAMA_MODEL")
            or "llama3.2:3b"
        )

        return str(model_name).strip()

    def _get_llm_usage_snapshot(self) -> dict:
        """
        Lee tokens acumulados sin acoplar respond() a una implementación concreta.

        Si Ollama no entrega usage, LLMService devuelve ceros y el flujo sigue
        funcionando sin inventar métricas.
        """
        if hasattr(self.llm, "get_usage_snapshot"):
            usage = self.llm.get_usage_snapshot() or {}
            return dict(usage)

        return {
            "model_name": self._get_observability_model_name(),
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    def _build_observability_payload(
        self,
        run_id: str,
        query: str,
        provider: str,
        model_name: str,
    ) -> dict:
        """
        Crea el payload base de observabilidad con valores seguros.

        Los costos simulados de OpenAI no se calculan aquí: observability.py los
        completa al normalizar el registro antes de insertarlo en SQLite.
        """
        return {
            "run_id": run_id,
            "timestamp": now_iso(),
            "query_text": query,
            "query_hash": hash_query(query),
            "query_preview": preview_query(query),
            "status": "started",
            "error_type": None,
            "error_message": None,
            "provider": provider,
            "model_name": model_name,
            "n_results": 0,
            "latency_total_ms": 0.0,
            "latency_criteria_ms": 0.0,
            "latency_planner_ms": 0.0,
            "latency_crew_ms": 0.0,
            "latency_rag_ms": 0.0,
            "latency_generation_ms": 0.0,
            "cpu_percent": None,
            "memory_mb": None,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "actual_cost_usd": 0.0 if provider == "ollama" else None,
            "openai_sim_model": os.getenv("OPENAI_SIM_MODEL", "gpt-4o-mini"),
        }

    def _finalize_observability_payload(
        self,
        obs: dict,
        properties: list[dict],
        total_timer: Timer,
        status: str,
    ) -> None:
        """
        Completa métricas finales antes de escribir observability_log.

        Se usa tanto en éxito como en error para evitar inconsistencias entre
        columnas: tokens, recursos, resultados, costo real y latencia total.
        """
        usage = self._get_llm_usage_snapshot()
        provider = str(usage.get("provider") or obs.get("provider") or "ollama").lower().strip()
        model_name = usage.get("model_name") or obs.get("model_name") or "llama3.2:3b"

        obs.update(
            {
                "status": status,
                "provider": provider,
                "model_name": model_name,
                "n_results": len(properties),
                "latency_total_ms": total_timer.elapsed_ms(),
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
                "actual_cost_usd": usage.get(
                    "actual_cost_usd",
                    0.0 if provider == "ollama" else obs.get("actual_cost_usd"),
                ),
                "openai_sim_model": usage.get(
                    "openai_sim_model",
                    obs.get("openai_sim_model") or os.getenv("OPENAI_SIM_MODEL", "gpt-4o-mini"),
                ),
            }
        )

        # get_resource_usage() ya retorna las mismas claves que espera la tabla:
        # cpu_percent y memory_mb.
        obs.update(get_resource_usage())

    def respond(self, query: str) -> str:
        """
        Ejecuta el flujo conversacional completo con observabilidad por corrida.

        La instrumentación mide latencias parciales, tokens, recursos y costos
        sin alterar la lógica de búsqueda existente ni exponer errores internos
        al usuario final.
        """
        run_id = generate_run_id()
        total_timer = Timer()
        provider = self._get_observability_provider()
        model_name = self._get_observability_model_name()
        obs = self._build_observability_payload(run_id, query, provider, model_name)

        # Reinicia el contador acumulado del LLM para que cada fila represente
        # únicamente la ejecución actual de respond(query).
        if hasattr(self.llm, "reset_usage"):
            self.llm.reset_usage()

        propiedades: list[dict] = []
        search_provider = "unknown"

        try:
            # 1. Memoria de usuario.
            self.memory.agregar_usuario(query)

            # 2. Extracción de criterios con LLM.
            criteria_timer = Timer()
            criteria = self.llm.extract_criteria(query)
            obs["latency_criteria_ms"] = criteria_timer.elapsed_ms()

            # 3. Merge de criterios explícitos con memoria conversacional.
            criteria = self._merge_criteria_with_memory(criteria, query)

            # 4. Planificación de búsqueda.
            # El planner recibe memoria/preferencias para manejar mejor preguntas
            # como "¿y algo parecido pero más barato?".
            planner_timer = Timer()
            memory_snapshot = self.memory.resumen_contexto()
            preferences_snapshot = self.memory.extraer_preferencias()
            plan = self.planner.plan(
                query,
                criteria,
                memory_context=memory_snapshot,
                preferences=preferences_snapshot,
            )
            obs["latency_planner_ms"] = planner_timer.elapsed_ms()
            logger.info("Ejecutando plan de búsqueda: %s", plan)

            contexto = self._build_memory_context(query)
            uf_value = None

            # 5. UF solo si el plan lo necesita.
            if plan.fetch_uf:
                uf_value = Tools.get_uf_value()
                contexto = (
                    f"{contexto}\nValor UF actual: {uf_value}"
                    if contexto
                    else f"Valor UF actual: {uf_value}"
                )

            # 6. Búsqueda principal vía CrewAI/tools.
            crew_timer = Timer()
            propiedades, search_provider = self._execute_crew_search(
                query,
                plan,
                contexto,
                uf_value,
            )
            obs["latency_crew_ms"] = crew_timer.elapsed_ms()

            # 7. Fallback RAG solamente cuando no hubo propiedades.
            if not propiedades and plan.use_rag:
                rag_timer = Timer()
                propiedades = self.fallback_rag(query, memory_context=contexto)
                search_provider = "RAG"
                obs["latency_rag_ms"] = rag_timer.elapsed_ms()

            # 8. Generación final basada únicamente en propiedades reales.
            generation_timer = Timer()
            respuesta = self.llm.generate_response(
                propiedades,
                query,
                contexto,
                historial=self.memory.get_historial_para_llm(),
            )
            obs["latency_generation_ms"] = generation_timer.elapsed_ms()

            # 9. Guarda respuesta del asistente en memoria.
            self.memory.agregar_asistente(respuesta, proveedor=search_provider)

            # 10. Actualiza el contexto activo para próximos follow-ups.
            self._update_contexto_activo(propiedades, query)

            # 11. Observabilidad exitosa. Se usa "ok" para coincidir con el
            # manual rápido de verificación y facilitar queries simples en SQL.
            self._finalize_observability_payload(
                obs=obs,
                properties=propiedades,
                total_timer=total_timer,
                status="ok",
            )
            log_observability_run(obs)

            return respuesta

        except Exception as exc:
            # Nunca se expone stacktrace al usuario. Se registra solo un resumen
            # corto del error para debugging y análisis de observabilidad.
            obs["error_type"] = type(exc).__name__
            obs["error_message"] = str(exc)[:240]

            self._finalize_observability_payload(
                obs=obs,
                properties=propiedades,
                total_timer=total_timer,
                status="error",
            )
            log_observability_run(obs)

            logger.warning(
                "Error procesando búsqueda run_id=%s error_type=%s error_message=%s",
                run_id,
                type(exc).__name__,
                str(exc)[:240],
            )

            return (
                "Ocurrió un problema al procesar tu búsqueda. "
                "Verifica que Ollama esté activo e intenta nuevamente."
            )


if __name__ == "__main__":
    agent = RealEstateAgent()

    consultas = [
        (
            "Busco departamento de 4 dormitorios en Las Condes con presupuesto 2500 UF",
            "Consulta con criterios específicos",
        ),
        (
            "Necesito algo con piscina y cerca del metro",
            "Consulta vaga descriptiva",
        ),
        (
            "Quiero un departamento en Ñuñoa por menos de 2000 UF",
            "Consulta con mención de UF",
        ),
    ]

    agent.memory.limpiar()
    for query, descripcion in consultas:
        print(f"\n--- {descripcion} ---")
        print("Consulta:", query)
        print("Respuesta:", agent.respond(query))

    print("\n--- Demostración de follow-up con memoria ---")
    initial = "Busco departamento de 3 dormitorios en Las Condes por menos de 2500 UF"
    follow_up = "¿Y ahora con piscina y cerca de un metro?"

    print("\nConsulta inicial:", initial)
    print("Respuesta:", agent.respond(initial))
    print("\nConsulta de seguimiento:", follow_up)
    print("Respuesta:", agent.respond(follow_up))

    print("\nHistorial en memoria:")
    agent.memory.mostrar_historial()
