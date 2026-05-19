"""
db.py — Capa de datos: SQLite + actualización de UF.

Responsabilidades:
  - Inicializar la base de datos desde CSV
  - Ejecutar consultas SQL de forma segura
  - Actualizar el valor de la UF desde API externa
"""

import os
import sqlite3
import uuid
import pandas as pd
import requests
from datetime import datetime, timedelta
from typing import Optional

from .data_pipeline import DataPipeline

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "backend", "propiedades.db")
CSV_PATH = os.path.join(BASE_DIR, "data", "processed", "propiedades_detalle.csv")

SCHEMA = """
CREATE TABLE IF NOT EXISTS propiedades (
    id            INTEGER PRIMARY KEY,
    id_fuente     TEXT,
    titulo        TEXT,
    moneda        TEXT DEFAULT 'UF',
    precio_valor  REAL,
    precio_uf     REAL,
    ubicacion_raw TEXT,
    comuna        TEXT,
    dormitorios   INTEGER,
    banos         INTEGER,
    metros        REAL,
    descripcion   TEXT,
    amenities     TEXT,
    rag_text      TEXT,
    link          TEXT
);

CREATE TABLE IF NOT EXISTS uf (
    fecha TEXT PRIMARY KEY,
    valor REAL
);

CREATE TABLE IF NOT EXISTS busquedas_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    consulta  TEXT,
    sql_gen   TEXT,
    n_results INTEGER,
    proveedor TEXT
);

CREATE TABLE IF NOT EXISTS favoritos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    propiedad_id  INTEGER,
    nota          TEXT,
    guardado_en   TEXT,
    sesion_id     TEXT
);
"""

# ══════════════════════════════════════════════════════════════
# INICIALIZACIÓN
# ══════════════════════════════════════════════════════════════

def inicializar_db(csv_path: str = CSV_PATH, db_path: str = DB_PATH):
    """Crea la DB desde cero y carga el CSV."""
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)

    df = pd.read_csv(csv_path)
    df = df.drop(columns=["error"], errors="ignore")

    uf = actualizar_uf(conn)
    pipeline = DataPipeline(uf_value=uf)
    df_limpio = pipeline.clean_dataframe(df)
    df_limpio.to_sql("propiedades", conn, if_exists="replace", index=False)

    conn.close()

    print(f"✅ DB inicializada: {len(df)} propiedades | UF = ${uf:,.2f}")
    return len(df), uf


