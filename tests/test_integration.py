import json
from unittest.mock import MagicMock, patch

from app.llm_service import LLMService
from app.main import RealEstateAgent
from app.memory import Memoria
from app.planner import SearchPlanner


def make_mock_openai_response(content: str) -> MagicMock:
    """Construye un mock de respuesta OpenAI con el contenido pedido."""
    response = MagicMock()
    message = MagicMock()
    message.message = MagicMock()
    message.message.content = content
    response.choices = [message]
    return response


@patch.object(LLMService, "extract_criteria", return_value={
    "presupuesto_min": None,
    "presupuesto_max": None,
    "moneda": None,
    "comuna": "Las Condes",
    "dormitorios_min": 3,
    "banos_min": None,
    "caracteristicas_adicionales": None,
})
@patch.object(LLMService, "generate_response", return_value="Propiedad encontrada en Las Condes con 3 dormitorios.")
def test_agent_responds_to_specific_query(mock_generate, mock_extract):
    """Verifica que el agente responda a una consulta con criterios específicos."""
    agent = RealEstateAgent()
    with patch.object(RealEstateAgent, "_execute_crew_search", return_value=([{"titulo": "Depto Las Condes", "precio_uf": 3000, "comuna": "Las Condes", "link": "https://example.com"}], "CrewAI")):
        response = agent.respond("3 dormitorios en Las Condes")

    assert isinstance(response, str)
    assert len(response) > 20


@patch.object(LLMService, "extract_criteria", return_value={})
@patch.object(LLMService, "generate_response", return_value="Opciones encontradas con piscina en el stock de propiedades.")
def test_agent_responds_to_vague_query(mock_generate, mock_extract):
    """Verifica que una consulta vaga aún retorne respuesta usando fallback."""
    agent = RealEstateAgent()
    with patch.object(RealEstateAgent, "_execute_crew_search", return_value=([], "CrewAI-empty")):
        with patch.object(RealEstateAgent, "fallback_rag", return_value=[{"titulo": "Depto piscina", "precio_uf": 2200, "comuna": "Ñuñoa", "link": "https://example.com"}]):
            response = agent.respond("algo barato con piscina")

    assert isinstance(response, str)
    assert len(response) > 0


def test_criteria_extraction_structure():
    """Verifica que extract_criteria retorne un diccionario con las claves esperadas."""
    service = LLMService()
    service.client = MagicMock()
    service.client.chat.completions.create.return_value = make_mock_openai_response(
        '{"presupuesto_min": null, "presupuesto_max": 8000, "moneda": "UF", "comuna": "Providencia", "dormitorios_min": 4, "banos_min": 2, "caracteristicas_adicionales": "balcón"}'
    )

    criteria = service.extract_criteria("4 dormitorios en Providencia, 8000 UF")

    expected_keys = {
        "presupuesto_min",
        "presupuesto_max",
        "moneda",
        "comuna",
        "dormitorios_min",
        "banos_min",
        "caracteristicas_adicionales",
    }
    assert set(criteria.keys()) == expected_keys
    assert criteria["dormitorios_min"] is not None
    assert criteria["dormitorios_min"] >= 1


def test_memory_persists_messages():
    """Verifica que la memoria persista el historial entre instancias."""
    memoria = Memoria()
    memoria.agregar_usuario("Hola agente")
    memoria.agregar_asistente("Hola usuario")

    memoria_nueva = Memoria()
    assert len(memoria_nueva.historial) >= 2


def test_memory_followup_detection():
    """Verifica la heurística básica para detectar consultas de seguimiento."""
    memoria = Memoria()
    assert memoria.es_followup("y cuánto cuesta?") is True
    assert memoria.es_followup("Busco departamento de 3 dormitorios en Providencia con piscina y estacionamiento") is False


@patch.object(LLMService, "extract_criteria", side_effect=[
    {
        "presupuesto_min": None,
        "presupuesto_max": 2500,
        "moneda": "UF",
        "comuna": "Las Condes",
        "dormitorios_min": 3,
        "banos_min": None,
        "caracteristicas_adicionales": None,
    },
    {
        "presupuesto_min": None,
        "presupuesto_max": None,
        "moneda": None,
        "comuna": None,
        "dormitorios_min": None,
        "banos_min": None,
        "caracteristicas_adicionales": "piscina",
    },
])
@patch.object(LLMService, "generate_response", return_value="Respuesta de seguimiento con memoria.")
def test_agent_uses_memory_on_followup(mock_generate, mock_extract):
    """Verifica que el agente pase el historial de la sesión al LLM en un follow-up."""
    agent = RealEstateAgent()

    with patch.object(
        RealEstateAgent,
        "_execute_crew_search",
        side_effect=[
            ([{"titulo": "Depto Las Condes", "precio_uf": 2500, "comuna": "Las Condes", "dormitorios": 3, "link": "https://example.com"}], "CrewAI"),
            ([{"titulo": "Depto con piscina", "precio_uf": 2600, "comuna": "Las Condes", "dormitorios": 3, "link": "https://example.com"}], "CrewAI"),
        ],
    ):
        first = agent.respond("Busco departamento de 3 dormitorios en Las Condes por menos de 2500 UF")
        second = agent.respond("¿Y ahora con piscina y cerca del metro?")

    assert isinstance(first, str)
    assert isinstance(second, str)
    assert mock_generate.call_count == 2

    second_call_kwargs = mock_generate.call_args_list[1].kwargs
    assert "historial" in second_call_kwargs
    assert any(
        item["role"] == "user" and "Busco departamento de 3 dormitorios" in item["content"]
        for item in second_call_kwargs["historial"]
    )
    assert any(item["role"] == "assistant" for item in second_call_kwargs["historial"])


def test_planner_vague_query():
    """Verifica que consultas vagas activen RAG primero."""
    planner = SearchPlanner()
    plan = planner.plan("algo lindo con vista al mar", {})
    assert plan.use_rag_first is True


def test_planner_specific_query():
    """Verifica que criterios específicos activen SQL estricto."""
    planner = SearchPlanner()
    criteria = {"comuna": "Ñuñoa", "dormitorios_min": 2}
    plan = planner.plan("depto en Ñuñoa 2 dorm", criteria)
    assert plan.use_sql is True
    assert plan.strict_matching is True


def test_planner_uf_detection():
    """Verifica que la detección de UF active la obtención de valor UF."""
    planner = SearchPlanner()
    plan = planner.plan("depto en 5000 UF máximo", {"moneda": "UF"})
    assert plan.fetch_uf is True


@patch.object(LLMService, "extract_criteria", return_value={})
@patch.object(LLMService, "generate_response", return_value="Respuesta de prueba.")
def test_agent_respond_is_string(mock_generate, mock_extract):
    """Verifica que el método respond siempre retorne un string."""
    agent = RealEstateAgent()
    with patch.object(RealEstateAgent, "_execute_crew_search", return_value=([], "CrewAI-empty")):
        with patch.object(RealEstateAgent, "fallback_rag", return_value=[]):
            response = agent.respond("cualquier consulta")

    assert isinstance(response, str)
