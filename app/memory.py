"""
memory.py — Memoria conversacional persistente para el agente inmobiliario.

La memoria no intenta reemplazar una base de datos de clientes ni un CRM.
Su objetivo es mantener continuidad conversacional de corto plazo:
- recordar preferencias inmobiliarias mencionadas en turnos recientes;
- detectar consultas de seguimiento;
- entregar contexto útil al RAG y al LLM local;
- evitar persistir datos personales sensibles en texto plano.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
MEMORIA_PATH = Path(os.getenv("MEMORY_PATH", BASE_DIR / "memoria_conversacion.json"))
MAX_TURNOS = int(os.getenv("MEMORY_MAX_TURNS", "12"))
MAX_CONTENT_CHARS = int(os.getenv("MEMORY_MAX_MESSAGE_CHARS", "1200"))
MAX_CONTEXT_CHARS = int(os.getenv("MEMORY_MAX_CONTEXT_CHARS", "1800"))


# ══════════════════════════════════════════════════════════════
# NORMALIZACIÓN Y REDACCIÓN DE DATOS SENSIBLES
# ══════════════════════════════════════════════════════════════

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
RUT_RE = re.compile(r"\b\d{1,2}\.?\d{3}\.?\d{3}-?[\dkK]\b")
PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?56\s*)?(?:9\s*)?(?:\d[\s.-]*){8}(?!\d)"
)
ADDRESS_RE = re.compile(
    r"\b(?:calle|av\.?|avenida|pasaje|camino|condominio|depto|departamento)\s+"
    r"[\wáéíóúñü\s.-]{2,70}\s+\d{1,6}\b",
    re.IGNORECASE,
)

NUMBER_WORDS = {
    "un": 1,
    "una": 1,
    "uno": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
}

COMUNAS = [
    "las condes",
    "providencia",
    "vitacura",
    "ñuñoa",
    "nunoa",
    "santiago",
    "la reina",
    "lo barnechea",
    "macul",
    "san miguel",
    "recoleta",
    "peñalolén",
    "penalolen",
    "estación central",
    "estacion central",
    "independencia",
    "quinta normal",
    "la florida",
    "maipú",
    "maipu",
    "puente alto",
    "san joaquín",
    "san joaquin",
    "providencia",
]

AMENITIES = {
    "piscina": ["piscina"],
    "gimnasio": ["gimnasio", "gym"],
    "quincho": ["quincho", "parrilla", "asado"],
    "bodega": ["bodega"],
    "ascensor": ["ascensor"],
    "terraza": ["terraza", "balcon", "balcón"],
    "jardín": ["jardin", "jardín", "patio", "área verde", "area verde"],
    "estacionamiento": ["estacionamiento", "parking", "garage"],
    "metro": ["metro", "estación", "estacion"],
    "mascotas": ["mascota", "mascotas", "pet friendly"],
    "seguridad": ["conserjería", "conserjeria", "seguridad", "control de acceso"],
    "vista": ["vista", "vista despejada", "vista al mar", "vista cordillera"],
    "amoblado": ["amoblado", "equipado"],
}

PROPERTY_TYPES = {
    "departamento": ["departamento", "depto", "dpto"],
    "casa": ["casa"],
    "oficina": ["oficina"],
    "terreno": ["terreno", "sitio"],
}

OPERATION_TYPES = {
    "venta": ["comprar", "compra", "venta", "vendo"],
    "arriendo": ["arrendar", "arriendo", "renta", "alquiler"],
}

FOLLOWUP_MARKERS = [
    "y ",
    "pero",
    "tambien",
    "también",
    "ademas",
    "además",
    "ahora",
    "mejor",
    "parecido",
    "similar",
    "ese",
    "esa",
    "esos",
    "esas",
    "la anterior",
    "el anterior",
    "otra opción",
    "otra opcion",
    "qué más",
    "que más",
    "cuál conviene",
    "cual conviene",
    "más barato",
    "mas barato",
    "más grande",
    "mas grande",
    "con piscina",
    "sin piscina",
    "cerca del metro",
]


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _normalize(text: str) -> str:
    text = text or ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower().strip()


def _title_comuna(comuna: str) -> str:
    comuna = comuna.replace("nunoa", "ñuñoa").replace("penalolen", "peñalolén")
    return " ".join(part.capitalize() for part in comuna.split())


def _sanitize_text(texto: str) -> str:
    """Reduce riesgo de persistir RUT, correo, teléfono o dirección exacta."""
    if texto is None:
        return ""

    sanitized = str(texto)[:MAX_CONTENT_CHARS]
    sanitized = EMAIL_RE.sub("[correo omitido]", sanitized)
    sanitized = RUT_RE.sub("[rut omitido]", sanitized)
    sanitized = PHONE_RE.sub("[teléfono omitido]", sanitized)
    sanitized = ADDRESS_RE.sub("[dirección omitida]", sanitized)
    return sanitized.strip()


def _parse_int(value: str) -> int | None:
    if not value:
        return None
    cleaned = re.sub(r"[^0-9]", "", str(value))
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


# ══════════════════════════════════════════════════════════════
# GESTIÓN DE ARCHIVO
# ══════════════════════════════════════════════════════════════


def _cargar_estado() -> dict:
    if MEMORIA_PATH.exists():
        try:
            with MEMORIA_PATH.open("r", encoding="utf-8") as f:
                estado = json.load(f)
                if isinstance(estado, dict):
                    return estado
        except (json.JSONDecodeError, OSError):
            pass

    return {
        "historial": [],
        "contexto_activo": None,
        "preferencias_cache": {},
        "creado": _now_iso(),
    }


def _guardar_estado(estado: dict):
    MEMORIA_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = MEMORIA_PATH.with_suffix(MEMORIA_PATH.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)
    tmp_path.replace(MEMORIA_PATH)


# ══════════════════════════════════════════════════════════════
# CLASE MEMORIA
# ══════════════════════════════════════════════════════════════


class Memoria:
    """
    Maneja memoria conversacional local de corto plazo.

    Guarda mensajes sanitizados, preferencias inferidas y un contexto activo
    para consultas de seguimiento. No registra datos personales de contacto
    como RUT, correo, teléfono o direcciones exactas.
    """

    def __init__(self):
        estado = _cargar_estado()
        self.historial: list[dict] = estado.get("historial", []) or []
        self.contexto_activo: str | None = estado.get("contexto_activo")
        self.preferencias_cache: dict = estado.get("preferencias_cache", {}) or {}

    # ── AGREGAR MENSAJES ──────────────────────────────────────

    def agregar_usuario(self, texto: str):
        self._agregar_mensaje("user", texto)

    def agregar_asistente(self, texto: str, proveedor: str = ""):
        self._agregar_mensaje("assistant", texto, proveedor=proveedor)

    def _agregar_mensaje(self, role: str, texto: str, proveedor: str = ""):
        content = _sanitize_text(texto)
        if not content:
            return

        mensaje = {
            "role": role,
            "content": content,
            "timestamp": _now_iso(),
        }
        if proveedor:
            mensaje["proveedor"] = _sanitize_text(proveedor)[:80]

        self.historial.append(mensaje)
        self._recortar()
        self.preferencias_cache = self.extraer_preferencias(recalcular=True)
        self._persistir()

    # ── CONTEXTO ACTIVO ───────────────────────────────────────

    def set_contexto(self, resumen: str):
        """Guarda un resumen breve del resultado más reciente para follow-ups."""
        self.contexto_activo = _sanitize_text(resumen)[:MAX_CONTEXT_CHARS]
        self._persistir()

    def get_contexto(self) -> str:
        return self.contexto_activo or ""

    def actualizar_contexto_busqueda(self, query: str, propiedades: list[dict]):
        """Crea un contexto activo compacto desde la última búsqueda realizada."""
        query = _sanitize_text(query)

        if not propiedades:
            self.set_contexto(f"Última búsqueda sin resultados claros: {query}")
            return

        resumenes = []
        for idx, prop in enumerate(propiedades[:3], start=1):
            titulo = prop.get("titulo") or "Propiedad sin título"
            comuna = prop.get("comuna") or prop.get("ubicacion_raw") or "comuna no especificada"
            precio = prop.get("precio_uf") or prop.get("precio_valor") or "precio no especificado"
            dormitorios = prop.get("dormitorios") or prop.get("dormitorios_min") or "N/D"
            banos = prop.get("banos") or prop.get("banos_min") or "N/D"
            resumenes.append(
                f"{idx}) {titulo} | {comuna} | {precio} UF | {dormitorios} dorm | {banos} baños"
            )

        self.set_contexto(
            "Última búsqueda: "
            f"{query}. Opciones recuperadas: "
            + " ; ".join(_sanitize_text(item) for item in resumenes)
        )

    # ── HISTORIAL PARA LLM ────────────────────────────────────

    def ultimos_turnos(self, n: int = 6) -> list[dict]:
        recientes = self.historial[-n:]
        return [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in recientes]

    def get_historial_para_llm(self, n_turnos: int = 6) -> list[dict]:
        return self.ultimos_turnos(n_turnos)

    def resumen_contexto(self) -> str:
        """
        Genera contexto conversacional compacto para prompts/RAG.

        Incluye:
        - búsqueda anterior;
        - preferencias inferidas;
        - últimos turnos relevantes.
        """
        partes: list[str] = []

        if self.contexto_activo:
            partes.append(f"[Contexto de búsqueda anterior]\n{self.contexto_activo}")

        preferencias = self.extraer_preferencias()
        pref_text = self.formatear_preferencias(preferencias)
        if pref_text:
            partes.append(f"[Preferencias recordadas]\n{pref_text}")

        if self.historial:
            turnos = []
            for m in self.historial[-6:]:
                rol = "Usuario" if m.get("role") == "user" else "Asistente"
                contenido = m.get("content", "")[:280]
                turnos.append(f"{rol}: {contenido}")
            partes.append("[Últimos turnos]\n" + "\n".join(turnos))

        contexto = "\n\n".join(partes).strip()
        return contexto[:MAX_CONTEXT_CHARS]

    def contexto_para_rag(self, query: str) -> str:
        """Contexto más corto para enriquecer consultas RAG sin meter demasiado ruido."""
        partes = []
        if self.es_followup(query) and self.contexto_activo:
            partes.append(self.contexto_activo)

        preferencias = self.extraer_preferencias()
        pref_text = self.formatear_preferencias(preferencias)
        if pref_text:
            partes.append(f"Preferencias: {pref_text}")

        return "\n".join(partes)[:900]

    # ── PREFERENCIAS E INTENCIÓN ──────────────────────────────

    def extraer_preferencias(self, recalcular: bool = False) -> dict:
        """Extrae preferencias inmobiliarias desde el historial sanitizado."""
        if self.preferencias_cache and not recalcular:
            return dict(self.preferencias_cache)

        textos = [m.get("content", "") for m in self.historial if m.get("role") == "user"]
        texto = "\n".join(textos)
        normalizado = _normalize(texto)

        comunas = self._extract_comunas(normalizado)
        precio_min, precio_max = self._extract_precios_uf(normalizado)
        dormitorios = self._extract_numero_asociado(normalizado, ["dorm", "habitacion", "habitaciones"])
        banos = self._extract_numero_asociado(normalizado, ["bano", "banos", "baño", "baños"])
        amenities = self._extract_amenities(normalizado)
        avoid_amenities = self._extract_avoid_amenities(normalizado)
        tipo_propiedad = self._extract_catalog_value(normalizado, PROPERTY_TYPES)
        tipo_operacion = self._extract_catalog_value(normalizado, OPERATION_TYPES)

        preferencias = {
            "comunas": sorted(comunas) if comunas else None,
            "precio_minimo_uf": precio_min,
            "precio_maximo_uf": precio_max,
            "dormitorios": dormitorios,
            "banos": banos,
            "amenities": sorted(amenities) if amenities else None,
            "evitar_amenities": sorted(avoid_amenities) if avoid_amenities else None,
            "tipo_propiedad": tipo_propiedad,
            "tipo_operacion": tipo_operacion,
            "moneda_preferida": "UF" if "uf" in normalizado else None,
        }

        return preferencias

    def formatear_preferencias(self, preferencias: dict | None = None) -> str:
        preferencias = preferencias or self.extraer_preferencias()
        partes = []

        if preferencias.get("tipo_operacion"):
            partes.append(f"operación: {preferencias['tipo_operacion']}")
        if preferencias.get("tipo_propiedad"):
            partes.append(f"tipo: {preferencias['tipo_propiedad']}")
        if preferencias.get("comunas"):
            partes.append(f"comunas: {', '.join(preferencias['comunas'])}")
        if preferencias.get("dormitorios"):
            partes.append(f"dormitorios mínimos: {preferencias['dormitorios']}")
        if preferencias.get("banos"):
            partes.append(f"baños mínimos: {preferencias['banos']}")
        if preferencias.get("precio_minimo_uf"):
            partes.append(f"presupuesto mínimo: {preferencias['precio_minimo_uf']} UF")
        if preferencias.get("precio_maximo_uf"):
            partes.append(f"presupuesto máximo: {preferencias['precio_maximo_uf']} UF")
        if preferencias.get("amenities"):
            partes.append(f"características deseadas: {', '.join(preferencias['amenities'])}")
        if preferencias.get("evitar_amenities"):
            partes.append(f"evitar: {', '.join(preferencias['evitar_amenities'])}")

        return "; ".join(partes)

    def es_followup(self, query: str) -> bool:
        """Detecta si la consulta depende de turnos anteriores."""
        if not query:
            return False

        texto = _normalize(query)
        palabras = texto.replace("?", " ").replace(".", " ").split()

        # Continuaciones explícitas: "y ahora...", "también...", "ese...".
        if any(marker in texto for marker in FOLLOWUP_MARKERS):
            return True

        # Preguntas muy cortas con verbos comparativos suelen depender del contexto.
        short_contextual_terms = [
            "cuanto", "precio", "vale", "conviene", "mejor", "mas", "menos", "similar"
        ]
        if len(palabras) <= 5 and any(term in texto for term in short_contextual_terms):
            return True

        # Una búsqueda corta pero autónoma no se marca automáticamente como follow-up.
        standalone_terms = ["depto", "departamento", "casa", "arriendo", "venta", "uf"]
        if len(palabras) <= 6 and any(term in texto for term in standalone_terms):
            return False

        return False

    def detectar_intencion(self, query: str) -> str:
        """Clasifica una intención conversacional simple para el planner."""
        texto = _normalize(query)
        if any(term in texto for term in ["guardar", "favorito", "favorita"]):
            return "favoritos"
        if any(term in texto for term in ["comparar", "conviene", "mejor opcion", "mejor opción"]):
            return "comparacion"
        if self.es_followup(query):
            return "seguimiento"
        if any(term in texto for term in ["busco", "quiero", "necesito", "tienes", "encuentra"]):
            return "busqueda"
        return "general"

    # ── UTILIDADES ────────────────────────────────────────────

    def limpiar(self):
        """Borra toda la memoria local."""
        self.historial = []
        self.contexto_activo = None
        self.preferencias_cache = {}
        self._persistir()
        print("🧹 Memoria borrada.")

    def mostrar_historial(self):
        if not self.historial:
            print("📭 Sin historial aún.")
            return
        print(f"\n📜 Historial ({len(self.historial)} mensajes):\n")
        for m in self.historial:
            rol = "👤" if m.get("role") == "user" else "🤖"
            ts = m.get("timestamp", "")[:16]
            prov = f" [{m.get('proveedor','')}]" if m.get("proveedor") else ""
            print(f"{rol} {ts}{prov}")
            print(f"   {m.get('content','')[:140]}")
            print()

    # ── EXTRACTORES INTERNOS ──────────────────────────────────

    def _extract_comunas(self, texto: str) -> set[str]:
        comunas = set()
        for comuna in COMUNAS:
            if _normalize(comuna) in texto:
                comunas.add(_title_comuna(comuna))
        return comunas

    def _extract_precios_uf(self, texto: str) -> tuple[int | None, int | None]:
        precios = []
        for match in re.finditer(r"(\d{1,3}(?:[\.]\d{3})*|\d+)\s*uf", texto):
            value = _parse_int(match.group(1))
            if value:
                precios.append(value)

        if not precios:
            return None, None

        precio_min = None
        precio_max = max(precios)

        min_match = re.search(r"(?:desde|minimo|mínimo)\s*(\d{1,3}(?:[\.]\d{3})*|\d+)\s*uf", texto)
        if min_match:
            precio_min = _parse_int(min_match.group(1))

        max_match = re.search(
            r"(?:hasta|maximo|máximo|menos de|no mas de|no más de|tope|presupuesto)\s*"
            r"(\d{1,3}(?:[\.]\d{3})*|\d+)\s*uf",
            texto,
        )
        if max_match:
            precio_max = _parse_int(max_match.group(1)) or precio_max

        return precio_min, precio_max

    def _extract_numero_asociado(self, texto: str, keywords: list[str]) -> int | None:
        keyword_pattern = "|".join(re.escape(_normalize(k)) for k in keywords)

        for match in re.finditer(rf"(\d+)\s*(?:{keyword_pattern})", texto):
            value = _parse_int(match.group(1))
            if value:
                return value

        for word, value in NUMBER_WORDS.items():
            if re.search(rf"\b{word}\s+(?:{keyword_pattern})", texto):
                return value

        return None

    def _extract_amenities(self, texto: str) -> set[str]:
        found = set()
        for amenity, aliases in AMENITIES.items():
            if any(_normalize(alias) in texto for alias in aliases):
                found.add(amenity)
        return found

    def _extract_avoid_amenities(self, texto: str) -> set[str]:
        avoid = set()
        for amenity, aliases in AMENITIES.items():
            for alias in aliases:
                alias_norm = _normalize(alias)
                if re.search(rf"\b(?:sin|no quiero|no necesito|evitar)\s+.{0,20}\b{re.escape(alias_norm)}\b", texto):
                    avoid.add(amenity)
        return avoid

    def _extract_catalog_value(self, texto: str, catalog: dict[str, list[str]]) -> str | None:
        for value, aliases in catalog.items():
            if any(_normalize(alias) in texto for alias in aliases):
                return value
        return None

    # ── INTERNAL ──────────────────────────────────────────────

    def _recortar(self):
        limite = MAX_TURNOS * 2
        if len(self.historial) > limite:
            self.historial = self.historial[-limite:]

    def _persistir(self):
        _guardar_estado(
            {
                "historial": self.historial,
                "contexto_activo": self.contexto_activo,
                "preferencias_cache": self.preferencias_cache,
                "actualizado": _now_iso(),
            }
        )
