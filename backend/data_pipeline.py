import os
import re
from typing import Any, Dict, List, Optional

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_UF = 38800.0

COMUNA_ALIAS = {
    "las condes": "Las Condes",
    "vitacura": "Vitacura",
    "providencia": "Providencia",
    "ñuñoa": "Ñuñoa",
    "nunoa": "Ñuñoa",
    "santiago": "Santiago",
    "la reina": "La Reina",
    "lo barnechea": "Lo Barnechea",
    "macul": "Macul",
    "san miguel": "San Miguel",
    "estacion central": "Estación Central",
    "estación central": "Estación Central",
    "independencia": "Independencia",
    "recoleta": "Recoleta",
    "peñalolén": "Peñalolén",
    "penalolen": "Peñalolén",
}

AMENITY_MAP = {
    "piscina": ["piscina"],
    "gimnasio": ["gimnasio", "gym"],
    "quincho": ["quincho"],
    "estacionamiento": ["estacionamiento", "parking"],
    "bodega": ["bodega"],
    "ascensor": ["ascensor", "elevador"],
    "conserjeria": ["conserjería", "conserjeria", "portería", "portería"],
    "seguridad": ["seguridad", "vigilancia"],
    "terraza": ["terraza"],
    "jardín": ["jardín", "jardin"],
    "patio": ["patio"],
    "baño visita": ["baño de visita", "baño visita"],
}

NOISE_PATTERNS = [
    r"(?i)whatsapp.*$",
    r"(?i)solicitar visita.*$",
    r"(?i)responde sus consultas.*$",
    r"(?i)av[ií]sanos.*$",
    r"(?i)consulta por.*$",
    r"(?i)tienda oficial.*$",
]

PRICE_CLP_KEYWORDS = ["clp", "pesos", "$", "chile"]


def limpiar_texto(texto: Optional[str]) -> str:
    if texto is None:
        return ""
    value = str(texto).strip()
    value = re.sub(r"\s+", " ", value)
    return value


def normalizar_numero(valor: Any) -> Optional[float]:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None

    texto = limpiar_texto(valor)
    texto = texto.replace("$", "").replace("CLP", "").replace("clp", "").strip()
    texto = texto.replace(" ", "")

    if not texto:
        return None

    # 1.234,56 -> 1234.56
    if "." in texto and "," in texto:
        texto = texto.replace(".", "").replace(",", ".")

    # 12.500 -> 12500
    if "." in texto and "," not in texto:
        texto = texto.replace(".", "")

    texto = texto.replace(",", ".")

    try:
        if "." in texto:
            return float(texto)
        return float(int(texto))
    except ValueError:
        return None


def normalizar_moneda(moneda: Any) -> Optional[str]:
    if moneda is None:
        return None
    texto = limpiar_texto(moneda).lower()
    if not texto:
        return None
    if "uf" in texto:
        return "UF"
    if any(keyword in texto for keyword in PRICE_CLP_KEYWORDS):
        return "CLP"
    return texto.upper()


def normalize_precio_uf(precio_valor: Any, moneda: Any, uf_val: float = DEFAULT_UF) -> Optional[float]:
    precio = normalizar_numero(precio_valor)
    if precio is None:
        return None

    moneda_norm = normalizar_moneda(moneda)

    if moneda_norm == "UF":
        return round(precio, 2)

    if moneda_norm == "CLP":
        return round(precio / uf_val, 2)

    if precio > 100000:
        return round(precio / uf_val, 2)

    return round(precio, 2)


def normalize_comuna(comuna: Any, ubicacion_raw: Any) -> Optional[str]:
    if comuna:
        texto = limpiar_texto(comuna).lower()
        return COMUNA_ALIAS.get(texto, texto.title())

    if ubicacion_raw:
        texto = limpiar_texto(ubicacion_raw).lower()
        for key, value in COMUNA_ALIAS.items():
            if key in texto:
                return value

    return None


def normalize_ubicacion(ubicacion_raw: Any) -> Optional[str]:
    if not ubicacion_raw:
        return None

    texto = limpiar_texto(ubicacion_raw)
    texto = texto.replace("/", ", ").replace(" - ", ", ")
    texto = re.sub(r"\s*,\s*", ", ", texto)
    return texto.title()


