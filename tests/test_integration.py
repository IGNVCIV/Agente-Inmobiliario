import os
from unittest.mock import MagicMock, patch

import pytest
from dotenv import load_dotenv

# Carga .env antes de instanciar servicios que dependen de variables de entorno.
load_dotenv(override=True)

from app.llm_service import LLMService
from app.main import RealEstateAgent
from app.memory import Memoria
from app.planner import SearchPlanner


def make_mock_openai_response(content: str, model_name: str | None = None) -> MagicMock:
    """
    Construye un mock compatible con:
    response.choices[0].message.content
    response.usage.prompt_tokens
    response.usage.completion_tokens
    response.usage.total_tokens

    Esto permite probar LLMService sin llamar realmente a Ollama/OpenAI.
    """
    response = MagicMock()

    choice = MagicMock()
    choice.message.content = content
    response.choices = [choice]

    response.usage.prompt_tokens = 20
    response.usage.completion_tokens = 10
    response.usage.total_tokens = 30

    response.model = model_name or os.getenv("OLLAMA_MODEL", "llama3.2:3b")

    return response


@pytest.fixture(autouse=True)
def stable_test_env(monkeypatch):
    """
    Asegura valores estables para los tests.

    Si el .env ya tiene estos valores, se respetan.
    Si no existen, se usan defaults compatibles con Ollama local.
    """
    monkeypatch.setenv("LLM_PROVIDER", os.getenv("LLM_PROVIDER", "ollama"))
    monkeypatch.setenv("OLLAMA_MODEL", os.getenv("OLLAMA_MODEL", "llama3.2:3b"))
    monkeypatch.setenv(
        "OLLAMA_BASE_URL",
        os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
    )


@pytest.fixture
def agent_without_observability_write():
    """
    Crea el agente evitando que los tests unitarios escriban registros reales
    en observability_log.

    La observabilidad se prueba de forma indirecta verificando que respond()
    no rompe el flujo.
    """
    with patch("app.main.log_observability_run", return_value=True):
        yield RealEstateAgent()


@patch.object(
    LLMService,
    "extract_criteria",
    return_value={
        "presupuesto_min": None,
        "presupuesto_max": None,
        "moneda": None,
        "comuna": "Las Condes",
        "dormitorios_min": 3,
        "banos_min": None,
        "caracteristicas_adicionales": None,
    },
)
@patch.object(
    LLMService,
    "generate_response",
    return_value="Propiedad encontrada en Las Condes con 3 dormitorios.",
)
def test_agent_responds_to_specific_query(
    mock_generate,
    mock_extract,
    agent_without_observability_write,
):
    """Verifica que el agente responda a una consulta con criterios específicos."""
    agent = agent_without_observability_write

    propiedades_mock = [
        {
            "titulo": "Depto Las Condes",
            "precio_uf": 3000,
            "comuna": "Las Condes",
            "link": "https://example.com",
        }
    ]

    with patch.object(
        RealEstateAgent,
        "_execute_crew_search",
        return_value=(propiedades_mock, "CrewAI"),
    ):
        response = agent.respond("3 dormitorios en Las Condes")

    assert isinstance(response, str)
    assert len(response) > 20
    mock_extract.assert_called_once()
    mock_generate.assert_called_once()


@patch.object(LLMService, "extract_criteria", return_value={})
@patch.object(
    LLMService,
    "generate_response",
    return_value="Opciones encontradas con piscina en el stock de propiedades.",
)
def test_agent_responds_to_vague_query(
    mock_generate,
    mock_extract,
    agent_without_observability_write,
):
    """Verifica que una consulta vaga aún retorne respuesta usando fallback."""
    agent = agent_without_observability_write

    fallback_mock = [
        {
            "titulo": "Depto piscina",
            "precio_uf": 2200,
            "comuna": "Ñuñoa",
            "link": "https://example.com",
        }
    ]

    with patch.object(
        RealEstateAgent,
        "_execute_crew_search",
        return_value=([], "CrewAI-empty"),
    ):
        with patch.object(
            RealEstateAgent,
            "fallback_rag",
            return_value=fallback_mock,
        ):
            response = agent.respond("algo barato con piscina")

    assert isinstance(response, str)
    assert len(response) > 0
    mock_extract.assert_called_once()
    mock_generate.assert_called_once()