def obtener_conexion(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def cargar_propiedades_db(db_path: str = DB_PATH) -> pd.DataFrame:
    """Retorna todas las propiedades almacenadas en SQLite como DataFrame."""
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM propiedades", conn)
    conn.close()
    return df


def preparar_propiedades_para_rag(db_path: str = DB_PATH, uf_value: Optional[float] = None) -> pd.DataFrame:
    """Limpia y normaliza las propiedades para construcción de corpus RAG."""
    df = cargar_propiedades_db(db_path)
    pipeline = DataPipeline(uf_value=uf_value)
    return pipeline.clean_dataframe(df)


# ══════════════════════════════════════════════════════
# EJECUCIÓN SQL
# ══════════════════════════════════════

OPERACIONES_PROHIBIDAS = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE"]


def ejecutar_sql(sql: str, db_path: str = DB_PATH) -> tuple[list[dict], Optional[str]]:
    """
    Ejecuta SQL de forma segura.
    Retorna (filas, error) — error es None si fue exitoso.
    """
    sql_upper = sql.upper()
    for kw in OPERACIONES_PROHIBIDAS:
        if kw in sql_upper:
            return [], f"Operación prohibida: {kw}"

    # Asegurar LIMIT
    if "LIMIT" not in sql_upper:
        sql = sql.rstrip(";") + " LIMIT 10;"

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur  = conn.execute(sql)
        filas = [dict(row) for row in cur.fetchall()]
        conn.close()
        return filas, None
    except sqlite3.Error as e:
        return [], str(e)


# ══════════════════════════════════════════════════════════════
# VALOR UF
# ══════════════════════════════════════════════════════════════

def actualizar_uf(conn: Optional[sqlite3.Connection] = None) -> float:
    """
    Obtiene el valor de la UF desde mindicador.cl y lo persiste en la DB.
    Usa caché: no reconsulta si ya tiene el valor de hoy.
    """
    close_after = conn is None
    if conn is None:
        conn = sqlite3.connect(DB_PATH)

    hoy = datetime.today().strftime("%Y-%m-%d")

    # ¿Ya tenemos el valor de hoy?
    cur = conn.execute("SELECT valor FROM uf WHERE fecha = ?", (hoy,))
    row = cur.fetchone()
    if row:
        if close_after:
            conn.close()
        return float(row[0])

    # Consultar API
    valor = _fetch_uf_api()

    conn.execute(
        "INSERT OR REPLACE INTO uf (fecha, valor) VALUES (?, ?)",
        (hoy, valor)
    )
    conn.commit()

    if close_after:
        conn.close()

    print(f"💱 UF actualizada: ${valor:,.2f} ({hoy})")
    return valor


def _fetch_uf_api() -> float:
    """Consulta mindicador.cl. Retorna valor de referencia si falla."""
    try:
        resp = requests.get("https://mindicador.cl/api/uf", timeout=5)
        data = resp.json()
        return float(data["serie"][0]["valor"])
    except Exception:
        # Fallback: valor histórico de referencia
        return 38_800.0


def get_uf_actual(db_path: str = DB_PATH) -> float:
    """Retorna el último valor de UF disponible en la DB."""
    conn = sqlite3.connect(db_path)
    cur  = conn.execute("SELECT valor FROM uf ORDER BY fecha DESC LIMIT 1")
    row  = cur.fetchone()
    conn.close()
    return float(row[0]) if row else 38_800.0


# ══════════════════════════════════════════════════════════════
# LOGGING DE BÚSQUEDAS
# ══════════════════════════════════════════════════════════════

def registrar_busqueda(
    consulta: str,
    sql_gen: str,
    n_results: int,
    proveedor: str,
    db_path: str = DB_PATH,
):
    """Guarda cada búsqueda para análisis y debug."""
    try:
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO busquedas_log (timestamp, consulta, sql_gen, n_results, proveedor) "
            "VALUES (?, ?, ?, ?, ?)",
            (str(datetime.now()), consulta, sql_gen, n_results, proveedor),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # El log no debe interrumpir el flujo principal


def historial_busquedas(n: int = 10, db_path: str = DB_PATH) -> list[dict]:
    """Retorna las últimas n búsquedas registradas."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur  = conn.execute(
        "SELECT * FROM busquedas_log ORDER BY id DESC LIMIT ?", (n,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def buscar_propiedades(
    cantidad: int = 5,
    comuna: str | None = None,
    min_dormitorios: int | None = None,
    min_banos: int | None = None,
    precio_min: float | None = None,
    precio_max: float | None = None,
    texto: str | None = None,
    db_path: str = DB_PATH,
) -> list[dict]:
    conn = obtener_conexion(db_path)
    filtros = []
    params = []

    if comuna:
        filtros.append("LOWER(comuna) LIKE ?")
        params.append(f"%{comuna.lower()}%")
    if min_dormitorios is not None:
        filtros.append("dormitorios >= ?")
        params.append(min_dormitorios)
    if min_banos is not None:
        filtros.append("banos >= ?")
        params.append(min_banos)
    if precio_min is not None:
        filtros.append("precio_uf >= ?")
        params.append(precio_min)
    if precio_max is not None:
        filtros.append("precio_uf <= ?")
        params.append(precio_max)
    if texto:
        texto_param = f"%{texto.lower()}%"
        filtros.append(
            "(LOWER(titulo) LIKE ? OR LOWER(descripcion) LIKE ? OR LOWER(amenities) LIKE ? OR LOWER(ubicacion_raw) LIKE ?)"
        )
        params.extend([texto_param] * 4)

    where = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    sql = f"SELECT * FROM propiedades {where} ORDER BY precio_valor ASC LIMIT ?"
    params.append(cantidad)

    cur = conn.execute(sql, params)
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def guardar_favorito(propiedad_id: int, nota: str = "", db_path: str = DB_PATH) -> dict:
    """Guarda una propiedad como favorita en la base de datos."""
    try:
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS favoritos ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "propiedad_id INTEGER, "
            "nota TEXT, "
            "guardado_en TEXT, "
            "sesion_id TEXT"
            ")"
        )
        sesion_id = str(uuid.uuid4())
        guardado_en = str(datetime.now())
        conn.execute(
            "INSERT INTO favoritos (propiedad_id, nota, guardado_en, sesion_id) VALUES (?, ?, ?, ?)",
            (propiedad_id, nota, guardado_en, sesion_id),
        )
        conn.commit()
        conn.close()
        return {"success": True, "mensaje": "Propiedad guardada como favorita correctamente."}
    except Exception as e:
        return {"success": False, "mensaje": f"Error guardando favorito: {str(e)}"}


def listar_favoritos(db_path: str = DB_PATH) -> list[dict]:
    """Retorna los favoritos recientes con información básica de la propiedad."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    sql = (
        "SELECT f.id AS favorito_id, f.propiedad_id, f.nota, f.guardado_en, "
        "p.titulo, p.precio_uf, p.precio_valor, p.comuna "
        "FROM favoritos f "
        "LEFT JOIN propiedades p ON p.id = f.propiedad_id "
        "ORDER BY f.id DESC LIMIT 10"
    )
    cur = conn.execute(sql)
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


# ══════════════════════════════════════════════════════════════════════
# ESTADÍSTICAS RÁPIDAS
# ══════════════════════════════════════════════════════

def stats_db(db_path: str = DB_PATH) -> dict:
    conn = sqlite3.connect(db_path)
    stats = {}

    for query, key in [
        ("SELECT COUNT(*) FROM propiedades",         "total_propiedades"),
        ("SELECT COUNT(*) FROM uf",                  "registros_uf"),
        ("SELECT COUNT(*) FROM busquedas_log",       "total_busquedas"),
        ("SELECT AVG(precio_valor) FROM propiedades", "precio_promedio_uf"),
        ("SELECT MIN(precio_valor) FROM propiedades", "precio_min_uf"),
        ("SELECT MAX(precio_valor) FROM propiedades", "precio_max_uf"),
    ]:
        cur = conn.execute(query)
        stats[key] = cur.fetchone()[0]

    conn.close()
    return stats
