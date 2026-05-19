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
Abre tu terminal (PowerShell, CMD o Terminal de Mac/Linux) y navega a la carpeta donde guardaste el proyecto:

```bash
cd /ruta/hacia/tu/carpeta/agente-inmobiliario
```

> Nota: reemplaza `/ruta/hacia/tu/carpeta/` por la ubicación real en tu equipo.

### 2. Crear el Entorno Virtual
```bash
python -m venv .venv
```

### 3. Activar el Entorno Virtual
Ejecuta el comando correspondiente a tu sistema:

- Windows (PowerShell):
  ```powershell
  .venv\Scripts\Activate.ps1
  ```
  Si aparece un error de permisos, primero ejecuta:
  ```powershell
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
  ```

- Windows (CMD tradicional):
  ```cmd
  .venv\Scripts\activate.bat
  ```

- Mac / Linux:
  ```bash
  source .venv/bin/activate
  ```

### 4. Instalar Dependencias
Con el entorno virtual activo, ejecuta:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Configurar Variables de Entorno
Crea un archivo `.env` en la raíz del proyecto (donde está `requirements.txt`) con este contenido:

```env
OPENAI_API_KEY=tu_clave_aqui
OPENAI_MODEL=gpt-4o-mini
BCCH_USER=tu_usuario_banco_central_si_tienes
BCCH_PASS=tu_password_banco_central_si_tienes
```

> Si no configuras las credenciales del Banco Central de Chile, el sistema activará un fallback automático.

### 6. Preparar Datos
Asegúrate de tener uno de estos archivos en `data/processed/`:
- `propiedades_detalle.csv`
- `propiedades_detalle_parcial.csv`

Si necesitas generar datos nuevos, revisa `scraping/scraper.py`.

## Guía de Ejecución y Testeo

### Ejecutar Demo en Terminal (CLI)
Para verificar el flujo de consultas, respuestas e historial:

```bash
python demo_end_to_end.py
```

### Ejecutar la Aplicación Web (Streamlit)
Para abrir la interfaz gráfica en el navegador:

```bash
python -m streamlit run ui/streamlit_app.py
```

Después de ejecutar este comando, abre en tu navegador:

```text
http://localhost:8501
```

### Comandos Rápidos (Copy-Paste)
Si ya estás en la carpeta del proyecto, usa estos bloques para instalar y ejecutar rápidamente.

- Terminal 1: instalar dependencias y ejecutar demo

```bash
python -m venv .venv; .venv\Scripts\Activate.ps1; pip install --upgrade pip; pip install -r requirements.txt; python demo_end_to_end.py
```

- Terminal 2: levantar la app web

```bash
.venv\Scripts\Activate.ps1; python -m streamlit run ui/streamlit_app.py
```

> Para Mac/Linux, sustituye `.venv\Scripts\Activate.ps1` por `source .venv/bin/activate`.

### Ejecución Opcional del Agente Principal
```bash
python app/main.py
```

Esto iniciará el agente y procesará consultas de ejemplo en la terminal.

### Probar Funcionalidades
```bash
pytest tests/test_data_pipeline.py
```

o bien:

```bash
python test.py
```

### Usar Herramientas Individualmente
```python
from app.tools import Tools

uf = Tools.get_uf_value()
print(f"Valor UF actual: {uf}")

dist = Tools.calculate_distance((-33.4489, -70.6693), (-33.4569, -70.6483))
print(f"Distancia: {dist} km")
```

## Despliegue

### Desarrollo Local
Sigue los pasos de instalación arriba. El agente se puede ejecutar localmente con las dependencias instaladas.

### Producción
Para desplegar en un servidor:
1. Configura un servidor con Python 3.8+.
2. Instala dependencias y configura `.env`.
3. Ejecuta `python app/main.py` o integra en una aplicación web con Streamlit.

### Integración con Streamlit
El proyecto incluye una interfaz web en `ui/streamlit_app.py`. Para ejecutarla:

```bash
python -m streamlit run ui/streamlit_app.py
```

Esto permite consultas interactivas al agente desde el navegador.

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
