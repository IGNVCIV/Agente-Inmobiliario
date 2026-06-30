#!/usr/bin/env python3
"""
Ejecuta escenarios controlados de observabilidad para un agente IA local.

Salida:
- data/observability/eval_results.csv
- data/observability/eval_summary.json

No requiere internet. Por defecto intenta evaluar el agente si se define AGENT_EVAL_URL;
si no, llama directamente a Ollama local en http://localhost:11434.
"""

from __future__ import annotations

import csv
import json
import math
import os
import time
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


NOTA_COSTOS = (
    "El proveedor principal es Ollama local. El costo real de API se registra como 0 USD. "
    "El costo OpenAI mostrado en observabilidad es una simulación referencial para análisis de sostenibilidad."
)

SCENARIOS: List[Dict[str, Any]] = [
    {
        "query": "Busco departamento de 3 dormitorios en Las Condes por menos de 2500 UF",
        "expected_keywords": ["Las Condes", "3", "UF"],
        "group": "especifica_las_condes",
    },
    {
        "query": "Busco departamento de 3 dormitorios en Las Condes por menos de 2500 UF",
        "expected_keywords": ["Las Condes", "3", "UF"],
        "group": "especifica_las_condes",
    },
    {
        "query": "Busco departamento de 3 dormitorios en Las Condes por menos de 2500 UF",
        "expected_keywords": ["Las Condes", "3", "UF"],
        "group": "especifica_las_condes",
    },
    {
        "query": "Necesito algo con piscina y cerca del metro",
        "expected_keywords": ["piscina", "metro"],
        "group": "amenities_piscina_metro",
    },
    {
        "query": "Necesito algo con piscina y cerca del metro",
        "expected_keywords": ["piscina", "metro"],
        "group": "amenities_piscina_metro",
    },
    {
        "query": "Necesito algo con piscina y cerca del metro",
        "expected_keywords": ["piscina", "metro"],
        "group": "amenities_piscina_metro",
    },
    {
        "query": "Quiero una propiedad económica en Providencia",
        "expected_keywords": ["Providencia"],
        "group": "providencia",
    },
    {
        "query": "Busco casa familiar en Ñuñoa",
        "expected_keywords": ["Ñuñoa", "casa"],
        "group": "nunoa",
    },
    {
        "query": "Muéstrame propiedades bajo 2000 UF",
        "expected_keywords": ["2000", "UF"],
        "group": "precio",
    },
    {
        "query": "Busco departamento en una comuna que no exista",
        "expected_keywords": [],
        "group": "sin_resultados",
    },
]

CSV_COLUMNS = [
    "scenario_id",
    "group",
    "query",
    "expected_keywords",
    "status",
    "error_type",
    "latency_ms",
    "precision_score",
    "consistency_score",
    "response_preview",
    "provider",
    "model_name",
]


class EvalConfig:
    def __init__(self) -> None:
        # Si AGENT_EVAL_URL está definido, se evalúa el agente. Si no, se usa Ollama directo.
        self.agent_eval_url = os.getenv("AGENT_EVAL_URL", "").strip()
        self.agent_request_field = os.getenv("AGENT_REQUEST_FIELD", "query").strip() or "query"
        self.agent_extra_payload = self._parse_extra_payload(os.getenv("AGENT_EXTRA_PAYLOAD", "{}"))

        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        self.model_name = os.getenv("OLLAMA_MODEL", os.getenv("MODEL_NAME", "llama3.1")).strip() or "llama3.1"
        self.provider = os.getenv("PROVIDER", "ollama_local").strip() or "ollama_local"
        self.timeout_seconds = float(os.getenv("EVAL_TIMEOUT_SECONDS", "60"))

        self.output_dir = Path(os.getenv("OBSERVABILITY_OUTPUT_DIR", "data/observability"))
        self.csv_path = self.output_dir / "eval_results.csv"
        self.summary_path = self.output_dir / "eval_summary.json"

    @property
    def mode(self) -> str:
        return "agent" if self.agent_eval_url else "ollama"

    @staticmethod
    def _parse_extra_payload(raw_value: str) -> Dict[str, Any]:
        try:
            parsed = json.loads(raw_value or "{}")
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        return {}


def normalize_text(value: Any) -> str:
    """Normaliza texto para comparación: minúsculas, sin tildes, con espacios estables."""
    text = str(value or "").lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.split())


def keyword_found(keyword: str, response_text: str) -> bool:
    return normalize_text(keyword) in normalize_text(response_text)


