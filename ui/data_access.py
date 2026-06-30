"""Carga ligera de datos para Dashboard y Traceability."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import streamlit as st


LATENCY_COLS = ["latency_ms", "total_latency_ms", "duration_ms", "elapsed_ms", "response_time_ms"]
QUERY_COLS = ["query_preview", "query", "user_query", "prompt", "input", "message", "user_message"]
STATUS_COLS = ["status", "estado", "result", "outcome"]
ERROR_COLS = ["error_type", "error", "exception_type", "failure_type", "tipo_error"]
PROVIDER_COLS = ["provider", "llm_provider", "model_provider", "proveedor"]
MODEL_COLS = ["model_name", "model", "llm_model", "modelo", "ollama_model"]
TIMESTAMP_COLS = ["timestamp", "created_at", "datetime", "date", "fecha", "ts"]
EXECUTION_COLS = ["execution_id", "run_id", "trace_id", "request_id", "interaction_id", "scenario_id"]
TOKEN_COLS = ["tokens_total", "total_tokens", "token_count", "tokens", "num_tokens"]
SIM_COST_COLS = ["estimated_openai_cost_usd", "simulated_openai_cost_usd", "openai_cost_usd"]
ACTUAL_COST_COLS = ["actual_cost_usd", "api_cost_usd", "real_cost_usd", "cost_usd"]
PRECISION_COLS = ["precision_score", "precision", "score_precision"]
CONSISTENCY_COLS = ["consistency_score", "consistency", "score_consistency"]


def get_col(df: pd.DataFrame | None, candidates: Iterable[str]) -> str | None:
    if df is None or df.empty:
        return None
    lookup = {str(col).lower().strip(): col for col in df.columns}
    for candidate in candidates:
        found = lookup.get(candidate.lower().strip())
        if found:
            return found
    return None


def numeric(df: pd.DataFrame | None, col: str | None) -> pd.Series:
    if df is None or df.empty or not col or col not in df.columns:
        return pd.Series(dtype="float64")
    return pd.to_numeric(df[col], errors="coerce").dropna()


def fmt_int(value: Any) -> str:
    try:
        return f"{int(round(float(value))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "N/D"


def fmt_ms(value: Any) -> str:
    try:
        return f"{float(value):,.0f} ms".replace(",", ".")
    except (TypeError, ValueError):
        return "N/D"


def fmt_pct(value: Any) -> str:
    try:
        number = float(value)
        number = number * 100 if 0 <= number <= 1 else number
        return f"{number:.1f} %".replace(".", ",")
    except (TypeError, ValueError):
        return "N/D"


def fmt_usd(value: Any) -> str:
    try:
        return f"US$ {float(value):,.6f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "N/D"


def is_success(value: Any) -> bool:
    if value is None or pd.isna(value):
        return True
    text = str(value).strip().lower()
    return text in {"", "ok", "success", "exitoso", "éxito", "completed", "complete", "200", "true"}


@st.cache_data(show_spinner=False)
def load_sqlite_log(db_path: str) -> tuple[pd.DataFrame, str | None]:
    path = Path(db_path)
    if not path.exists():
        return pd.DataFrame(), f"No se encontró la base de datos: {path}"
    try:
        with sqlite3.connect(path) as conn:
            exists = pd.read_sql_query(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='observability_log'",
                conn,
            )
            if exists.empty:
                return pd.DataFrame(), "La tabla observability_log no existe."
            return pd.read_sql_query("SELECT * FROM observability_log", conn), None
    except Exception as exc:
        return pd.DataFrame(), f"Error leyendo observability_log: {exc}"


@st.cache_data(show_spinner=False)
def load_csv(path_text: str) -> tuple[pd.DataFrame, str | None]:
    path = Path(path_text)
    if not path.exists():
        return pd.DataFrame(), f"No se encontró el archivo: {path}"
    try:
        return pd.read_csv(path), None
    except Exception as exc:
        return pd.DataFrame(), f"Error leyendo {path.name}: {exc}"


@st.cache_data(show_spinner=False)
def load_json(path_text: str) -> tuple[dict[str, Any], str | None]:
    path = Path(path_text)
    if not path.exists():
        return {}, f"No se encontró el archivo: {path}"
    try:
        with path.open("r", encoding="utf-8") as file:
            value = json.load(file)
        return value if isinstance(value, dict) else {}, None
    except Exception as exc:
        return {}, f"Error leyendo {path.name}: {exc}"


def resolve_paths(project_root: Path) -> tuple[Path, Path, Path]:
    return (
        Path(os.getenv("OBS_DB_PATH", str(project_root / "backend" / "propiedades.db"))),
        Path(os.getenv("OBS_EVAL_RESULTS_PATH", str(project_root / "data" / "observability" / "eval_results.csv"))),
        Path(os.getenv("OBS_EVAL_SUMMARY_PATH", str(project_root / "data" / "observability" / "eval_summary.json"))),
    )


def load_observability_bundle(project_root: Path) -> dict[str, Any]:
    db_path, eval_path, summary_path = resolve_paths(project_root)
    db_df, db_error = load_sqlite_log(str(db_path))
    eval_df, eval_error = load_csv(str(eval_path))
    summary, summary_error = load_json(str(summary_path))
    return {
        "db_df": db_df,
        "eval_df": eval_df,
        "summary": summary,
        "errors": [error for error in [db_error, eval_error, summary_error] if error],
        "paths": {"db": db_path, "eval": eval_path, "summary": summary_path},
    }


def latest_rows(df: pd.DataFrame, limit: int = 8) -> pd.DataFrame:
    if df.empty:
        return df
    output = df.copy()
    ts_col = get_col(output, TIMESTAMP_COLS)
    if ts_col:
        output["_sort_ts"] = pd.to_datetime(output[ts_col], errors="coerce")
        output = output.sort_values("_sort_ts", ascending=False).drop(columns=["_sort_ts"])
    else:
        output = output.tail(limit).iloc[::-1]
    return output.head(limit)


def compute_summary(db_df: pd.DataFrame, eval_df: pd.DataFrame, summary: dict[str, Any]) -> dict[str, Any]:
    latency = numeric(db_df, get_col(db_df, LATENCY_COLS))
    if latency.empty:
        latency = numeric(eval_df, get_col(eval_df, LATENCY_COLS))

    status_col = get_col(db_df, STATUS_COLS)
    error_col = get_col(db_df, ERROR_COLS)
    error_count = None
    if not db_df.empty and (status_col or error_col):
        mask = pd.Series(False, index=db_df.index)
        if status_col:
            mask = mask | ~db_df[status_col].apply(is_success)
        if error_col:
            mask = mask | ~db_df[error_col].apply(is_success)
        error_count = int(mask.sum())

    provider_col = get_col(db_df, PROVIDER_COLS) or get_col(eval_df, PROVIDER_COLS)
    model_col = get_col(db_df, MODEL_COLS) or get_col(eval_df, MODEL_COLS)
    provider_source = db_df if provider_col and provider_col in db_df.columns else eval_df
    model_source = db_df if model_col and model_col in db_df.columns else eval_df

    precision = numeric(eval_df, get_col(eval_df, PRECISION_COLS))
    consistency = numeric(eval_df, get_col(eval_df, CONSISTENCY_COLS))
    sim_cost = numeric(db_df, get_col(db_df, SIM_COST_COLS))
    actual_cost = numeric(db_df, get_col(db_df, ACTUAL_COST_COLS))
    tokens = numeric(db_df, get_col(db_df, TOKEN_COLS))

    provider = summary.get("provider")
    if not provider and provider_col and not provider_source.empty:
        provider = provider_source[provider_col].dropna().astype(str).mode().iloc[0]

    model = summary.get("model_name")
    if not model and model_col and not model_source.empty:
        model = model_source[model_col].dropna().astype(str).mode().iloc[0]

    if actual_cost.empty and provider and "ollama" in str(provider).lower():
        actual_cost_total = 0.0
    else:
        actual_cost_total = float(actual_cost.sum()) if not actual_cost.empty else None

    return {
        "executions": len(db_df) if not db_df.empty else len(eval_df),
        "latency_avg": float(latency.mean()) if not latency.empty else summary.get("latency_avg_ms"),
        "latency_p95": float(latency.quantile(0.95)) if not latency.empty else summary.get("latency_p95_ms"),
        "errors": error_count if error_count is not None else summary.get("error_count"),
        "precision": float(precision.mean()) if not precision.empty else summary.get("precision_avg"),
        "consistency": float(consistency.mean()) if not consistency.empty else summary.get("consistency_avg"),
        "tokens": float(tokens.sum()) if not tokens.empty else None,
        "actual_cost": actual_cost_total,
        "sim_cost": float(sim_cost.sum()) if not sim_cost.empty else None,
        "provider": provider or "N/D",
        "model": model or "N/D",
    }


def compact_log_table(df: pd.DataFrame, limit: int = 12) -> pd.DataFrame:
    if df.empty:
        return df
    source = latest_rows(df, limit)
    columns = [
        get_col(source, TIMESTAMP_COLS),
        get_col(source, EXECUTION_COLS),
        get_col(source, QUERY_COLS),
        get_col(source, STATUS_COLS),
        get_col(source, ERROR_COLS),
        get_col(source, LATENCY_COLS),
        get_col(source, PROVIDER_COLS),
        get_col(source, MODEL_COLS),
    ]
    selected = [col for col in columns if col and col in source.columns]
    output = source[selected].copy() if selected else source.head(limit).copy()
    rename = {
        get_col(output, TIMESTAMP_COLS): "Fecha",
        get_col(output, EXECUTION_COLS): "Run",
        get_col(output, QUERY_COLS): "Consulta",
        get_col(output, STATUS_COLS): "Estado",
        get_col(output, ERROR_COLS): "Error",
        get_col(output, LATENCY_COLS): "Latencia",
        get_col(output, PROVIDER_COLS): "Proveedor",
        get_col(output, MODEL_COLS): "Modelo",
    }
    rename = {key: value for key, value in rename.items() if key}
    output = output.rename(columns=rename)
    if "Latencia" in output.columns:
        output["Latencia"] = pd.to_numeric(output["Latencia"], errors="coerce").apply(lambda v: fmt_ms(v) if pd.notna(v) else "N/D")
    return output
