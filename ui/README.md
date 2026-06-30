# UI Streamlit

La entrada principal de la interfaz es:

```powershell
python -m streamlit run ui/agent_portal.py
```

## Pantallas

- **Home**: pantalla inicial para elegir qué hacer. También muestra resumen ejecutivo y actividad reciente.
- **AI Agent**: interfaz conversacional con sugerencias, filtros claros y respuestas legibles.
- **Dashboard**: KPIs ejecutivos, actividad reciente, costos simulados y resumen de propiedades.
- **Traceability**: timeline, logs, tool calls inferidos y auditoría de ejecuciones.

## Navegación

La app tiene dos formas de navegación:

1. **Sidebar** de Streamlit.
2. **Navegación superior fija dentro del contenido**.

Esto evita depender únicamente del sidebar. Si el usuario lo cierra, igual puede cambiar de pantalla desde los botones superiores.

## Archivos

- `agent_portal.py`: punto de entrada, navegación, Home y Dashboard.
- `agent_screen.py`: experiencia conversacional del agente.
- `observability_dashboard.py`: trazabilidad y auditoría.
- `styles.py`: CSS global, fuentes, contraste, tablas claras, filtros y chat.
- `components.py`: componentes visuales reutilizables.
- `data_access.py`: carga de SQLite, CSV y JSON de observabilidad.

## Ajustes visuales importantes

- El historial del chat usa burbujas propias en vez de depender del estilo nativo de `st.chat_message`, para evitar texto ilegible con temas oscuros.
- El input del agente usa formulario estable en vez de `st.chat_input`, porque en algunos temas se veía como una barra negra grande.
- Las tablas compactas se renderizan en HTML claro para evitar que `st.dataframe` herede estilos oscuros.
- Las sugerencias se basan en comunas reales de `data/processed/propiedades_detalle.csv`.
