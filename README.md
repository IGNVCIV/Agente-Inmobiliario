# Agente Inmobiliario con IA

Sistema de agente inmobiliario con inteligencia artificial para búsqueda, recomendación y análisis de propiedades en la Región Metropolitana de Chile.

El proyecto permite consultar propiedades mediante lenguaje natural, recuperar información desde una base local, generar respuestas estructuradas con un modelo de lenguaje y monitorear el comportamiento del agente mediante métricas de observabilidad, costos referenciales, trazabilidad y dashboard operativo.

---

## Descripción General

El sistema funciona como un centro operativo inmobiliario con IA. Integra una base local de propiedades, recuperación semántica, memoria conversacional, modelo de lenguaje local y una interfaz web para interactuar con el agente.

El flujo principal permite que un usuario realice consultas como:

```text
Busco departamento de 3 dormitorios en Las Condes por menos de 2500 UF.
```

```text
Necesito algo con piscina y cerca del metro.
```

```text
Muéstrame las alternativas más económicas disponibles.
```

El agente interpreta la solicitud, extrae criterios relevantes, busca propiedades disponibles y genera una respuesta basada en datos recuperados desde el sistema.

---

## Características Principales

- Búsqueda inmobiliaria mediante lenguaje natural.
- Recuperación de propiedades desde SQLite.
- Recuperación semántica mediante RAG.
- Modelo de lenguaje local con Ollama.
- Memoria conversacional para consultas de seguimiento.
- Interfaz web en Streamlit.
- Dashboard operativo con KPIs.
- Vista de trazabilidad por ejecución.
- Registro de latencia, errores, proveedor, modelo, tokens y costos referenciales.
- Separación entre costo real de API y costo comparativo estimado.
- Uso de variables de entorno para configuración segura.

---

## Arquitectura del Sistema

El proyecto está compuesto por los siguientes módulos principales:

### 1. Agente Principal — `app/main.py`

Coordina el flujo completo de una consulta:

1. Recibe la consulta del usuario.
2. Guarda el mensaje en memoria conversacional.
3. Extrae criterios de búsqueda.
4. Combina criterios nuevos con contexto previo.
5. Planifica la estrategia de búsqueda.
6. Recupera propiedades desde SQLite, herramientas o RAG.
7. Genera una respuesta con el modelo de lenguaje.
8. Actualiza memoria y contexto activo.
9. Registra métricas de observabilidad.

---

### 2. Servicio de Modelo de Lenguaje — `app/llm_service.py`

Gestiona la interacción con el proveedor LLM.

Proveedor principal:

```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2:3b
```

El sistema utiliza Ollama local mediante Docker, lo que permite ejecutar el modelo de lenguaje sin depender directamente de una API externa para el flujo principal.

---

### 3. Observabilidad — `app/observability.py`

Registra información técnica de cada ejecución del agente en la tabla:

```text
observability_log
```

La observabilidad permite analizar el comportamiento del sistema, revisar trazabilidad, detectar errores, medir latencia, revisar tokens y comparar costos referenciales.

Métricas principales registradas:

- `run_id`
- `timestamp`
- `query_hash`
- `query_preview`
- `status`
- `error_type`
- `error_message`
- `provider`
- `model_name`
- `n_results`
- `latency_total_ms`
- `latency_criteria_ms`
- `latency_planner_ms`
- `latency_crew_ms`
- `latency_rag_ms`
- `latency_generation_ms`
- `cpu_percent`
- `memory_mb`
- `prompt_tokens`
- `completion_tokens`
- `total_tokens`
- `actual_cost_usd`
- `estimated_openai_cost_usd`
- `precision_score`
- `consistency_group`
- `notes`

---

### 4. RAG Pipeline — `app/rag_pipeline.py`

Implementa recuperación aumentada por generación para encontrar propiedades relevantes a partir de la consulta del usuario.

Utiliza:

- FAISS para indexación vectorial.
- Sentence Transformers para embeddings.
- Datos procesados desde `data/processed/`.

---

### 5. Base de Datos — `backend/db.py`

Gestiona la base de datos SQLite del proyecto:

```text
backend/propiedades.db
```

Funciones principales:

- Almacenamiento de propiedades.
- Búsquedas estructuradas.
- Registro histórico de búsquedas.
- Lectura de datos para dashboard y trazabilidad.
- Integración con el flujo principal del agente.

---

