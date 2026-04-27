# UI Streamlit

Esta carpeta contiene la interfaz de usuario basada en Streamlit para el agente inmobiliario.

## Ejecutar

Activa el entorno virtual y ejecuta:

```powershell
.venv\Scripts\python.exe -m streamlit run ui/streamlit_app.py
```

## Descripción

- `streamlit_app.py`: Interfaz básica que envía la consulta al agente y muestra la respuesta.
- Usa `RealEstateAgent` desde `app/main.py`.
