import hashlib
import logging
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from dotenv import load_dotenv

try:
    import psutil
except ImportError:
    psutil = None

try:
    from backend.db import DB_PATH
except Exception:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_PATH = os.path.join(BASE_DIR, "backend", "propiedades.db")


load_dotenv(override=True)

logger = logging.getLogger(__name__)

OBSERVABILITY_TABLE = "observability_log"


OBSERVABILITY_FIELDS = [
    "run_id",
    "timestamp",
    "query_hash",
    "query_preview",
    "status",
    "error_type",
    "error_message",
    "provider",
    "model_name",
    "n_results",
    "latency_total_ms",
    "latency_criteria_ms",
    "latency_planner_ms",
    "latency_crew_ms",
    "latency_rag_ms",
    "latency_generation_ms",
    "cpu_percent",
    "memory_mb",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",

    # Costo real estimado según el proveedor usado.
    # Con Ollama local será 0.0.
    "estimated_cost_usd",

    # Campos para evaluación comparativa.
    "actual_cost_usd",
    "openai_sim_model",
    "estimated_openai_cost_usd",
    "cost_note",

    "precision_score",
    "consistency_group",
    "notes",
]


COLUMN_TYPES = {
    "run_id": "TEXT",
    "timestamp": "TEXT",
    "query_hash": "TEXT",
    "query_preview": "TEXT",
    "status": "TEXT",
    "error_type": "TEXT",
    "error_message": "TEXT",
    "provider": "TEXT",
    "model_name": "TEXT",
    "n_results": "INTEGER",
    "latency_total_ms": "REAL",
    "latency_criteria_ms": "REAL",
    "latency_planner_ms": "REAL",
    "latency_crew_ms": "REAL",
    "latency_rag_ms": "REAL",
    "latency_generation_ms": "REAL",
    "cpu_percent": "REAL",
    "memory_mb": "REAL",
    "prompt_tokens": "INTEGER",
    "completion_tokens": "INTEGER",
    "total_tokens": "INTEGER",
    "estimated_cost_usd": "REAL",
    "actual_cost_usd": "REAL",
    "openai_sim_model": "TEXT",
    "estimated_openai_cost_usd": "REAL",
    "cost_note": "TEXT",
    "precision_score": "REAL",
    "consistency_group": "TEXT",
    "notes": "TEXT",
}


OBSERVABILITY_TABLE_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {OBSERVABILITY_TABLE} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    query_hash TEXT,
    query_preview TEXT,
    status TEXT,
    error_type TEXT,
    error_message TEXT,
    provider TEXT,
    model_name TEXT,
    n_results INTEGER,
    latency_total_ms REAL,
    latency_criteria_ms REAL,
    latency_planner_ms REAL,
    latency_crew_ms REAL,
    latency_rag_ms REAL,
    latency_generation_ms REAL,
    cpu_percent REAL,
    memory_mb REAL,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    estimated_cost_usd REAL,
    actual_cost_usd REAL,
    openai_sim_model TEXT,
    estimated_openai_cost_usd REAL,
    cost_note TEXT,
    precision_score REAL,
    consistency_group TEXT,
    notes TEXT
);
"""


OBSERVABILITY_INDEXES = f"""
CREATE INDEX IF NOT EXISTS idx_observability_run_id
ON {OBSERVABILITY_TABLE} (run_id);

CREATE INDEX IF NOT EXISTS idx_observability_timestamp
ON {OBSERVABILITY_TABLE} (timestamp);

CREATE INDEX IF NOT EXISTS idx_observability_status
ON {OBSERVABILITY_TABLE} (status);

CREATE INDEX IF NOT EXISTS idx_observability_provider
ON {OBSERVABILITY_TABLE} (provider);