### 6. Pipeline de Datos — `backend/data_pipeline.py`

Normaliza y prepara información inmobiliaria antes de usarla en búsqueda estructurada o RAG.

Procesa campos como:

- Precio.
- Comuna.
- Dormitorios.
- Baños.
- Metros cuadrados.
- Amenities.
- Texto optimizado para recuperación semántica.

---

### 7. Memoria Conversacional — `app/memory.py`

Mantiene contexto entre turnos de conversación.

Esto permite consultas de seguimiento como:

```text
¿Y ahora con piscina?
```

```text
Muéstrame opciones parecidas pero más económicas.
```

---

### 8. Herramientas — `app/tools.py`

Incluye funciones auxiliares utilizadas por el agente:

- Consulta de valor UF.
- Cálculo de distancia.
- Recuperación de propiedades.
- Herramientas de apoyo para búsqueda inmobiliaria.

---

### 9. Portal Streamlit — `ui/agent_portal.py`

Interfaz principal del sistema.

Se ejecuta con:

```bash
python -m streamlit run ui/agent_portal.py
```

Módulos disponibles:

- **Inicio**: vista general del sistema.
- **Agente IA**: interfaz conversacional.
- **Dashboard**: KPIs operativos.
- **Trazabilidad**: logs, timeline y auditoría de ejecuciones.

---

### 10. Evaluador Operativo — `scripts/run_observability_eval.py`

Script de ejecución controlada para generar datos de monitoreo y revisar el comportamiento del agente en distintos escenarios de consulta.

Genera:

```text
data/observability/eval_results.csv
data/observability/eval_summary.json
```

---

## Proveedor LLM y Costos

El proveedor principal del sistema es **Ollama local**.

Esto permite ejecutar el modelo en entorno local mediante Docker. En este modo, el costo real de API externa se registra como:

```text
actual_cost_usd = 0.0
```

Además, el sistema calcula un costo comparativo estimado mediante:

```text
estimated_openai_cost_usd
```

Este valor es solo una referencia técnica para comparar escenarios de escalabilidad con proveedores cloud. No representa facturación real.

Variables asociadas:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3.2:3b
OPENAI_SIM_MODEL=gpt-4o-mini
```

---

## Requisitos del Sistema

Se recomienda usar:

- Python 3.11 o 3.12.
- Docker Desktop.
- SQLite.
- Navegador web moderno.
- Entorno virtual de Python.

No se recomienda Python 3.14 para este proyecto, ya que algunas dependencias pueden requerir binarios nativos no disponibles o compilación adicional en Windows.

---

## Instalación

### 1. Entrar a la carpeta del proyecto

```bash
cd agente-inmobiliario
```

---

### 2. Crear entorno virtual

Windows:

```bash
py -3.12 -m venv .venv
```

O usando Python configurado en el sistema:

```bash
python -m venv .venv
```

---

### 3. Activar entorno virtual

Windows CMD:

```cmd
.venv\Scripts\activate.bat
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Mac/Linux:

```bash
source .venv/bin/activate
```

---

### 4. Instalar dependencias

Se recomienda usar `python -m pip` para evitar conflictos con instalaciones globales:

```bash
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

---

## Configuración

Crear un archivo `.env` en la raíz del proyecto a partir de `.env.example`.

Ejemplo de configuración local:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3.2:3b

OPENAI_SIM_MODEL=gpt-4o-mini

BCCH_USER=
BCCH_PASS=

OBS_DB_PATH=backend/propiedades.db
OBS_EVAL_RESULTS_PATH=data/observability/eval_results.csv
OBS_EVAL_SUMMARY_PATH=data/observability/eval_summary.json
```

El archivo `.env` no debe subirse al repositorio.

---

## Ejecución

### 1. Levantar Ollama con Docker

```bash
docker compose up -d
```

Verificar contenedores activos:

```bash
docker ps
```

---

### 2. Verificar modelos disponibles en Ollama

```bash
curl http://localhost:11434/api/tags
```

Si el modelo no está disponible, descargarlo:

```bash
docker compose exec ollama ollama pull llama3.2:3b
```

---

### 3. Ejecutar el portal web

```bash
python -m streamlit run ui/agent_portal.py
```

Abrir en el navegador:

```text
http://localhost:8501
```

---

### 4. Ejecutar generación de datos de observabilidad

```bash
python scripts/run_observability_eval.py
```

---

