import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.data_pipeline import DataPipeline
from backend.db import cargar_propiedades_db


class RAGPipeline:
    """
    Pipeline RAG para recuperar propiedades desde una fuente local.

    Mejoras principales:
    - Permite configurar fuente, modelo de embeddings y cantidad de resultados por variables de entorno.
    - Valida datos de entrada para no indexar registros vacíos.
    - Combina búsqueda semántica FAISS con reglas simples de intención inmobiliaria.
    - Reordena resultados considerando comuna, presupuesto, dormitorios, baños y amenities.
    - Devuelve evidencia y motivos de coincidencia para que el LLM pueda responder de forma más natural.
    - Evita forzar recomendaciones cuando los resultados no tienen relación suficiente.
    """

    SAFE_METADATA_FIELDS = [
        "id",
        "id_fuente",
        "titulo",
        "moneda",
        "precio_valor",
        "precio_uf",
        "ubicacion_raw",
        "comuna",
        "dormitorios",
        "banos",
        "metros",
        "superficie_total",
        "superficie_util",
        "amenities",
        "link",
    ]

    COMUNA_ALIAS = {
        "las condes": "Las Condes",
        "vitacura": "Vitacura",
        "providencia": "Providencia",
        "nunoa": "Ñuñoa",
        "ñuñoa": "Ñuñoa",
        "santiago": "Santiago",
        "la reina": "La Reina",
        "lo barnechea": "Lo Barnechea",
        "macul": "Macul",
        "san miguel": "San Miguel",
        "estacion central": "Estación Central",
        "estación central": "Estación Central",
        "independencia": "Independencia",
        "recoleta": "Recoleta",
        "penalolen": "Peñalolén",
        "peñalolén": "Peñalolén",
    }

    AMENITY_ALIAS = {
        "piscina": ["piscina", "pool"],
        "gimnasio": ["gimnasio", "gym"],
        "quincho": ["quincho", "parrilla", "asado"],
        "estacionamiento": ["estacionamiento", "parking", "garage", "garaje"],
        "bodega": ["bodega"],
        "ascensor": ["ascensor", "elevador"],
        "terraza": ["terraza", "balcon", "balcón"],
        "jardin": ["jardin", "jardín", "patio"],
        "seguridad": ["seguridad", "conserjeria", "conserjería", "vigilancia"],
        "metro": ["metro", "estacion de metro", "estación de metro"],
    }

    def __init__(
        self,
        source: Optional[str] = None,
        model_name: Optional[str] = None,
        default_k: Optional[int] = None,
    ):
        self.source = source or os.getenv(
            "RAG_SOURCE",
            "data/processed/propiedades_detalle.csv",
        )
        self.model_name = self._normalize_embedding_model(
            model_name
            or os.getenv("EMBEDDING_MODEL")
            or "sentence-transformers/all-MiniLM-L6-v2"
        )
        self.default_k = default_k or int(os.getenv("RAG_TOP_K", "5"))
        self.fetch_k = int(os.getenv("RAG_FETCH_K", "20"))
        self.min_match_score = float(os.getenv("RAG_MIN_MATCH_SCORE", "0.18"))
        self.strict_filter = os.getenv("RAG_STRICT_FILTER", "true").lower() in {
            "1",
            "true",
            "yes",
            "si",
            "sí",
        }

        self.pipeline = DataPipeline()
        self.vectorstore: Optional[FAISS] = None
        self.document_count = 0

        self.load_and_index_data()

    # ══════════════════════════════════════════════════════════════
    # Carga e indexación
    # ══════════════════════════════════════════════════════════════

    def _resolve_path(self, path_value: str) -> Path:
        path = Path(path_value)
        if path.is_absolute():
            return path
        return Path(PROJECT_ROOT) / path

    def _normalize_embedding_model(self, model_name: str) -> str:
        """
        Permite usar 'all-MiniLM-L6-v2' o el nombre completo.
        HuggingFace recomienda el nombre completo del repositorio.
        """
        model_name = str(model_name).strip()
        if "/" not in model_name:
            return f"sentence-transformers/{model_name}"
        return model_name

    def _clean_value(self, value: Any) -> Any:
        """Limpia NaN y convierte tipos numpy/pandas a valores simples."""
        if value is None:
            return None
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
        if hasattr(value, "item"):
            try:
                return value.item()
            except Exception:
                return value
        return value

    def _load_source_dataframe(self) -> pd.DataFrame:
        """Carga propiedades desde SQLite o CSV."""
        source_path = self._resolve_path(self.source)

        if not source_path.exists():
            raise FileNotFoundError(f"No se encontró la fuente RAG: {source_path}")

        if source_path.suffix.lower() == ".db":
            df = cargar_propiedades_db(str(source_path))
        elif source_path.suffix.lower() == ".csv":
            df = pd.read_csv(source_path)
        else:
            raise ValueError("Fuente RAG no soportada. Use archivo .csv o .db")

        if df.empty:
            raise ValueError("La fuente RAG no contiene propiedades.")

        return df

    def load_and_index_data(self) -> None:
        """Carga, limpia e indexa las propiedades en FAISS."""
        df = self._load_source_dataframe()
        df_clean = self.pipeline.clean_dataframe(df)

        if "rag_text" not in df_clean.columns:
            raise ValueError("El dataframe limpio no contiene la columna obligatoria 'rag_text'.")

        df_clean = df_clean[
            df_clean["rag_text"].fillna("").astype(str).str.strip() != ""
        ].copy()

        if df_clean.empty:
            raise ValueError("No hay propiedades con texto RAG válido para indexar.")

        documents = []

        for _, row in df_clean.iterrows():
            metadata = {}
            for field in self.SAFE_METADATA_FIELDS:
                if field in df_clean.columns:
                    metadata[field] = self._clean_value(row.get(field))

            rag_text = str(row.get("rag_text", "")).strip()
            documents.append(Document(page_content=rag_text, metadata=metadata))

        embeddings = HuggingFaceEmbeddings(
            model_name=self.model_name,
            encode_kwargs={"normalize_embeddings": True},
        )

        self.vectorstore = FAISS.from_documents(documents, embeddings)
        self.document_count = len(documents)

    # ══════════════════════════════════════════════════════════════
    # Comprensión simple de intención inmobiliaria
    # ══════════════════════════════════════════════════════════════

    def _strip_accents(self, text: str) -> str:
        text = unicodedata.normalize("NFKD", text)
        return "".join(ch for ch in text if not unicodedata.combining(ch))

    def _normalize_text(self, text: Any) -> str:
        text = "" if text is None else str(text)
        text = self._strip_accents(text.lower())
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _parse_number(self, value: str) -> Optional[float]:
        value = value.replace(".", "").replace(",", ".").strip()
        try:
            return float(value)
        except ValueError:
            return None

    def _extract_number_before_terms(self, text: str, terms: list[str]) -> Optional[int]:
        joined_terms = "|".join(re.escape(term) for term in terms)
        pattern = rf"(\d+)\s*(?:{joined_terms})"
        match = re.search(pattern, text)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    def _extract_budget_uf(self, text: str) -> tuple[Optional[float], Optional[float]]:
        """Detecta rangos simples de presupuesto en UF."""
        presupuesto_min = None
        presupuesto_max = None

        entre = re.search(
            r"entre\s+([\d\.,]+)\s*(?:uf)?\s+y\s+([\d\.,]+)\s*uf",
            text,
        )
        if entre:
            primero = self._parse_number(entre.group(1))
            segundo = self._parse_number(entre.group(2))
            if primero is not None and segundo is not None:
                presupuesto_min = min(primero, segundo)
                presupuesto_max = max(primero, segundo)
                return presupuesto_min, presupuesto_max

        max_patterns = [
            r"(?:menos de|hasta|tope de|maximo|maxima|por debajo de|bajo)\s+([\d\.,]+)\s*uf",
            r"([\d\.,]+)\s*uf\s*(?:maximo|maxima|tope)",
        ]
        for pattern in max_patterns:
            match = re.search(pattern, text)
            if match:
                presupuesto_max = self._parse_number(match.group(1))
                break

        min_patterns = [
            r"(?:mas de|mayor a|desde|minimo|minima|sobre)\s+([\d\.,]+)\s*uf",
            r"([\d\.,]+)\s*uf\s*(?:minimo|minima)",
        ]
        for pattern in min_patterns:
            match = re.search(pattern, text)
            if match:
                presupuesto_min = self._parse_number(match.group(1))
                break

        # Si solo se menciona una cifra UF sin palabra de rango, se interpreta como techo suave.
        if presupuesto_min is None and presupuesto_max is None:
            generic = re.search(r"([\d\.,]+)\s*uf", text)
            if generic:
                presupuesto_max = self._parse_number(generic.group(1))

        return presupuesto_min, presupuesto_max

    def _extract_intent(self, query: str, memory_context: Optional[str] = None) -> dict[str, Any]:
        full_text = f"{memory_context or ''} {query or ''}".strip()
        text = self._normalize_text(full_text)

        comunas = []
        for raw, canonical in self.COMUNA_ALIAS.items():
            if self._normalize_text(raw) in text and canonical not in comunas:
                comunas.append(canonical)

        amenities = []
        for canonical, aliases in self.AMENITY_ALIAS.items():
            if any(self._normalize_text(alias) in text for alias in aliases):
                amenities.append(canonical)

        dormitorios = self._extract_number_before_terms(
            text,
            ["dormitorio", "dormitorios", "habitacion", "habitaciones", "pieza", "piezas", "dorm"],
        )
        banos = self._extract_number_before_terms(
            text,
            ["bano", "banos", "baño", "baños"],
        )
        presupuesto_min, presupuesto_max = self._extract_budget_uf(text)

        return {
            "raw_query": query,
            "normalized_text": text,
            "comunas": comunas,
            "amenities": amenities,
            "dormitorios_min": dormitorios,
            "banos_min": banos,
            "presupuesto_min": presupuesto_min,
            "presupuesto_max": presupuesto_max,
        }

    def _build_query(self, query: str, memory_context: Optional[str] = None) -> str:
        """
        Construye una consulta semántica natural.
        Se limita la memoria para evitar que contamine demasiado la búsqueda.
        """
        query = (query or "").strip()
        if not memory_context:
            return query

        memory_context = memory_context.strip()
        if len(memory_context) > 500:
            memory_context = memory_context[:500]

        return f"Contexto previo: {memory_context}\nConsulta actual: {query}"

    # ══════════════════════════════════════════════════════════════
    # Reranking y explicación
    # ══════════════════════════════════════════════════════════════

    def _distance_to_similarity(self, distance: float) -> float:
        """
        FAISS con embeddings normalizados retorna una distancia donde menor es mejor.
        Esta transformación no pretende ser probabilidad; solo ayuda a ordenar.
        """
        try:
            distance = float(distance)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, 1.0 - (distance / 2.0)))

    def _as_float(self, value: Any) -> Optional[float]:
        value = self._clean_value(value)
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _as_int(self, value: Any) -> Optional[int]:
        number = self._as_float(value)
        return int(number) if number is not None else None

    def _metadata_text(self, metadata: dict[str, Any], evidence: str = "") -> str:
        values = [str(v) for v in metadata.values() if v not in (None, "")]
        values.append(evidence or "")
        return self._normalize_text(" ".join(values))

    def _score_candidate(
        self,
        metadata: dict[str, Any],
        evidence: str,
        distance: float,
        semantic_rank: int,
        intent: dict[str, Any],
    ) -> tuple[float, list[str], list[str], bool]:
        similarity = self._distance_to_similarity(distance)
        # Pequeño premio por aparecer arriba en la búsqueda semántica original.
        rank_bonus = max(0.0, 0.08 - (semantic_rank * 0.01))
        score = (similarity * 0.55) + rank_bonus

        reasons: list[str] = []
        warnings: list[str] = []
        hard_mismatch = False

        candidate_text = self._metadata_text(metadata, evidence)
        comuna_prop = metadata.get("comuna")
        comuna_norm = self._normalize_text(comuna_prop)

        if intent.get("comunas"):
            expected = [self._normalize_text(c) for c in intent["comunas"]]
            if comuna_norm and comuna_norm in expected:
                score += 0.22
                reasons.append(f"calza con la comuna {comuna_prop}")
            else:
                score -= 0.35
                warnings.append("la comuna no coincide exactamente con lo pedido")
                hard_mismatch = True

        precio_uf = self._as_float(metadata.get("precio_uf"))
        if intent.get("presupuesto_max") is not None:
            max_uf = float(intent["presupuesto_max"])
            if precio_uf is not None and precio_uf <= max_uf:
                score += 0.18
                reasons.append(f"está dentro del presupuesto máximo de {max_uf:g} UF")
            elif precio_uf is not None:
                score -= 0.35
                warnings.append(f"supera el presupuesto solicitado de {max_uf:g} UF")
                hard_mismatch = True

        if intent.get("presupuesto_min") is not None:
            min_uf = float(intent["presupuesto_min"])
            if precio_uf is not None and precio_uf >= min_uf:
                score += 0.08
            elif precio_uf is not None:
                score -= 0.12
                warnings.append(f"está bajo el mínimo indicado de {min_uf:g} UF")

        dormitorios_prop = self._as_int(metadata.get("dormitorios"))
        if intent.get("dormitorios_min") is not None:
            required = int(intent["dormitorios_min"])
            if dormitorios_prop is not None and dormitorios_prop >= required:
                score += 0.14
                reasons.append(f"tiene {dormitorios_prop} dormitorio(s)")
            elif dormitorios_prop is not None:
                score -= 0.25
                warnings.append(f"tiene menos dormitorios que los {required} solicitados")
                hard_mismatch = True

        banos_prop = self._as_int(metadata.get("banos"))
        if intent.get("banos_min") is not None:
            required = int(intent["banos_min"])
            if banos_prop is not None and banos_prop >= required:
                score += 0.10
                reasons.append(f"tiene {banos_prop} baño(s)")
            elif banos_prop is not None:
                score -= 0.18
                warnings.append(f"tiene menos baños que los {required} solicitados")

        for amenity in intent.get("amenities") or []:
            amenity_norm = self._normalize_text(amenity)
            if amenity_norm in candidate_text:
                score += 0.08
                reasons.append(f"menciona {amenity}")
            else:
                warnings.append(f"no se confirma {amenity} en la evidencia recuperada")

        if not reasons:
            if similarity >= 0.55:
                reasons.append("coincide semánticamente con la búsqueda")
            else:
                reasons.append("es una coincidencia aproximada, conviene revisarla con cuidado")

        return max(0.0, score), reasons, warnings, hard_mismatch

    def _quality_label(self, score: float) -> str:
        if score >= 0.62:
            return "alta"
        if score >= 0.38:
            return "media"
        return "baja"

    def _build_search_summary(self, intent: dict[str, Any], total_candidates: int, returned: int) -> str:
        parts = []
        if intent.get("comunas"):
            parts.append(f"comuna {', '.join(intent['comunas'])}")
        if intent.get("dormitorios_min"):
            parts.append(f"mínimo {intent['dormitorios_min']} dormitorio(s)")
        if intent.get("banos_min"):
            parts.append(f"mínimo {intent['banos_min']} baño(s)")
        if intent.get("presupuesto_max"):
            parts.append(f"hasta {intent['presupuesto_max']:g} UF")
        if intent.get("amenities"):
            parts.append(f"amenities: {', '.join(intent['amenities'])}")

        criterios = "; ".join(parts) if parts else "criterios generales de la consulta"
        return (
            f"Se evaluaron {total_candidates} candidatos recuperados por FAISS usando {criterios}. "
            f"Se devuelven {returned} resultado(s) priorizados."
        )

    # ══════════════════════════════════════════════════════════════
    # API pública
    # ══════════════════════════════════════════════════════════════

    def retrieve_properties(
        self,
        query: str,
        k: Optional[int] = None,
        memory_context: Optional[str] = None,
        include_evidence: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Recupera propiedades usando búsqueda semántica + reranking inmobiliario.

        Retorna una lista de propiedades con metadata segura, score interno,
        calidad de coincidencia, evidencia RAG y motivos de recomendación.

        Si no hay resultados suficientemente relacionados, retorna lista vacía.
        """
        if not self.vectorstore:
            return []

        if not query or not query.strip():
            return []

        k = k or self.default_k
        enhanced_query = self._build_query(query, memory_context)
        intent = self._extract_intent(query, memory_context)

        fetch_k = max(k, self.fetch_k)
        docs_with_scores = self.vectorstore.similarity_search_with_score(
            enhanced_query,
            k=fetch_k,
        )

        ranked: list[dict[str, Any]] = []

        for rank, (doc, distance) in enumerate(docs_with_scores):
            metadata = dict(doc.metadata)
            evidence = (doc.page_content or "").strip()
            match_score, reasons, warnings, hard_mismatch = self._score_candidate(
                metadata=metadata,
                evidence=evidence,
                distance=float(distance),
                semantic_rank=rank,
                intent=intent,
            )

            if self.strict_filter and hard_mismatch:
                continue

            if match_score < self.min_match_score:
                continue

            item = dict(metadata)
            item["retrieval_distance"] = float(distance)
            item["retrieval_score"] = round(match_score, 4)
            item["match_quality"] = self._quality_label(match_score)
            item["match_reasons"] = reasons[:4]
            item["match_warnings"] = warnings[:3]

            if include_evidence:
                item["rag_evidence"] = evidence[:700]

            ranked.append(item)

        ranked.sort(key=lambda item: item.get("retrieval_score", 0), reverse=True)
        results = ranked[:k]

        summary = self._build_search_summary(
            intent=intent,
            total_candidates=len(docs_with_scores),
            returned=len(results),
        )
        for item in results:
            item["rag_search_summary"] = summary

        return results

    def retrieve_context(
        self,
        query: str,
        k: Optional[int] = None,
        memory_context: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Variante útil para depuración o futuras mejoras conversacionales.
        Mantiene retrieve_properties compatible con el resto del proyecto.
        """
        results = self.retrieve_properties(
            query=query,
            k=k,
            memory_context=memory_context,
            include_evidence=True,
        )
        return {
            "query": query,
            "source": self.source,
            "embedding_model": self.model_name,
            "document_count": self.document_count,
            "results": results,
            "has_results": bool(results),
        }
