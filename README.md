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

### 4. **RealEstateAgent** (`app/main.py`)
- Agente principal construido con LangChain y OpenAI Functions Agent.
- Integra herramientas para responder consultas sobre propiedades, precios en UF y distancias.

### 5. **Prompts** (`app/prompts/system_prompt.txt`)
- Define el comportamiento del agente como asesor virtual experto.

## Modelos Utilizados

- **Modelo de Lenguaje**: GPT-4o-mini (via OpenAI API)
- **Embeddings**: Sentence Transformers (para RAG)
- **Indexación Vectorial**: FAISS

## Requisitos del Sistema

- Python 3.8+
- Cuenta de OpenAI con API key
- Credenciales del Banco Central de Chile (para API UF)
- Entorno virtual recomendado

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

Esto iniciará el agente y procesará una consulta de ejemplo.

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
El proyecto incluye Streamlit en las dependencias. Puedes crear una interfaz web:

```python
# streamlit_app.py
import streamlit as st
from app.main import RealEstateAgent

agent = RealEstateAgent()

st.title("Agente Inmobiliario IA")
query = st.text_input("Consulta sobre propiedades:")
if st.button("Consultar"):
    response = agent.respond(query)
    st.write(response)
```

Ejecuta con `streamlit run streamlit_app.py`.

## Estructura del Proyecto

```
agente-inmobiliario/
├── app/
│   ├── llm_service.py      # Servicio de LLM
│   ├── main.py             # Agente principal
│   ├── rag_pipeline.py     # Pipeline RAG
│   ├── tools.py            # Herramientas (UF, distancia)
│   ├── prompts/
│   │   └── system_prompt.txt
│   └── __pycache__/
├── data/
│   ├── processed/          # Datos procesados de propiedades
│   └── raw/                # Datos crudos
├── docs/                   # Documentación adicional
├── scraping/               # Scripts de scraping
│   ├── scraper.py
│   └── try.py
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
<parameter name="filePath">c:\Users\javie\Desktop\Codigos\Evaluación sol. con IA\agente-inmobiliario\README.md