def detected_keywords(expected_keywords: Sequence[str], response_text: str) -> Set[str]:
    return {keyword for keyword in expected_keywords if keyword_found(keyword, response_text)}


def precision_score(expected_keywords: Sequence[str], response_text: str) -> Optional[float]:
    if not expected_keywords:
        return None
    detected = detected_keywords(expected_keywords, response_text)
    return round(len(detected) / len(expected_keywords), 4)


def jaccard_similarity(left: Set[str], right: Set[str]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def percentile(values: Sequence[float], percent: float) -> Optional[float]:
    if not values:
        return None
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return round(sorted_values[0], 2)
    position = (len(sorted_values) - 1) * (percent / 100.0)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return round(sorted_values[int(position)], 2)
    lower_value = sorted_values[lower]
    upper_value = sorted_values[upper]
    interpolated = lower_value + (upper_value - lower_value) * (position - lower)
    return round(interpolated, 2)


def mean_or_none(values: Iterable[Optional[float]]) -> Optional[float]:
    filtered = [value for value in values if value is not None]
    if not filtered:
        return None
    return round(sum(filtered) / len(filtered), 4)


def post_json(url: str, payload: Dict[str, Any], timeout_seconds: float) -> Any:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        raw = response.read().decode("utf-8", errors="replace")
        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type or raw.strip().startswith(("{", "[")):
            return json.loads(raw)
        return raw


def extract_text_from_response(payload: Any) -> str:
    """
    Extrae texto desde respuestas comunes de agentes y de Ollama.
    Soporta strings, dicts planos y estructuras anidadas frecuentes.
    """
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, list):
        return "\n".join(extract_text_from_response(item) for item in payload)
    if not isinstance(payload, dict):
        return str(payload)

    direct_fields = [
        "response",
        "answer",
        "message",
        "content",
        "output",
        "text",
        "result",
        "reply",
    ]
    for field in direct_fields:
        value = payload.get(field)
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            nested = extract_text_from_response(value)
            if nested:
                return nested

    # Ollama /api/chat: {"message": {"role": "assistant", "content": "..."}}
    message = payload.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return message["content"]

    # Algunos agentes devuelven data/output anidados.
    for field in ["data", "payload"]:
        nested_value = payload.get(field)
        nested_text = extract_text_from_response(nested_value)
        if nested_text:
            return nested_text

    return json.dumps(payload, ensure_ascii=False)


def call_agent(query: str, config: EvalConfig) -> str:
    payload: Dict[str, Any] = dict(config.agent_extra_payload)
    payload[config.agent_request_field] = query
    response_payload = post_json(config.agent_eval_url, payload, config.timeout_seconds)
    return extract_text_from_response(response_payload).strip()


def call_ollama(query: str, config: EvalConfig) -> str:
    url = f"{config.ollama_base_url}/api/chat"
    payload = {
        "model": config.model_name,
        "stream": False,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Eres un asistente inmobiliario. Responde en español, de forma breve, "
                    "manteniendo los datos relevantes de la consulta del usuario."
                ),
            },
            {"role": "user", "content": query},
        ],
    }
    response_payload = post_json(url, payload, config.timeout_seconds)
    return extract_text_from_response(response_payload).strip()


def run_single_scenario(scenario_id: int, scenario: Dict[str, Any], config: EvalConfig) -> Dict[str, Any]:
    query = scenario["query"]
    expected = scenario["expected_keywords"]

    print(f"[{scenario_id:02d}] Ejecutando grupo '{scenario['group']}': {query}")

    start = time.perf_counter()
    response_text = ""
    status = "success"
    error_type = ""

    try:
        if config.mode == "agent":
            response_text = call_agent(query, config)
        else:
            response_text = call_ollama(query, config)

        if not response_text:
            status = "error"
            error_type = "respuesta_vacia"
    except HTTPError as exc:
        status = "error"
        error_type = f"HTTPError_{exc.code}"
        try:
            response_text = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            response_text = str(exc)
    except URLError as exc:
        status = "error"
        error_type = "URLError"
        response_text = str(exc.reason)
    except TimeoutError as exc:
        status = "error"
        error_type = "TimeoutError"
        response_text = str(exc)
    except Exception as exc:  # noqa: BLE001 - en evaluación conviene registrar y continuar.
        status = "error"
        error_type = exc.__class__.__name__
        response_text = str(exc)

    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    score = precision_score(expected, response_text) if status == "success" else None
    found = detected_keywords(expected, response_text) if status == "success" else set()

    print(
        f"[{scenario_id:02d}] Estado: {status} | Latencia: {latency_ms} ms | "
        f"Precisión: {score if score is not None else 'N/A'}"
    )

    return {
        "scenario_id": scenario_id,
        "group": scenario["group"],
        "query": query,
        "expected_keywords": expected,
        "status": status,
        "error_type": error_type,
        "latency_ms": latency_ms,
        "precision_score": score,
        "consistency_score": None,
        "response_preview": " ".join(response_text.split())[:240],
        "provider": config.provider,
        "model_name": config.model_name,
        "_detected_keywords": found,
    }


