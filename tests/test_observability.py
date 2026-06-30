import sqlite3

from app.observability import (
    Timer,
    estimate_openai_cost,
    estimate_provider_api_cost,
    generate_run_id,
    get_observability_cost_summary,
    get_resource_usage,
    hash_query,
    log_observability_run,
    preview_query,
)


def test_generate_run_id_genera_strings_distintos():
    run_id_1 = generate_run_id()
    run_id_2 = generate_run_id()

    assert isinstance(run_id_1, str)
    assert isinstance(run_id_2, str)
    assert run_id_1
    assert run_id_2
    assert run_id_1 != run_id_2


def test_hash_query_es_estable_y_normaliza_texto():
    query_1 = "  Departamento   EN   Ñuñoa con piscina  "
    query_2 = "departamento en ñuñoa con piscina"

    assert hash_query(query_1) == hash_query(query_2)
    assert hash_query(query_1) == hash_query(query_1)
    assert len(hash_query(query_1)) == 64


def test_preview_query_limita_largo():
    query = "x" * 200
    preview = preview_query(query, max_len=30)

    assert isinstance(preview, str)
    assert len(preview) == 30
    assert preview.endswith("...")


def test_timer_retorna_milisegundos_no_negativos():
    timer = Timer()

    elapsed_ms = timer.elapsed_ms()

    assert isinstance(elapsed_ms, float)
    assert elapsed_ms >= 0


def test_get_resource_usage_retorna_cpu_y_memoria():
    usage = get_resource_usage()

    assert "cpu_percent" in usage
    assert "memory_mb" in usage

    assert usage["cpu_percent"] is None or isinstance(
        usage["cpu_percent"],
        (int, float),
    )
    assert usage["memory_mb"] is None or isinstance(
        usage["memory_mb"],
        (int, float),
    )


def test_log_observability_run_inserta_registro_en_db_temporal(tmp_path):
    db_path = tmp_path / "observability_test.db"

    ok = log_observability_run(
        {
            "query_text": "Busco departamento en Providencia",
            "status": "ok",
            "provider": "ollama",
            "model_name": "llama3.2:3b",
            "n_results": 2,
            "latency_total_ms": 12.5,
            "latency_criteria_ms": 1.0,
            "latency_planner_ms": 1.0,
            "latency_crew_ms": 2.0,
            "latency_rag_ms": 0.0,
            "latency_generation_ms": 8.5,
            "cpu_percent": 0.0,
            "memory_mb": 120.0,
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        },
        db_path=str(db_path),
    )

    assert ok is True

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM observability_log ORDER BY id DESC LIMIT 1"
        ).fetchone()

    assert row is not None
    assert row["status"] == "ok"
    assert row["provider"] == "ollama"
    assert row["model_name"] == "llama3.2:3b"
    assert row["n_results"] == 2
    assert row["actual_cost_usd"] == 0.0
    assert row["estimated_cost_usd"] == 0.0
    assert row["query_hash"]
    assert row["query_preview"] == "Busco departamento en Providencia"


def test_estimate_provider_api_cost_ollama_retorna_cero():
    cost = estimate_provider_api_cost(
        "ollama",
        model_name="llama3.2:3b",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
    )

    assert cost == 0.0


def test_estimate_openai_cost_gpt_4o_mini_con_total_tokens_no_negativo():
    cost = estimate_openai_cost("gpt-4o-mini", total_tokens=1300)

    assert cost is not None
    assert cost >= 0


def test_get_observability_cost_summary_retorna_totales_y_costos_acumulados(tmp_path):
    db_path = tmp_path / "observability_summary_test.db"

    log_observability_run(
        {
            "query_text": "Consulta 1",
            "status": "ok",
            "provider": "ollama",
            "model_name": "llama3.2:3b",
            "latency_total_ms": 10,
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "estimated_openai_cost_usd": 0.001,
        },
        db_path=str(db_path),
    )
    log_observability_run(
        {
            "query_text": "Consulta 2",
            "status": "ok",
            "provider": "ollama",
            "model_name": "llama3.2:3b",
            "latency_total_ms": 20,
            "prompt_tokens": 200,
            "completion_tokens": 100,
            "total_tokens": 300,
            "estimated_openai_cost_usd": 0.002,
        },
        db_path=str(db_path),
    )

    summary = get_observability_cost_summary(db_path=str(db_path))

    assert summary["total_runs"] == 2
    assert summary["total_actual_cost_usd"] == 0.0
    assert summary["total_provider_cost_usd"] == 0.0
    assert summary["total_openai_sim_cost_usd"] == 0.003
    assert summary["total_tokens"] == 450
    assert summary["avg_latency_total_ms"] == 15.0