### 5. Ejecutar pruebas

```bash
pytest
```

O solo pruebas de observabilidad:

```bash
pytest tests/test_observability.py
```

---

## Uso del Portal

### Inicio

Muestra una vista general del estado del sistema:

- Ejecuciones recientes.
- Latencia promedio.
- Errores.
- Costo real de API.
- Actividad reciente.
- Notas operativas.

---

### Agente IA

Interfaz conversacional para buscar propiedades usando lenguaje natural.

Ejemplos:

```text
Busco departamento de 3 dormitorios en Las Condes por menos de 2500 UF.
```

```text
Necesito algo con piscina y cerca del metro.
```

```text
Muéstrame las alternativas más económicas disponibles.
```

---

### Dashboard

Vista ejecutiva con indicadores del agente:

- Ejecuciones.
- Latencia promedio.
- Latencia p95.
- Errores.
- Precisión.
- Consistencia.
- Tokens.
- Costo comparativo estimado.

---

### Trazabilidad

Vista de auditoría técnica del agente:

- Timeline de ejecuciones.
- Logs.
- Estado de cada consulta.
- Proveedor usado.
- Modelo usado.
- Costo real de API.
- Costo comparativo estimado.
- Tool calls inferidos.
- Registro original desde `observability_log`.

---

## Observabilidad

La capa de observabilidad permite revisar el comportamiento del agente en cada ejecución.

Cada consulta genera un `run_id` único y registra datos técnicos como latencia, proveedor, modelo, estado, errores, cantidad de resultados y consumo estimado de tokens.

La tabla principal es:

```text
observability_log
```

Ubicada en:

```text
backend/propiedades.db
```

---

## Seguridad y Privacidad

El proyecto considera las siguientes prácticas:

- Uso de variables de entorno mediante `.env`.
- Archivo `.env.example` sin claves reales.
- Exclusión de `.env` del repositorio.
- Registro de `query_hash` para trazabilidad.
- Uso de `query_preview` limitado.
- No registrar claves, tokens privados, RUT, teléfonos, correos ni direcciones exactas.
- Ejecución local del proveedor LLM mediante Ollama.
- Separación entre costo real de API y costo comparativo.
- Respuestas basadas en propiedades recuperadas.
- Validación humana recomendada para decisiones inmobiliarias.

---

## Estructura del Proyecto

```text
agente-inmobiliario/
├── app/
│   ├── __init__.py
│   ├── llm_service.py
│   ├── main.py
│   ├── memory.py
│   ├── observability.py
│   ├── planner.py
│   ├── rag_pipeline.py
│   ├── tools.py
│   └── prompts/
│       └── system_prompt.txt
│
├── backend/
│   ├── __init__.py
│   ├── data_pipeline.py
│   ├── db.py
│   └── propiedades.db
│
├── data/
│   ├── processed/
│   ├── raw/
│   └── observability/
│       ├── eval_results.csv
│       └── eval_summary.json
│
├── docs/
│   ├── architecture.md
│   └── security_responsible_ai.md
│
├── scripts/
│   └── run_observability_eval.py
│
├── scraping/
│   └── scraper.py
│
├── tests/
│   ├── test_data_pipeline.py
│   └── test_observability.py
│
├── ui/
│   ├── agent_portal.py
│   ├── agent_screen.py
│   ├── components.py
│   ├── data_access.py
│   ├── observability_dashboard.py
│   ├── styles.py
│   └── README.md
│
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── .gitignore
├── requirements.txt
├── test.py
└── README.md
```

---

## Comandos Rápidos

### Instalar dependencias

```bash
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

### Levantar Ollama

```bash
docker compose up -d
```

### Ejecutar portal

```bash
python -m streamlit run ui/agent_portal.py
```

### Generar datos de observabilidad

```bash
python scripts/run_observability_eval.py
```

### Ejecutar pruebas

```bash
pytest
```

---

## Limitaciones

- La latencia depende del hardware local.
- El modelo local puede tener menor calidad que modelos cloud más grandes.
- Los tokens pueden ser estimados si el proveedor no entrega desglose completo.
- El costo comparativo con OpenAI es referencial.
- Las recomendaciones inmobiliarias no reemplazan validación comercial, legal o profesional.

---

## Uso

Este proyecto está diseñado como una solución local de agente inmobiliario con IA, orientada a búsqueda, recomendación, monitoreo y trazabilidad técnica.