def normalize_description(texto: Any) -> Optional[str]:
    if texto is None:
        return None

    resultado = limpiar_texto(texto)
    for patron in NOISE_PATTERNS:
        resultado = re.sub(patron, "", resultado)

    resultado = re.sub(r"\s+", " ", resultado).strip()
    return resultado if resultado else None


def normalize_amenities(amenities: Any) -> Optional[str]:
    if amenities is None:
        return None

    texto = limpiar_texto(amenities).lower()
    tokens = re.split(r"[,;/]|\|", texto)
    resultados = set()

    for token in tokens:
        token = limpiar_texto(token).lower()
        for canon, alias_list in AMENITY_MAP.items():
            if any(alias in token for alias in alias_list):
                resultados.add(canon)

    return ", ".join(sorted(resultados)) if resultados else None


def build_rag_text(record: Dict[str, Any]) -> str:
    partes: List[str] = []

    titulo = record.get("titulo")
    if titulo:
        partes.append(f"Título: {titulo}.")

    comuna = record.get("comuna")
    ubicacion = record.get("ubicacion_raw")
    if comuna:
        partes.append(f"Comuna: {comuna}.")
    elif ubicacion:
        partes.append(f"Ubicación: {ubicacion}.")

    dormitorios = record.get("dormitorios")
    if dormitorios is not None:
        partes.append(f"Dormitorios: {dormitorios}.")

    banos = record.get("banos")
    if banos is not None:
        partes.append(f"Baños: {banos}.")

    metros = record.get("metros")
    if metros is not None:
        partes.append(f"Metros cuadrados: {metros}.")

    precio_uf = record.get("precio_uf")
    if precio_uf is not None:
        partes.append(f"Precio: {precio_uf} UF.")

    amenities = record.get("amenities")
    if amenities:
        partes.append(f"Amenities: {amenities}.")

    descripcion = record.get("descripcion")
    if descripcion:
        partes.append(f"Descripción: {descripcion}.")

    return " ".join(partes).strip()


class DataPipeline:
    """Pipeline de normalización y limpieza de propiedades para RAG."""

    def __init__(self, uf_value: Optional[float] = None):
        self.uf_value = uf_value or DEFAULT_UF

    def clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.copy()

        df["titulo"] = df.get("titulo", pd.Series(dtype="string")).apply(limpiar_texto)
        df["descripcion"] = df.get("descripcion", pd.Series(dtype="string")).apply(normalize_description)
        df["ubicacion_raw"] = df.get("ubicacion_raw", pd.Series(dtype="string")).apply(normalize_ubicacion)
        df["comuna"] = df.apply(
            lambda row: normalize_comuna(row.get("comuna"), row.get("ubicacion_raw")), axis=1
        )
        df["amenities"] = df.get("amenities", pd.Series(dtype="string")).apply(normalize_amenities)

        for campo in ["dormitorios", "banos"]:
            if campo in df.columns:
                df[campo] = df[campo].apply(normalizar_numero).apply(lambda v: int(v) if v is not None else None)

        if "metros" in df.columns:
            df["metros"] = df["metros"].apply(normalizar_numero)

        df["precio_valor"] = df.get("precio_valor", pd.Series(dtype="float")).apply(normalizar_numero)
        df["moneda"] = df.get("moneda", pd.Series(dtype="string")).apply(normalizar_moneda)
        df["precio_uf"] = df.apply(
            lambda row: normalize_precio_uf(row.get("precio_valor"), row.get("moneda"), self.uf_value),
            axis=1,
        )

        df["rag_text"] = df.apply(build_rag_text, axis=1)
        return df

    def prepare_rag_documents(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        cleaned = self.clean_dataframe(df)
        docs: List[Dict[str, Any]] = []

        for _, row in cleaned.iterrows():
            metadata = {
                "id": row.get("id"),
                "titulo": row.get("titulo"),
                "comuna": row.get("comuna"),
                "precio_uf": row.get("precio_uf"),
                "link": row.get("link"),
            }
            docs.append({"page_content": row.get("rag_text", ""), "metadata": metadata})

        return docs

    def export_clean_csv(self, df: pd.DataFrame, output_path: str) -> str:
        cleaned = self.clean_dataframe(df)
        cleaned.to_csv(output_path, index=False, encoding="utf-8-sig")
        return output_path