def add_consistency_scores(rows: List[Dict[str, Any]]) -> None:
    grouped_rows: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped_rows[row["group"]].append(row)

    for group, group_rows in grouped_rows.items():
        if len(group_rows) < 2:
            continue

        successful_rows = [row for row in group_rows if row["status"] == "success"]
        if len(successful_rows) < 2:
            continue

        pair_scores: List[float] = []
        for index, left in enumerate(successful_rows):
            for right in successful_rows[index + 1 :]:
                pair_scores.append(
                    jaccard_similarity(left["_detected_keywords"], right["_detected_keywords"])
                )

        if not pair_scores:
            continue

        group_score = round(sum(pair_scores) / len(pair_scores), 4)
        for row in successful_rows:
            row["consistency_score"] = group_score

        print(f"Consistencia grupo '{group}': {group_score}")


def write_csv(rows: List[Dict[str, Any]], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            clean_row = {column: row.get(column) for column in CSV_COLUMNS}
            clean_row["expected_keywords"] = json.dumps(
                clean_row["expected_keywords"], ensure_ascii=False
            )
            writer.writerow(clean_row)


def write_summary(rows: List[Dict[str, Any]], config: EvalConfig, path: Path) -> Dict[str, Any]:
    total_queries = len(rows)
    success_count = sum(1 for row in rows if row["status"] == "success")
    error_count = total_queries - success_count
    latency_values = [float(row["latency_ms"]) for row in rows]

    summary = {
        "total_queries": total_queries,
        "success_count": success_count,
        "error_count": error_count,
        "error_rate": round(error_count / total_queries, 4) if total_queries else None,
        "latency_avg_ms": round(sum(latency_values) / len(latency_values), 2)
        if latency_values
        else None,
        "latency_p95_ms": percentile(latency_values, 95),
        "precision_avg": mean_or_none(row["precision_score"] for row in rows),
        "consistency_avg": mean_or_none(row["consistency_score"] for row in rows),
        "provider": config.provider,
        "model_name": config.model_name,
        "nota_costos": NOTA_COSTOS,
    }

    with path.open("w", encoding="utf-8") as file:
        json.dump(summary, file, ensure_ascii=False, indent=2)
        file.write("\n")

    return summary


def main() -> int:
    config = EvalConfig()
    config.output_dir.mkdir(parents=True, exist_ok=True)

    print("Iniciando evaluación de observabilidad...")
    print(f"Modo de evaluación: {config.mode}")
    if config.mode == "agent":
        print(f"Endpoint del agente: {config.agent_eval_url}")
        print(f"Campo de consulta: {config.agent_request_field}")
    else:
        print(f"Endpoint Ollama: {config.ollama_base_url}/api/chat")
    print(f"Proveedor: {config.provider}")
    print(f"Modelo: {config.model_name}")
    print(f"Directorio de salida: {config.output_dir}")

    rows = [
        run_single_scenario(index, scenario, config)
        for index, scenario in enumerate(SCENARIOS, start=1)
    ]

    add_consistency_scores(rows)
    write_csv(rows, config.csv_path)
    summary = write_summary(rows, config, config.summary_path)

    print("Evaluación finalizada.")
    print(f"CSV generado: {config.csv_path}")
    print(f"JSON generado: {config.summary_path}")
    print(
        "Resumen: "
        f"total={summary['total_queries']}, "
        f"éxitos={summary['success_count']}, "
        f"errores={summary['error_count']}, "
        f"latencia_promedio_ms={summary['latency_avg_ms']}, "
        f"precision_promedio={summary['precision_avg']}, "
        f"consistencia_promedio={summary['consistency_avg']}"
    )

    # No se devuelve error aunque algunas consultas fallen: esas fallas quedan registradas.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
