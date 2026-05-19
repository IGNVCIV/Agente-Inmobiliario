"""
memoria.py — Memoria conversacional persistente.

Guarda el historial en un archivo JSON para que sobreviva entre sesiones.
Implementa ventana deslizante (mantiene los últimos N turnos).
"""

import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORIA_PATH = os.path.join(BASE_DIR, "memoria_conversacion.json")
MAX_TURNOS   = 10      # cuántos pares usuario/asistente recordar


# ══════════════════════════════════════════════════════════════
# GESTIÓN DE ARCHIVO
# ══════════════════════════════════════════════════════════════

def _cargar_estado() -> dict:
    if os.path.exists(MEMORIA_PATH):
        try:
            with open(MEMORIA_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"historial": [], "contexto_activo": None, "creado": str(datetime.now())}


def _guardar_estado(estado: dict):
    with open(MEMORIA_PATH, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)


# ══════════════════════════════════════════════════════════════
# CLASE MEMORIA
# ══════════════════════════════════════════════════════════════

class Memoria:
    """
    Maneja el historial de conversación del agente.

    Atributos persistidos:
      - historial:       lista de {"role", "content", "timestamp", "proveedor"}
      - contexto_activo: resumen del estado actual de búsqueda
    """

    def __init__(self):
        estado = _cargar_estado()
        self.historial: list[dict]    = estado.get("historial", [])
        self.contexto_activo: str|None = estado.get("contexto_activo")

    # ── AGREGAR MENSAJES ──────────────────────────────────────

    def agregar_usuario(self, texto: str):
        self.historial.append({
            "role":      "user",
            "content":   texto,
            "timestamp": str(datetime.now()),
        })
        self._recortar()
        self._persistir()

    def agregar_asistente(self, texto: str, proveedor: str = ""):
        self.historial.append({
            "role":      "assistant",
            "content":   texto,
            "proveedor": proveedor,
            "timestamp": str(datetime.now()),
        })
        self._recortar()
        self._persistir()

    # ── CONTEXTO ACTIVO ───────────────────────────────────────

    def set_contexto(self, resumen: str):
        """Guarda un resumen del resultado más reciente (para follow-ups)."""
        self.contexto_activo = resumen
        self._persistir()

    def get_contexto(self) -> str:
        return self.contexto_activo or ""

    # ── HISTORIAL PARA LLM ────────────────────────────────────

    def ultimos_turnos(self, n: int = 6) -> list[dict]:
        """Retorna los últimos n mensajes en formato {"role", "content"}."""
        recientes = self.historial[-n:]
        return [{"role": m["role"], "content": m["content"]} for m in recientes]

    def resumen_contexto(self) -> str:
        """
        Genera un string con el contexto conversacional para inyectar en prompts.
        Incluye los últimos 4 turnos + el contexto activo de búsqueda.
        """
        partes = []

        if self.contexto_activo:
            partes.append(f"[Búsqueda anterior: {self.contexto_activo}]")

        for m in self.historial[-4:]:
            rol = "Usuario" if m["role"] == "user" else "Asistente"
            partes.append(f"{rol}: {m['content'][:200]}")

        return "\n".join(partes) if partes else ""

    def extraer_preferencias(self) -> dict:
        """Extrae preferencias implícitas del historial conversacional."""
        comunas = set()
        precios = []
        dormitorios = []
        amenities = set()

        for mensaje in self.historial:
            texto = mensaje["content"].lower()

            # Detectar comunas simples por mención directa
            for comuna in [
                "las condes", "providencia", "vitacura", "ñuñoa", "santiago",
                "la reina", "lo barnechea", "macul", "san miguel", "recoleta",
                "peñalolén", "estación central", "estacion central",
            ]:
                if comuna in texto:
                    comunas.add(comuna.title())

            # Detectar rangos de precio máximos en UF
            if "uf" in texto:
                tokens = texto.replace("$", " ").replace("uf", " uf ").split()
                for i, token in enumerate(tokens):
                    if token.isdigit() and i + 1 < len(tokens) and tokens[i + 1] == "uf":
                        precios.append(int(token))

            # Detectar número de dormitorios
            for palabra in ["dormitorios", "dormitorio", "habitación", "habitaciones"]:
                if palabra in texto:
                    partes = texto.replace(".", "").replace(",", "").split()
                    for idx, item in enumerate(partes):
                        if item.isdigit() and idx + 1 < len(partes) and partes[idx + 1] in ["dormitorios", "dormitorio"]:
                            dormitorios.append(int(item))

            # Detectar amenities comunes
            for amenity in ["piscina", "gimnasio", "quincho", "bodega", "ascensor", "terraza", "jardín", "patio"]:
                if amenity in texto:
                    amenities.add(amenity)

        return {
            "comunas": sorted(comunas) if comunas else None,
            "precio_maximo_uf": max(precios) if precios else None,
            "dormitorios": max(dormitorios) if dormitorios else None,
            "amenities": sorted(amenities) if amenities else None,
        }

    def get_historial_para_llm(self, n_turnos: int = 5) -> list[dict]:
        """Retorna los últimos n_turnos en formato compatible con OpenAI messages."""
        recientes = self.historial[-n_turnos:]
        return [{"role": m["role"], "content": m["content"]} for m in recientes]

    def es_followup(self, query: str) -> bool:
        """Heurística simple para detectar consultas de seguimiento."""
        if not query:
            return False

        texto = query.lower().strip()
        palabras = texto.replace("?", "").replace(".", "").split()
        followup_keywords = [
            "ese", "esa", "esos", "también", "además", "qué más",
            "mismo", "anterior", "esa misma",
        ]

        if len(palabras) < 8:
            return True

        return any(keyword in texto for keyword in followup_keywords)

    # ── UTILIDADES ────────────────────────────────────────────

    def limpiar(self):
        """Borra toda la memoria."""
        self.historial = []
        self.contexto_activo = None
        self._persistir()
        print("🧹 Memoria borrada.")

    def mostrar_historial(self):
        if not self.historial:
            print("📭 Sin historial aún.")
            return
        print(f"\n📜 Historial ({len(self.historial)} mensajes):\n")
        for m in self.historial:
            rol   = "👤" if m["role"] == "user" else "🤖"
            ts    = m.get("timestamp", "")[:16]
            prov  = f" [{m.get('proveedor','')}]" if m.get("proveedor") else ""
            print(f"{rol} {ts}{prov}")
            print(f"   {m['content'][:120]}")
            print()

    # ── INTERNAL ──────────────────────────────────────────────

    def _recortar(self):
        """Mantiene solo los últimos MAX_TURNOS*2 mensajes."""
        limite = MAX_TURNOS * 2
        if len(self.historial) > limite:
            self.historial = self.historial[-limite:]

    def _persistir(self):
        _guardar_estado({
            "historial":       self.historial,
            "contexto_activo": self.contexto_activo,
            "actualizado":     str(datetime.now()),
        })
