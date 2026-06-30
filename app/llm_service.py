import ast
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI, APIConnectionError, APIStatusError

load_dotenv(override=True)

DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "system_prompt.txt"


class LLMService:
    def __init__(self):
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        model_name = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

        self.client = OpenAI(
            api_key="ollama",
            base_url=base_url,
        )

        self.model = model_name
        self.system_prompt = self._load_system_prompt()
        self.reset_usage()

    def reset_usage(self) -> None:
        """
        Reinicia el conteo acumulado de uso del modelo.
        """
        self.last_usage = {
            "model_name": self.model,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "llm_calls": 0,
        }

    def get_usage_snapshot(self) -> dict:
        """
        Retorna una copia del uso acumulado del modelo.
        """
        return dict(self.last_usage)

    def _safe_token_value(self, value: Any) -> int:
        """
        Convierte valores de tokens a int de forma segura.
        """
        try:
            if value is None:
                return 0
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _store_usage(self, response: Any, model_name: Optional[str] = None) -> None:
        """
        Guarda y acumula el uso de tokens de una llamada al modelo.

        En Ollama puede que usage venga vacío o incompleto, por eso se manejan
        valores en 0 sin romper la app.
        """
        usage = getattr(response, "usage", None)

        prompt_tokens = self._safe_token_value(
            getattr(usage, "prompt_tokens", 0) if usage else 0
        )
        completion_tokens = self._safe_token_value(
            getattr(usage, "completion_tokens", 0) if usage else 0
        )
        total_tokens = self._safe_token_value(
            getattr(usage, "total_tokens", None) if usage else None
        )

        if total_tokens == 0:
            total_tokens = prompt_tokens + completion_tokens

        self.last_usage["model_name"] = model_name or self.model
        self.last_usage["prompt_tokens"] += prompt_tokens
        self.last_usage["completion_tokens"] += completion_tokens
        self.last_usage["total_tokens"] += total_tokens
        self.last_usage["llm_calls"] += 1

    def _load_system_prompt(self) -> str:
        if SYSTEM_PROMPT_PATH.exists():
            return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")

        return (
            "Eres un asesor virtual experto en propiedades inmobiliarias. "
            "Extrae criterios de usuario y genera respuestas estructuradas basadas en datos reales."
        )

    def _parse_json(self, content: str) -> dict:
        """
        Intenta parsear JSON incluso si el modelo local responde con ```json ... ```.
        """
        if not content:
            return {}

        content = content.strip()

        content = re.sub(r"^```json\s*", "", content, flags=re.IGNORECASE)
        content = re.sub(r"^```\s*", "", content)
        content = re.sub(r"\s*```$", "", content)

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                try:
                    return ast.literal_eval(match.group(0))
                except Exception:
                    return {}

        try:
            return ast.literal_eval(content)
        except Exception:
            return {}

    def extract_criteria(self, query: str) -> dict:
        prompt = (
            "Extrae los criterios de búsqueda de la consulta del usuario sobre propiedades en Chile.\n"
            "Responde únicamente con un JSON válido, sin markdown, sin explicación y sin texto adicional.\n\n"
            "El JSON debe contener exactamente estas claves:\n"
            "{\n"
            '  "presupuesto_min": null,\n'
            '  "presupuesto_max": null,\n'
            '  "moneda": null,\n'
            '  "comuna": null,\n'
            '  "dormitorios_min": null,\n'
            '  "banos_min": null,\n'
            '  "caracteristicas_adicionales": null\n'
            "}\n\n"
            "Reglas:\n"
            "- Si aparece UF, la moneda debe ser UF.\n"
            "- Si aparece CLP o pesos chilenos, la moneda debe ser CLP.\n"
            "- Si el usuario dice 'menos de X', usa presupuesto_max = X.\n"
            "- Si el usuario dice 'más de X', usa presupuesto_min = X.\n"
            "- Si un valor no está presente, usa null.\n\n"
            f"Consulta: {query}"
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
            )

            self._store_usage(response, self.model)

            content = response.choices[0].message.content or ""
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

        except APIConnectionError as e:
            raise ConnectionError(
                f"No se pudo conectar con Ollama: {str(e)}. "
                "Verifica que Ollama esté corriendo en http://localhost:11434 "
                "o que el contenedor 'ollama' esté levantado si usas Docker."
            )

        except APIStatusError as e:
            raise RuntimeError(
                f"Ollama respondió con error HTTP {e.status_code}: {e.response.text}. "
                f"Verifica que el modelo '{self.model}' esté descargado con: "
                f"ollama pull {self.model}"
            )

    def _format_properties(self, properties: List[Dict[str, Any]]) -> str:
        """
        Convierte propiedades recuperadas en un contexto legible para el LLM.

        La idea no es obligar al modelo a copiar una plantilla rígida, sino
        entregarle datos, evidencia y motivos de coincidencia para que pueda
        conversar de forma más natural sin inventar información.
        """
        if not properties:
            return (
                "No se recuperaron propiedades reales para esta consulta. "
                "No se debe inventar ninguna opción."
            )

        bloques = []
        max_props = int(os.getenv("RESPONSE_MAX_PROPERTIES", "3"))

        for idx, prop in enumerate(properties[:max_props], start=1):
            precio = prop.get("precio_uf") or prop.get("precio_valor")
            moneda = "UF" if prop.get("precio_uf") is not None else prop.get("moneda")
            comuna = prop.get("comuna") or prop.get("ubicacion_raw") or "No especificada"
            dormitorios = prop.get("dormitorios", "N/A")
            banos = prop.get("banos", "N/A")
            metros = prop.get("metros") or prop.get("superficie_total") or prop.get("superficie_util") or "N/A"
            amenities = prop.get("amenities") or "No especificado"
            link = prop.get("link") or "No disponible"
            quality = prop.get("match_quality")
            reasons = prop.get("match_reasons") or []
            warnings = prop.get("match_warnings") or []
            evidence = prop.get("rag_evidence")

            reasons_text = "; ".join(str(item) for item in reasons) if reasons else "No especificado"
            warnings_text = "; ".join(str(item) for item in warnings) if warnings else "Sin advertencias relevantes"

            bloque = (
                f"Opción {idx}\n"
                f"- Título: {prop.get('titulo', 'Sin título')}\n"
                f"- Precio: {precio} {moneda}\n"
                f"- Ubicación/comuna: {comuna}\n"
                f"- Características: {dormitorios} dormitorio(s), {banos} baño(s), {metros} m²\n"
                f"- Amenities: {amenities}\n"
                f"- Calidad de coincidencia RAG: {quality or 'no calculada'}\n"
                f"- Motivos para mostrarla: {reasons_text}\n"
                f"- Advertencias: {warnings_text}\n"
                f"- Link: {link}\n"
            )

            if evidence:
                bloque += f"- Evidencia recuperada: {str(evidence)[:500]}\n"

            bloques.append(bloque)

        search_summary = properties[0].get("rag_search_summary") if properties else None
        if search_summary:
            bloques.insert(0, f"Resumen interno de recuperación: {search_summary}\n")

        return "\n".join(bloques)

    def generate_response(
        self,
        properties: List[Dict[str, Any]],
        query: str,
        context: Optional[str] = None,
        historial: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        Genera una respuesta conversacional usando únicamente propiedades recuperadas.
        """
        properties_text = self._format_properties(properties)
        context_text = f"Contexto conversacional previo: {context}\n\n" if context else ""

        prompt = (
            "Actúa como asesor inmobiliario conversacional, claro y prudente. "
            "Tu trabajo es ayudar al usuario a comparar opciones reales, no vender de forma exagerada.\n\n"
            "Reglas obligatorias:\n"
            "- Responde solo con información contenida en las propiedades proporcionadas.\n"
            "- No inventes propiedades, precios, ubicaciones, metros, beneficios ni disponibilidad.\n"
            "- Si no hay propiedades recuperadas, dilo de forma natural y pide 1 o 2 criterios útiles para buscar mejor.\n"
            "- Si una coincidencia tiene advertencias, menciónalas con cuidado y sin dramatizar.\n"
            "- Las recomendaciones inmobiliarias deben considerarse referenciales y requerir validación humana.\n"
            "- Mantén un tono natural, como asesor útil, no como formulario.\n"
            "- Evita responder con una plantilla rígida tipo 'Propiedad 1 / Título / Precio' si no es necesario.\n"
            "- Usa máximo 3 opciones y prioriza las mejores.\n"
            "- Cierra con una pregunta breve que ayude a continuar la conversación.\n\n"
            f"Consulta del usuario: {query}\n\n"
            f"{context_text}"
            "Propiedades reales recuperadas desde SQLite/RAG:\n"
            f"{properties_text}\n\n"
            "Redacta la respuesta final en español de Chile, clara, amable y breve."
        )

        messages = [{"role": "system", "content": self.system_prompt}]

        if historial:
            # Mantiene memoria, pero evita que un historial largo opaque los datos recuperados.
            messages.extend(historial[-6:])

        messages.append({"role": "user", "content": prompt})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=float(os.getenv("RESPONSE_TEMPERATURE", "0.35")),
            )

            self._store_usage(response, self.model)

            return response.choices[0].message.content or ""

        except APIConnectionError as e:
            raise ConnectionError(
                f"No se pudo conectar con Ollama: {str(e)}. "
                "Verifica que Ollama esté corriendo en http://localhost:11434 "
                "o que el contenedor 'ollama' esté levantado si usas Docker."
            )

        except APIStatusError as e:
            raise RuntimeError(
                f"Ollama respondió con error HTTP {e.status_code}: {e.response.text}. "
                f"Verifica que el modelo '{self.model}' esté descargado con: "
                f"ollama pull {self.model}"
            )