CREATE INDEX IF NOT EXISTS idx_observability_model_name
ON {OBSERVABILITY_TABLE} (model_name);
"""


OPENAI_PRICING_PER_1M_TOKENS = {
    # Precios referenciales para evaluación académica.
    # Input/output expresados en USD por 1 millón de tokens.
    "gpt-4o-mini": {
        "input": 0.15,
        "output": 0.60,
    },
    "gpt-4o": {
        "input": 2.50,
        "output": 10.00,
    },
    "gpt-4.1": {
        "input": 2.00,
        "output": 8.00,
    },
    "gpt-4.1-mini": {
        "input": 0.40,
        "output": 1.60,
    },
    "gpt-4.1-nano": {
        "input": 0.10,
        "output": 0.40,
    },
}


def generate_run_id() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def hash_query(query: Optional[str]) -> str:
    if not query:
        return ""

    normalized = " ".join(query.strip().lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def preview_query(query: Optional[str], max_len: int = 120) -> str:
    if not query:
        return ""

    clean = " ".join(query.strip().split())

    if len(clean) <= max_len:
        return clean

    return clean[: max_len - 3] + "..."


def safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (ValueError, TypeError):
        return None


def safe_int(value: Any) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (ValueError, TypeError):
        return None


def safe_text(value: Any, max_len: int = 500) -> Optional[str]:
    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    if len(text) > max_len:
        return text[: max_len - 3] + "..."

    return text


class Timer:
    def __init__(self) -> None:
        self._start = time.perf_counter()

    def elapsed_ms(self) -> float:
        return round((time.perf_counter() - self._start) * 1000.0, 2)


def _ensure_observability_columns(conn: sqlite3.Connection) -> None:
    """
    Agrega columnas nuevas si la tabla ya existía con un esquema antiguo.

    Esto es importante porque CREATE TABLE IF NOT EXISTS no modifica tablas
    ya creadas anteriormente.
    """
    existing_columns = {
        row[1]
        for row in conn.execute(f"PRAGMA table_info({OBSERVABILITY_TABLE})").fetchall()
    }

    for column_name in OBSERVABILITY_FIELDS:
        if column_name not in existing_columns:
            column_type = COLUMN_TYPES[column_name]
            conn.execute(
                f"ALTER TABLE {OBSERVABILITY_TABLE} "
                f"ADD COLUMN {column_name} {column_type}"
            )


def init_observability_db(db_path: str = DB_PATH) -> bool:
    try:
        db_dir = os.path.dirname(db_path)

        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        with sqlite3.connect(db_path) as conn:
            conn.execute(OBSERVABILITY_TABLE_SCHEMA)
            _ensure_observability_columns(conn)
            conn.executescript(OBSERVABILITY_INDEXES)
            conn.commit()

        return True

    except Exception as exc:
        logger.warning("No se pudo inicializar la tabla de observabilidad: %s", exc)
        return False


def get_resource_usage() -> Dict[str, Optional[float]]:
    if psutil is None:
        return {
            "cpu_percent": None,
            "memory_mb": None,
        }

    try:
        process = psutil.Process(os.getpid())

        return {
            "cpu_percent": round(process.cpu_percent(interval=None), 2),
            "memory_mb": round(process.memory_info().rss / 1024 / 1024, 2),
        }

    except Exception as exc:
        logger.warning("No se pudo obtener el uso de recursos: %s", exc)

        return {
            "cpu_percent": None,
            "memory_mb": None,
        }


def get_default_provider() -> str:
    return (os.getenv("LLM_PROVIDER") or "ollama").lower().strip()


def get_default_model(provider: Optional[str] = None) -> str:
    provider_key = (provider or get_default_provider()).lower().strip()

    if provider_key == "ollama":
        return os.getenv("OLLAMA_MODEL", "llama3.2:3b")

    if provider_key == "github":
        return os.getenv("GITHUB_MODEL", "openai/gpt-4.1")

    if provider_key == "openai":
        return os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    return os.getenv("OLLAMA_MODEL", "llama3.2:3b")


def normalize_model_name(model_name: Optional[str]) -> str:
    """
    Normaliza nombres como:
    - openai/gpt-4o-mini -> gpt-4o-mini
    - gpt-4o-mini       -> gpt-4o-mini
    """
    model_key = (model_name or "").lower().strip()

    if "/" in model_key:
        model_key = model_key.split("/")[-1]

    return model_key


def estimate_openai_cost(
    model_name: Optional[str],
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
) -> Optional[float]:
    """
    Estima cuánto habría costado usando OpenAI.

    Si solo existe total_tokens y no hay separación entre prompt/completion,
    se usa total_tokens como input_tokens para obtener una estimación mínima.
    """
    prompt_tokens = safe_int(prompt_tokens) or 0
    completion_tokens = safe_int(completion_tokens) or 0
    total_tokens = safe_int(total_tokens) or 0

    if prompt_tokens == 0 and completion_tokens == 0 and total_tokens > 0:
        prompt_tokens = total_tokens

    model_key = normalize_model_name(model_name)

    if not model_key:
        return None

    rates = None

    # Importante: los modelos más específicos van primero.
    for known_model in [
        "gpt-4o-mini",
        "gpt-4.1-mini",
        "gpt-4.1-nano",
        "gpt-4.1",
        "gpt-4o",
    ]:
        if model_key.startswith(known_model):
            rates = OPENAI_PRICING_PER_1M_TOKENS[known_model]
            break

    if rates is None:
        return None

    input_cost = (prompt_tokens / 1_000_000) * rates["input"]
    output_cost = (completion_tokens / 1_000_000) * rates["output"]

    return round(input_cost + output_cost, 8)


def estimate_provider_api_cost(
    provider: Optional[str],
    model_name: Optional[str],
    prompt_tokens: Optional[int],
    completion_tokens: Optional[int],
    total_tokens: Optional[int] = None,
) -> Optional[float]:
    """
    Estima el costo real de API según el proveedor usado.

    - Ollama local: 0.0 USD de API.
    - OpenAI: usa tabla de precios referencial.
    - GitHub Models: no se estima aquí porque depende del plan/límites.
    """
    provider_key = (provider or "").lower().strip()

    if provider_key == "ollama":
        return 0.0

    if provider_key == "openai":
        return estimate_openai_cost(
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    return None


def build_cost_note(
    provider: str,
    model_name: str,
    openai_sim_model: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
) -> str:
    if provider == "ollama":
        note = (
            "Costo API real estimado: 0.0 USD, porque el modelo se ejecuta "
            "localmente con Ollama. estimated_openai_cost_usd representa una "
            f"simulación usando {openai_sim_model}."
        )
    else:
        note = (
            "estimated_cost_usd representa el costo estimado del proveedor usado. "
            f"estimated_openai_cost_usd representa una simulación usando {openai_sim_model}."
        )

    if prompt_tokens == 0 and completion_tokens == 0 and total_tokens > 0:
        note += (
            " Advertencia: solo se recibió total_tokens; la simulación puede ser "
            "una estimación mínima porque no se separaron tokens de entrada y salida."
        )

    return note


def normalize_observability_data(data: Dict[str, Any]) -> Dict[str, Any]:
    query_text = data.get("query_text", "")

    provider = (
        safe_text(data.get("provider"), 120)
        or get_default_provider()
    ).lower()

    model_name = (
        safe_text(data.get("model_name"), 120)
        or get_default_model(provider)
    )

    openai_sim_model = (
        safe_text(data.get("openai_sim_model"), 120)
        or safe_text(data.get("simulated_openai_model"), 120)
        or os.getenv("OPENAI_SIM_MODEL", "gpt-4o-mini")
    )

    prompt_tokens = safe_int(data.get("prompt_tokens")) or 0
    completion_tokens = safe_int(data.get("completion_tokens")) or 0
    total_tokens = safe_int(data.get("total_tokens"))

    if total_tokens is None:
        total_tokens = prompt_tokens + completion_tokens

    actual_cost_usd = safe_float(data.get("actual_cost_usd"))

    if actual_cost_usd is None:
        actual_cost_usd = estimate_provider_api_cost(
            provider=provider,
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    estimated_cost_usd = safe_float(data.get("estimated_cost_usd"))

    if estimated_cost_usd is None:
        estimated_cost_usd = actual_cost_usd

    estimated_openai_cost_usd = safe_float(data.get("estimated_openai_cost_usd"))

    if estimated_openai_cost_usd is None:
        estimated_openai_cost_usd = estimate_openai_cost(
            model_name=openai_sim_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    cost_note = (
        safe_text(data.get("cost_note"), 500)
        or build_cost_note(
            provider=provider,
            model_name=model_name,
            openai_sim_model=openai_sim_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
    )

    return {
        "run_id": safe_text(data.get("run_id")) or generate_run_id(),
        "timestamp": safe_text(data.get("timestamp")) or now_iso(),
        "query_hash": safe_text(data.get("query_hash")) or hash_query(query_text),
        "query_preview": (
            safe_text(data.get("query_preview"), 120)
            or preview_query(query_text)
        ),
        "status": safe_text(data.get("status"), 50) or "desconocido",
        "error_type": safe_text(data.get("error_type"), 120),
        "error_message": safe_text(data.get("error_message"), 500),
        "provider": provider,
        "model_name": safe_text(model_name, 120),
        "n_results": safe_int(data.get("n_results")),
        "latency_total_ms": safe_float(data.get("latency_total_ms")),
        "latency_criteria_ms": safe_float(data.get("latency_criteria_ms")),
        "latency_planner_ms": safe_float(data.get("latency_planner_ms")),
        "latency_crew_ms": safe_float(data.get("latency_crew_ms")),
        "latency_rag_ms": safe_float(data.get("latency_rag_ms")),
        "latency_generation_ms": safe_float(data.get("latency_generation_ms")),
        "cpu_percent": safe_float(data.get("cpu_percent")),
        "memory_mb": safe_float(data.get("memory_mb")),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "estimated_cost_usd": estimated_cost_usd,
        "actual_cost_usd": actual_cost_usd,
        "openai_sim_model": safe_text(openai_sim_model, 120),
        "estimated_openai_cost_usd": estimated_openai_cost_usd,
        "cost_note": cost_note,
        "precision_score": safe_float(data.get("precision_score")),
        "consistency_group": safe_text(data.get("consistency_group"), 120),
        "notes": safe_text(data.get("notes"), 500),
    }


def log_observability_run(data: Dict[str, Any], db_path: str = DB_PATH) -> bool:
    """
    Registra una ejecución del agente en la tabla observability_log.

    Está diseñado para no romper el flujo principal.
    Si falla la observabilidad, retorna False y el agente puede continuar.
    """
    fields = normalize_observability_data(data)

    try:
        init_observability_db(db_path)

        columns = ", ".join(OBSERVABILITY_FIELDS)
        placeholders = ", ".join(["?"] * len(OBSERVABILITY_FIELDS))
        values = [fields[field] for field in OBSERVABILITY_FIELDS]

        with sqlite3.connect(db_path) as conn:
            conn.execute(
                f"INSERT INTO {OBSERVABILITY_TABLE} ({columns}) VALUES ({placeholders})",
                values,
            )
            conn.commit()

        return True

    except Exception as exc:
        logger.warning(
            "No se pudo registrar la observabilidad; el flujo principal continuará: %s",
            exc,
        )
        return False


def get_latest_observability_runs(
    limit: int = 20,
    db_path: str = DB_PATH,
) -> list[dict]:
    limit = safe_int(limit) or 20
    limit = max(1, min(limit, 200))

    try:
        init_observability_db(db_path)

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT *
                FROM {OBSERVABILITY_TABLE}
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [dict(row) for row in rows]

    except Exception as exc:
        logger.warning("No se pudieron leer los registros de observabilidad: %s", exc)
        return []


def get_observability_cost_summary(db_path: str = DB_PATH) -> Dict[str, Any]:
    """
    Resumen útil para informe/evaluación.

    Muestra:
    - costo real estimado del proveedor usado
    - costo simulado si se hubiera usado OpenAI
    - tokens totales
    - latencia promedio
    """
    try:
        init_observability_db(db_path)

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                f"""
                SELECT
                    COUNT(*) AS total_runs,
                    SUM(COALESCE(actual_cost_usd, 0)) AS total_actual_cost_usd,
                    SUM(COALESCE(estimated_cost_usd, 0)) AS total_provider_cost_usd,
                    SUM(COALESCE(estimated_openai_cost_usd, 0)) AS total_openai_sim_cost_usd,
                    SUM(COALESCE(total_tokens, 0)) AS total_tokens,
                    AVG(COALESCE(latency_total_ms, 0)) AS avg_latency_total_ms
                FROM {OBSERVABILITY_TABLE}
                """
            ).fetchone()

        result = dict(row) if row else {}

        for key in [
            "total_actual_cost_usd",
            "total_provider_cost_usd",
            "total_openai_sim_cost_usd",
            "avg_latency_total_ms",
        ]:
            if result.get(key) is not None:
                result[key] = round(float(result[key]), 8)

        return result

    except Exception as exc:
        logger.warning("No se pudo generar resumen de costos: %s", exc)
        return {}
