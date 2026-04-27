import ast
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "system_prompt.txt"


class LLMService:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("GITHUB_TOKEN"))
        self.system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        if SYSTEM_PROMPT_PATH.exists():
            return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
        return (
            "Eres un asesor virtual experto en propiedades inmobiliarias. "
            "Extrae criterios de usuario y genera respuestas estructuradas basadas en datos reales."
        )

    def _parse_json(self, content: str) -> dict:
        content = content.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            try:
                return ast.literal_eval(content)
            except Exception:
                return {}

    def extract_criteria(self, query: str) -> dict:
        prompt = (
            "Extrae los criterios de búsqueda de la consulta del usuario sobre propiedades en Chile. "
            "Responde únicamente con un JSON válido que contenga estas claves: presupuesto_min, presupuesto_max, moneda, comuna, dormitorios_min, banos_min, caracteristicas_adicionales. "
            "Si un valor no está presente, usa null."
            f"\n\nConsulta: {query}"
        )

        response = self.client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
        )
        content = response.choices[0].message.content
        criteria = self._parse_json(content)
        return {
            "presupuesto_min": criteria.get("presupuesto_min"),
            "presupuesto_max": criteria.get("presupuesto_max"),
            "moneda": criteria.get("moneda"),
            "comuna": criteria.get("comuna"),
            "dormitorios_min": criteria.get("dormitorios_min"),
            "banos_min": criteria.get("banos_min"),
            "caracteristicas_adicionales": criteria.get("caracteristicas_adicionales"),
        }

    def _format_properties(self, properties: List[Dict[str, Any]]) -> str:
        if not properties:
            return "No hay propiedades disponibles para mostrar."

        bloques = []
        for idx, prop in enumerate(properties[:3], start=1):
            precio = prop.get("precio_uf") or prop.get("precio_valor")
            moneda = "UF" if prop.get("precio_uf") is not None else prop.get("moneda")
            bloques.append(
                f"Propiedad {idx}:\n"
                f"- Título: {prop.get('titulo', 'Sin título')}\n"
                f"- Precio: {precio} {moneda}\n"
                f"- Ubicación: {prop.get('comuna') or prop.get('ubicacion_raw', 'No especificada')}\n"
                f"- Características: {prop.get('dormitorios', 'N/A')} dormitorios / {prop.get('banos', 'N/A')} baños / {prop.get('metros', 'N/A')} m²\n"
                f"- Amenities: {prop.get('amenities', 'No especificado')}\n"
                f"- Link: {prop.get('link', 'No disponible')}\n"
            )
        return "\n".join(bloques)

    def generate_response(self, properties: List[Dict[str, Any]], query: str, context: Optional[str] = None) -> str:
        properties_text = self._format_properties(properties)
        context_text = f"Contexto adicional: {context}\n\n" if context else ""

        prompt = (
            "Eres un asistente que responde solo con información extraída de las propiedades proporcionadas. "
            "No inventes datos, no agregues propiedades nuevas y no menciones fuentes externas si no están en la lista. "
            f"Consulta del usuario: {query}\n\n"
            f"{context_text}"
            "Propiedades disponibles:\n"
            f"{properties_text}\n\n"
            "Genera la respuesta en el siguiente formato:\n"
            "Propiedad 1:\n"
            "- Título:\n"
            "- Precio:\n"
            "- Ubicación:\n"
            "- Características:\n"
            "- Link:\n\n"
            "Resumen:\n"
            "Explica brevemente por qué estas opciones son adecuadas."
        )

        response = self.client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content
