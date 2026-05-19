# Agente Inmobiliario con IA

Este proyecto implementa un agente virtual experto en propiedades de la Región Metropolitana de Chile, utilizando técnicas de IA como RAG (Retrieval-Augmented Generation) y herramientas integradas para consultas sobre propiedades inmobiliarias.

## Arquitectura

El agente está construido con los siguientes componentes principales:

> Ver también: `docs/architecture.md` para el diagrama de flujo de datos y componentes.


### 1. **LLMService** (`app/llm_service.py`)
- Maneja las interacciones con el modelo de lenguaje de OpenAI (GPT-4o-mini).
- Extrae criterios de búsqueda de consultas de usuarios.
- Genera respuestas estructuradas basadas en propiedades recuperadas.

### 2. **RAGPipeline** (`app/rag_pipeline.py`)
- Implementa Retrieval-Augmented Generation para recuperar propiedades relevantes.
- Utiliza FAISS para indexación vectorial y Sentence Transformers para embeddings.
- Procesa datos de propiedades desde archivos CSV en `data/processed/`.

### 2.1 **Backend Data Pipeline** (`backend/data_pipeline.py`)
- Normaliza y limpia información de propiedades antes de generar embeddings.
- Unifica formatos de precio a UF, números de dormitorios/baños, ubicaciones y descripciones.
- Genera texto de documento optimizado para RAG con menos ruido semántico.
- Permite almacenar `precio_uf` y `rag_text` en la DB para búsquedas consistentes.

### 3. **Tools** (`app/tools.py`)
- **get_uf_value()**: Consulta el valor actual de la UF desde la API del Banco Central de Chile usando credenciales configuradas en variables de entorno.
- **calculate_distance()**: Calcula distancias entre coordenadas usando Geopy.
- **retrieve_properties()**: Recupera propiedades usando el pipeline RAG.
- Integrado con CrewAI para herramientas del agente.

### 4. **RealEstateAgent** (`app/main.py`)
- Agente principal construido con LangChain y OpenAI Functions Agent.
- Integra herramientas para responder consultas sobre propiedades, precios en UF y distancias.
- Utiliza memoria conversacional persistente y base de datos SQLite para búsquedas eficientes.

### 5. **Memory** (`app/memory.py`)
- Gestiona el historial conversacional persistente del agente.
- Implementa ventana deslizante para mantener los últimos turnos de conversación en un archivo JSON.

### 6. **Database** (`backend/db.py`)
- Almacena propiedades en SQLite con actualización automática de valores UF desde la API del Banco Central.
- Registra búsquedas para análisis y mejora del sistema.

### 7. **UI** (`ui/streamlit_app.py`)
- Interfaz web simple construida con Streamlit para interactuar con el agente inmobiliario.
- Permite consultas en tiempo real y visualización de respuestas.

### 8. **Prompts** (`app/prompts/system_prompt.txt`)
- Define el comportamiento del agente como asesor virtual experto.

### 9. **Tests** (`tests/`)
- Pruebas unitarias para validar el funcionamiento del data pipeline y otros componentes.

## Modelos Utilizados

- **Modelo de Lenguaje**: GPT-4o-mini (via OpenAI API)
- **Embeddings**: Sentence Transformers (para RAG)
- **Indexación Vectorial**: FAISS
- **Framework de Agente**: LangChain y CrewAI
- **Base de Datos**: SQLite
- **Interfaz Web**: Streamlit

## Requisitos del Sistema

- Python 3.8+
- Cuenta de OpenAI con API key
- Credenciales del Banco Central de Chile (para API UF)
- SQLite (incluido con Python)
- Entorno virtual recomendado

## Dependencias Principales

- **LangChain**: Framework para agentes de IA
- **CrewAI**: Herramientas para agentes
- **OpenAI**: API de modelos de lenguaje
- **FAISS**: Indexación vectorial
- **Streamlit**: Interfaz web
- **Pandas**: Manipulación de datos
- **Sentence Transformers**: Embeddings de texto
- **Geopy**: Cálculos de distancia
- **Requests**: Llamadas HTTP

Ver `requirements.txt` para la lista completa.

## Instalación y Configuración

### 1. Clonar el Repositorio
```bash
git clone <url-del-repositorio>
cd agente-inmobiliario
```

### 2. Crear Entorno Virtual
```bash
python -m venv .venv
# En Windows:
.venv\Scripts\activate
# En Linux/Mac:
source .venv/bin/activate
```

### 3. Instalar Dependencias
```bash
pip install -r requirements.txt
```

### 4. Ejecutar pruebas
```bash
pytest tests/test_data_pipeline.py
```

