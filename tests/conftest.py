import os
import sys
import types
from pathlib import Path

import pytest
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Permite imports como "from app.main import RealEstateAgent" al ejecutar pytest.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# Carga .env desde la raíz del proyecto.
load_dotenv(PROJECT_ROOT / ".env", override=True)


def _install_lightweight_rag_stub_for_tests() -> None:
    """
    Evita que los tests unitarios/de observabilidad carguen RAG real.

    app.main importa app.rag_pipeline.RAGPipeline al cargarse.
    El RAG real depende de langchain_huggingface, FAISS y embeddings locales.
    Para estos tests no queremos probar embeddings; queremos probar flujo,
    memoria, LLMService y observability_log.

    Si necesitas testear el RAG real, ejecuta con:
    ENABLE_REAL_RAG_TESTS=1
    y asegúrate de instalar las dependencias necesarias.
    """
    if os.getenv("ENABLE_REAL_RAG_TESTS") == "1":
        return

    if "app.rag_pipeline" in sys.modules:
        return

    rag_module = types.ModuleType("app.rag_pipeline")

    class RAGPipeline:
        """
        Stub mínimo compatible con la interfaz usada por RealEstateAgent.

        Devuelve lista vacía para que los tests puedan mockear fallback_rag
        o _execute_crew_search sin cargar embeddings reales.
        """

        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def retrieve_properties(self, query: str, k: int = 3):
            return []

    rag_module.RAGPipeline = RAGPipeline
    sys.modules["app.rag_pipeline"] = rag_module


_install_lightweight_rag_stub_for_tests()


from app.memory import MEMORIA_PATH


@pytest.fixture(autouse=True)
def configure_test_environment(monkeypatch):
    """
    Configura variables de entorno estables para los tests.

    El proyecto usa Ollama como proveedor principal.
    OPENAI_API_KEY se mantiene como dummy por compatibilidad defensiva.
    """
    monkeypatch.setenv("LLM_PROVIDER", os.getenv("LLM_PROVIDER", "ollama"))
    monkeypatch.setenv("OLLAMA_MODEL", os.getenv("OLLAMA_MODEL", "llama3.2:3b"))
    monkeypatch.setenv(
        "OLLAMA_BASE_URL",
        os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
    )
    monkeypatch.setenv("OPENAI_SIM_MODEL", os.getenv("OPENAI_SIM_MODEL", "gpt-4o-mini"))
    monkeypatch.setenv("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", "test-openai-key"))


@pytest.fixture(autouse=True)
def clear_memory_file():
    """
    Limpia la memoria entre tests para evitar contaminación del historial.
    """
    memory_path = Path(MEMORIA_PATH)

    if memory_path.exists():
        memory_path.unlink()

    yield

    if memory_path.exists():
        memory_path.unlink()