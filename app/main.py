import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from crewai.tools import tool
from .rag_pipeline import RAGPipeline
from .llm_service import LLMService
from .tools import Tools
from .memory import Memoria
from backend.db import buscar_propiedades, registrar_busqueda


# Tools para CrewAI
@tool
def get_uf_value():
    """Obtiene el valor actual de la UF desde el Banco Central."""
    return Tools.get_uf_value()


@tool
def calculate_distance(coord1: str, coord2: str):
    """Calcula la distancia entre dos coordenadas."""
    c1 = tuple(map(float, coord1.split(",")))
    c2 = tuple(map(float, coord2.split(",")))
    return Tools.calculate_distance(c1, c2)


@tool
def retrieve_properties(query: str):
    """Recupera propiedades relevantes usando RAG."""
    rag = RAGPipeline('data/processed/propiedades_detalle.csv')
    return rag.retrieve_properties(query)


@tool
def retrieve_properties_db(query: str, cantidad: int = 5):
    """Recupera propiedades relevantes desde la base de datos SQLite."""
    propiedades = buscar_propiedades(texto=query, cantidad=cantidad)
    registrar_busqueda(
        consulta=query,
        sql_gen="buscar_propiedades(texto)",
        n_results=len(propiedades),
        proveedor="sqlite",
    )
    return propiedades


class RealEstateAgent:
    def __init__(self):
        self.memory = Memoria()
        self.llm = LLMService()
        self.rag = RAGPipeline('data/processed/propiedades_detalle.csv')

    def search_properties(self, query: str, criteria: dict) -> list[dict]:
        if not criteria:
            return buscar_propiedades(texto=query, cantidad=5)

        propiedades = buscar_propiedades(
            cantidad=5,
            comuna=criteria.get("comuna"),
            min_dormitorios=criteria.get("dormitorios_min"),
            min_banos=criteria.get("banos_min"),
            precio_min=criteria.get("presupuesto_min"),
            precio_max=criteria.get("presupuesto_max"),
            texto=criteria.get("caracteristicas_adicionales") or query,
        )

        if propiedades:
            registrar_busqueda(
                consulta=query,
                sql_gen=str(criteria),
                n_results=len(propiedades),
                proveedor="sqlite",
            )
            return propiedades

        return []

    def fallback_rag(self, query: str) -> list[dict]:
        resultados = self.rag.retrieve_properties(query, k=3)
        registrar_busqueda(
            consulta=query,
            sql_gen="RAG fallback",
            n_results=len(resultados),
            proveedor="rag",
        )
        return resultados

    def respond(self, query: str) -> str:
        self.memory.agregar_usuario(query)

        criteria = self.llm.extract_criteria(query)
        propiedades = self.search_properties(query, criteria)

        if not propiedades:
            propiedades = self.fallback_rag(query)

        contexto = self.memory.resumen_contexto()
        respuesta = self.llm.generate_response(propiedades, query, contexto)

        self.memory.agregar_asistente(respuesta, proveedor="LLM")
        return respuesta


# Para uso directo
if __name__ == "__main__":
    agent = RealEstateAgent()
    query = "Busco un departamento de 3 dormitorios en Las Condes con presupuesto de 10000 UF"
    response = agent.respond(query)
    print(response)
