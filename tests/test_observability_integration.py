import os
import sqlite3
from unittest.mock import patch

import pytest

from app.llm_service import LLMService
from app.main import RealEstateAgent
from app.observability import init_observability_db


def _latest_observability_row_after(before_id: int):
    """
    Lee el último registro creado en observability_log después de before_id.
    """
    conn = sqlite3.connect("backend/propiedades.db")
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        """
        SELECT
            id,
            status,
            provider,
            model_name,
            n_results,
            latency_total_ms,
            latency_criteria_ms,
            latency_planner_ms,
            latency_crew_ms,
            latency_rag_ms,
            latency_generation_ms,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            actual_cost_usd,
            estimated_openai_cost_usd,
            cpu_percent,
            memory_mb,
            error_type,
            error_message
        FROM observability_log
        WHERE id > ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (before_id,),
    ).fetchone()

    conn.close()
    return row


def _current_max_observability_id() -> int:
    """
    Obtiene el último id actual para validar que respond() inserte uno nuevo.
    """
    init_observability_db()

    conn = sqlite3.connect("backend/propiedades.db")

    before_id = conn.execute(
        "SELECT COALESCE(MAX(id), 0) FROM observability_log"
    ).fetchone()[0]

    conn.close()
    return before_id


def _assert_valid_success_observability_row(row):
    """
    Valida los campos principales que debe registrar RealEstateAgent.respond().
    """
    assert row is not None
    assert row["status"] == "ok"
    assert row["provider"] == "ollama"
    assert row["model_name"] == os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    assert row["n_results"] is not None
    assert row["latency_total_ms"] is not None
    assert row["latency_total_ms"] > 0
    assert row["latency_criteria_ms"] is not None
    assert row["latency_planner_ms"] is not None
    assert row["latency_crew_ms"] is not None
    assert row["latency_generation_ms"] is not None
    assert row["actual_cost_usd"] == 0.0
    assert row["error_type"] is None
    assert row["error_message"] is None


@patch.object(
    LLMService,
    "extract_criteria",
    return_value={
        "presupuesto_min": None,
        "presupuesto_max": 2500,
        "moneda": "UF",
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
@patch.object(
    LLMService,
    "get_usage_snapshot",
    return_value={
        "provider": "ollama",
        "model_name": os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
        "prompt_tokens": 120,
        "completion_tokens": 40,
        "total_tokens": 160,
        "llm_calls": 2,
        "actual_cost_usd": 0.0,
        "openai_sim_model": os.getenv("OPENAI_SIM_MODEL", "gpt-4o-mini"),
    },
)
def test_agent_respond_writes_observability_log_with_mocks(
    mock_usage,
    mock_generate,
    mock_extract,
):
    """
    Verifica observabilidad sin depender de Ollama, RAG real ni CrewAI real.

    Este test debe ser rápido y estable:
    - mockea extracción de criterios
    - mockea generación de respuesta
    - mockea búsqueda de propiedades
    - sí escribe una fila real en observability_log
    """
    before_id = _current_max_observability_id()

    propiedades_mock = [
        {
            "titulo": "Depto Las Condes",
            "precio_uf": 2500,
            "comuna": "Las Condes",
            "dormitorios": 3,
            "link": "https://example.com",
        }
    ]

    agent = RealEstateAgent()

    with patch("app.main.Tools.get_uf_value", return_value="35000"):
        with patch.object(
            RealEstateAgent,
            "_execute_crew_search",
            return_value=(propiedades_mock, "CrewAI"),
        ):
            response = agent.respond(
                "Busco departamento de 3 dormitorios en Las Condes por menos de 2500 UF"
            )

    assert isinstance(response, str)
    assert len(response.strip()) > 0

    row = _latest_observability_row_after(before_id)

    _assert_valid_success_observability_row(row)

    assert row["n_results"] == 1
    assert row["prompt_tokens"] == 120
    assert row["completion_tokens"] == 40
    assert row["total_tokens"] == 160


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_OLLAMA_INTEGRATION_TESTS") != "1",
    reason=(
        "Test de integración con Ollama desactivado. "
        "Usa RUN_OLLAMA_INTEGRATION_TESTS=1 para activarlo."
    ),
)
def test_agent_respond_writes_observability_log_with_real_ollama():
    """
    Verifica observabilidad usando Ollama real.

    Mantiene mockeada la búsqueda CrewAI para no depender de RAG, embeddings
    ni scraping. Lo que se prueba realmente aquí es:
    - LLMService contra Ollama
    - RealEstateAgent.respond()
    - escritura en observability_log
    """
    before_id = _current_max_observability_id()

    propiedades_mock = [
        {
            "titulo": "Depto Las Condes",
            "precio_uf": 2500,
            "comuna": "Las Condes",
            "dormitorios": 3,
            "link": "https://example.com",
        }
    ]

    agent = RealEstateAgent()

    with patch("app.main.Tools.get_uf_value", return_value="35000"):
        with patch.object(
            RealEstateAgent,
            "_execute_crew_search",
            return_value=(propiedades_mock, "CrewAI"),
        ):
            response = agent.respond(
                "Busco departamento de 3 dormitorios en Las Condes por menos de 2500 UF"
            )

    assert isinstance(response, str)
    assert len(response.strip()) > 0

    row = _latest_observability_row_after(before_id)

    _assert_valid_success_observability_row(row)

    assert row["n_results"] == 1