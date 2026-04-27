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