### 4. Configurar Variables de Entorno
Crear un archivo `.env` en la raíz del proyecto con las siguientes variables:

```env
OPENAI_BASE_URL=https://models.inference.ai.azure.com
OPENAI_EMBEDDINGS_URL=https://models.github.ai/inference
GITHUB_TOKEN=ghp_...  # Tu token de GitHub para OpenAI
LANGSMITH_TRACING=
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=
BCCH_USER=tu_usuario@dominio.cl  # Usuario del Banco Central
BCCH_PASS=tu_contraseña  # Contraseña del Banco Central
BCCH_SERIE_UF=F073.UFF.PRE.Z.D  # Serie UF del Banco Central
```

**Nota**: Las credenciales del Banco Central se obtienen registrándose en [SI3 Banco Central](https://si3.bcentral.cl/Indicadoressiete/secure/Indicadoresdiarios.aspx).

### 5. Preparar Datos
Asegúrate de que los archivos de datos estén en `data/processed/`:
- `propiedades_detalle.csv` o `propiedades_detalle_parcial.csv`

Si necesitas generar datos nuevos, revisa `scraping/scraper.py`.

## Uso

### Ejecutar el Agente
```bash
python app/main.py
```

Esto iniciará el agente y procesará consultas de ejemplo.

### Ejecutar la demostración end-to-end con memoria
```bash
python demo_end_to_end.py
```

Este script ejecuta una consulta inicial y un follow-up, y muestra el historial persistido para probar que la memoria se está usando efectivamente.

### Usar la Interfaz Web
```bash
streamlit run ui/streamlit_app.py
```

Esto abrirá la interfaz web en el navegador para consultas interactivas.

### Probar Funcionalidades
```bash
python test.py
```

### Usar Herramientas Individualmente
```python
from app.tools import Tools

# Obtener valor UF
uf = Tools.get_uf_value()
print(f"Valor UF actual: {uf}")

# Calcular distancia
dist = Tools.calculate_distance((-33.4489, -70.6693), (-33.4569, -70.6483))  # Santiago a Providencia
print(f"Distancia: {dist} km")
```

## Despliegue

### Desarrollo Local
Sigue los pasos de instalación arriba. El agente se ejecuta localmente con las dependencias instaladas.

### Producción
Para desplegar en un servidor:
1. Configura un servidor con Python 3.8+.
2. Instala dependencias y configura `.env`.
3. Ejecuta `python app/main.py` o integra en una aplicación web (ej. con Streamlit en `streamlit_app.py` si se crea).

### Integración con Streamlit
El proyecto incluye una interfaz web construida con Streamlit en `ui/streamlit_app.py`. Para ejecutarla:

```bash
streamlit run ui/streamlit_app.py
```

Esto permite consultas interactivas al agente a través del navegador.

## Estructura del Proyecto

```
agente-inmobiliario/
├── app/
│   ├── llm_service.py      # Servicio de LLM
│   ├── main.py             # Agente principal
│   ├── rag_pipeline.py     # Pipeline RAG
│   ├── tools.py            # Herramientas (UF, distancia)
│   ├── memory.py           # Memoria conversacional
│   ├── prompts/
│   │   └── system_prompt.txt
│   └── __pycache__/
├── backend/
│   ├── data_pipeline.py    # Pipeline de datos
│   ├── db.py               # Base de datos SQLite
│   └── __pycache__/
├── data/
│   ├── processed/          # Datos procesados de propiedades
│   └── raw/                # Datos crudos
├── docs/                   # Documentación adicional
│   └── architecture.md     # Diagrama de arquitectura
├── scraping/               # Scripts de scraping
│   ├── scraper.py
│   └── try.py
├── tests/                  # Pruebas unitarias
│   └── test_data_pipeline.py
├── ui/                     # Interfaz de usuario
│   └── streamlit_app.py    # App de Streamlit
├── .env                    # Variables de entorno (no commitear)
├── requirements.txt        # Dependencias Python
├── test.py                 # Script de pruebas
└── README.md               # Este archivo
```

## Contribución

1. Fork el proyecto.
2. Crea una rama para tu feature (`git checkout -b feature/nueva-funcionalidad`).
3. Commit tus cambios (`git commit -am 'Agrega nueva funcionalidad'`).
4. Push a la rama (`git push origin feature/nueva-funcionalidad`).
5. Abre un Pull Request.

## Licencia

Este proyecto es de uso educativo. Consulta términos de OpenAI y Banco Central para uso comercial.

## Contacto

Para preguntas o soporte, contacta al desarrollador.</content>