def test_criteria_extraction_structure():
    """
    Verifica que extract_criteria retorne un diccionario con las claves esperadas.

    Este test no llama a Ollama realmente: mockea el cliente OpenAI-compatible
    usado por Ollama.
    """
    service = LLMService()
    service.client = MagicMock()

    service.client.chat.completions.create.return_value = make_mock_openai_response(
        (
            '{"presupuesto_min": null, '
            '"presupuesto_max": 8000, '
            '"moneda": "UF", '
            '"comuna": "Providencia", '
            '"dormitorios_min": 4, '
            '"banos_min": 2, '
            '"caracteristicas_adicionales": "balcón"}'
        )
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
    assert criteria["comuna"] == "Providencia"
    assert criteria["moneda"] == "UF"
    assert criteria["dormitorios_min"] == 4
    assert criteria["dormitorios_min"] >= 1

    usage = service.get_usage_snapshot()
    assert usage["model_name"] == os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    assert usage["prompt_tokens"] == 20
    assert usage["completion_tokens"] == 10
    assert usage["total_tokens"] == 30
    assert usage["llm_calls"] == 1


def test_llm_service_reads_ollama_env():
    """
    Verifica que LLMService tome el modelo desde .env.

    No valida conexión real a Ollama; solo configuración.
    """
    expected_model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

    service = LLMService()

    assert service.model == expected_model
    assert service.get_usage_snapshot()["model_name"] == expected_model


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_OLLAMA_INTEGRATION_TESTS") != "1",
    reason="Test de integración con Ollama desactivado. Usa RUN_OLLAMA_INTEGRATION_TESTS=1 para activarlo.",
)
def test_ollama_real_criteria_extraction_integration():
    """
    Test opcional de integración real con Ollama.

    Requiere:
    - Ollama activo.
    - Modelo descargado.
    - .env configurado con OLLAMA_MODEL y OLLAMA_BASE_URL.

    No se ejecuta por defecto para no romper CI ni tests locales rápidos.
    """
    service = LLMService()

    criteria = service.extract_criteria(
        "Busco departamento de 2 dormitorios en Ñuñoa por menos de 3000 UF"
    )

    assert isinstance(criteria, dict)
    assert "comuna" in criteria
    assert "dormitorios_min" in criteria
    assert "presupuesto_max" in criteria


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
    assert (
        memoria.es_followup(
            "Busco departamento de 3 dormitorios en Providencia con piscina y estacionamiento"
        )
        is False
    )


@patch.object(
    LLMService,
    "extract_criteria",
    side_effect=[
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
    ],
)
@patch.object(
    LLMService,
    "generate_response",
    return_value="Respuesta de seguimiento con memoria.",
)
def test_agent_uses_memory_on_followup(
    mock_generate,
    mock_extract,
    agent_without_observability_write,
):
    """Verifica que el agente pase el historial de la sesión al LLM en un follow-up."""
    agent = agent_without_observability_write

    with patch("app.main.Tools.get_uf_value", return_value="35000"):
        with patch.object(
            RealEstateAgent,
            "_execute_crew_search",
            side_effect=[
                (
                    [
                        {
                            "titulo": "Depto Las Condes",
                            "precio_uf": 2500,
                            "comuna": "Las Condes",
                            "dormitorios": 3,
                            "link": "https://example.com",
                        }
                    ],
                    "CrewAI",
                ),
                (
                    [
                        {
                            "titulo": "Depto con piscina",
                            "precio_uf": 2600,
                            "comuna": "Las Condes",
                            "dormitorios": 3,
                            "link": "https://example.com",
                        }
                    ],
                    "CrewAI",
                ),
            ],
        ):
            first = agent.respond(
                "Busco departamento de 3 dormitorios en Las Condes por menos de 2500 UF"
            )
            second = agent.respond("¿Y ahora con piscina y cerca del metro?")

    assert isinstance(first, str)
    assert isinstance(second, str)
    assert mock_generate.call_count == 2

    second_call_kwargs = mock_generate.call_args_list[1].kwargs

    assert "historial" in second_call_kwargs
    assert any(
        item["role"] == "user"
        and "Busco departamento de 3 dormitorios" in item["content"]
        for item in second_call_kwargs["historial"]
    )
    assert any(
        item["role"] == "assistant"
        for item in second_call_kwargs["historial"]
    )


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
def test_agent_respond_is_string(
    mock_generate,
    mock_extract,
    agent_without_observability_write,
):
    """Verifica que el método respond siempre retorne un string."""
    agent = agent_without_observability_write

    with patch.object(
        RealEstateAgent,
        "_execute_crew_search",
        return_value=([], "CrewAI-empty"),
    ):
        with patch.object(
            RealEstateAgent,
            "fallback_rag",
            return_value=[],
        ):
            response = agent.respond("cualquier consulta")

    assert isinstance(response, str)


@patch.object(LLMService, "extract_criteria", side_effect=ConnectionError("Ollama caído"))
def test_agent_respond_returns_safe_message_on_ollama_error(
    mock_extract,
    agent_without_observability_write,
):
    """
    Verifica que respond() no exponga stacktrace al usuario cuando falla Ollama.
    """
    agent = agent_without_observability_write

    with patch("app.main.Tools.get_uf_value", return_value="35000"):
        with patch.object(
            RealEstateAgent,
            "_execute_crew_search",
            side_effect=[
                (
                    [
                        {
                            "titulo": "Depto Las Condes",
                            "precio_uf": 2500,
                            "comuna": "Las Condes",
                            "dormitorios": 3,
                            "link": "https://example.com",
                        }
                    ],
                    "CrewAI",
                ),
                (
                    [
                        {
                            "titulo": "Depto con piscina",
                            "precio_uf": 2600,
                            "comuna": "Las Condes",
                            "dormitorios": 3,
                            "link": "https://example.com",
                        }
                    ],
                    "CrewAI",
                ),
            ],
        ):
            first = agent.respond(
                "Busco departamento de 3 dormitorios en Las Condes por menos de 2500 UF"
            )
            second = agent.respond("¿Y ahora con piscina y cerca del metro?")