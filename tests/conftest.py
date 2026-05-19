import os
import pytest

from app.memory import MEMORIA_PATH


@pytest.fixture(autouse=True)
def clear_memory_file():
    """Limpia la memoria entre tests para evitar contaminación del historial."""
    if os.path.exists(MEMORIA_PATH):
        os.remove(MEMORIA_PATH)
    yield
    if os.path.exists(MEMORIA_PATH):
        os.remove(MEMORIA_PATH)


@pytest.fixture(autouse=True)
def set_openai_api_key(monkeypatch):
    """Asegura que la variable de entorno OPENAI_API_KEY exista durante los tests."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
