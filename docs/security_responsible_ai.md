# Seguridad, privacidad y uso responsable del agente IA inmobiliario

## Alcance

Este documento describe los criterios técnicos de seguridad, privacidad, observabilidad, costos y uso responsable aplicables al agente inmobiliario IA. Su objetivo es dejar explícitas las decisiones de diseño tomadas para la Fase 6, especialmente considerando que el proveedor principal de generación LLM es Ollama ejecutado localmente en Docker.

El documento no reemplaza una revisión legal ni una auditoría externa. Debe entenderse como una guía técnica interna para reducir riesgos y mejorar la trazabilidad del sistema.

---

## 1. Gestión de proveedores LLM

El agente utiliza **Ollama local como proveedor principal** para la generación de respuestas y extracción de criterios. Ollama se ejecuta en Docker y expone una API compatible con OpenAI, lo que permite usar el cliente de OpenAI como interfaz técnica sin depender de una API externa para la generación principal.

La configuración esperada debe mantenerse mediante variables de entorno, evitando dejar modelos o proveedores hardcodeados en el código fuente. Las variables principales son:

| Variable | Uso esperado |
|---|---|
| `LLM_PROVIDER` | Define el proveedor activo. Para esta fase, el valor principal es `ollama`. |
| `OLLAMA_BASE_URL` | URL base del servicio Ollama. En Docker puede apuntar al contenedor; en local puede usar `http://localhost:11434/v1`. |
| `OLLAMA_MODEL` | Modelo local usado por Ollama, por ejemplo `llama3.2:3b`. |
| `OPENAI_SIM_MODEL` | Modelo usado solo para simulaciones referenciales de costo OpenAI. |
| `OPENAI_MODEL` | Modelo alternativo o de referencia si se habilita OpenAI. |
| `GITHUB_MODEL` | Modelo alternativo o de referencia si se habilita GitHub Models. |

OpenAI y GitHub no se consideran proveedores principales en esta fase. Pueden quedar documentados como opciones alternativas, respaldo futuro o referencia comparativa, pero el flujo principal debe funcionar con Ollama local.

---

## 2. Privacidad

Al utilizar Ollama local, las consultas del usuario **no necesitan salir hacia una API externa para la generación LLM**. Esto reduce la exposición de datos frente a proveedores externos, aunque no elimina la necesidad de aplicar controles internos sobre logs, base de datos y archivos del proyecto.

La observabilidad debe registrar datos mínimos y útiles para depuración y evaluación, evitando almacenar consultas completas con información sensible. En particular, `observability_log` utiliza:

- `query_hash`: hash de la consulta normalizada, útil para identificar repeticiones sin guardar el texto completo como identificador principal.
- `query_preview`: vista corta y limitada de la consulta, pensada para diagnóstico rápido.

El campo `query_preview` debe mantenerse como dato no sensible. Si una consulta incluye datos personales, se debe evitar persistirlos o se deben anonimizar antes de registrarlos.

No se deben registrar en logs, observabilidad ni mensajes de error:

- RUT.
- Teléfonos.
- Correos electrónicos.
- Direcciones exactas.
- Claves, tokens o secretos.

Para búsquedas inmobiliarias, es aceptable registrar criterios generales como comuna, rango de precio, cantidad de dormitorios, cantidad de baños o características generales, siempre que no identifiquen directamente a una persona o domicilio específico.

---

## 3. Seguridad de claves y configuración

El archivo `.env` contiene configuración local y potencialmente secretos, por lo tanto **no debe subirse al repositorio** ni compartirse como evidencia de entrega. Debe mantenerse excluido mediante `.gitignore`.

El archivo `.env.example` sí debe mantenerse versionado, pero solo con valores de ejemplo. Su función es documentar las variables necesarias para ejecutar el proyecto sin exponer credenciales reales.

Buenas prácticas aplicables:

- No hardcodear claves, tokens, usuarios o contraseñas dentro del código.
- No imprimir claves en consola, logs, dashboards ni capturas de pantalla.
- No incluir `.env` en commits, zips de entrega pública ni evidencias académicas.
- Usar nombres de variables claros para separar configuración local, proveedor LLM, base de datos y simulación de costos.
- Revisar que los mensajes de error no incluyan secretos completos.

Ejemplo de configuración segura para esta fase:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434/v1
OLLAMA_MODEL=llama3.2:3b
OPENAI_SIM_MODEL=gpt-4o-mini
```

Las claves de OpenAI, GitHub o Banco Central solo deben agregarse si realmente se usan en el entorno local y nunca deben aparecer en capturas, logs o archivos versionados.

---

## 4. Seguridad de base de datos

El agente utiliza SQLite como fuente de datos estructurada para propiedades y registros operativos. Las consultas a la base de datos deben seguir un enfoque restrictivo y controlado.

Controles esperados:

- Usar consultas parametrizadas para evitar inyección SQL.
- Construir filtros de búsqueda desde criterios validados, no desde SQL libre escrito por el usuario.
- Limitar la cantidad de resultados devueltos por consulta.
- Bloquear operaciones peligrosas como `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER` o ejecución de múltiples sentencias cuando provengan de entrada del usuario.
- Manejar errores de forma controlada, sin exponer stack traces, rutas internas sensibles o contenido completo de la base de datos al usuario final.
- Registrar fallos de manera resumida, manteniendo el flujo principal del agente estable.

El agente debe consultar propiedades mediante funciones internas y parámetros controlados. El usuario no debe poder ejecutar SQL directo contra SQLite.

---

## 5. Uso responsable del agente

El agente debe actuar como asistente de búsqueda y apoyo informativo, no como una fuente definitiva de decisión inmobiliaria.

Principios de uso responsable:

- No inventar propiedades, precios, ubicaciones, enlaces ni características.
- Responder únicamente con datos recuperados desde SQLite, RAG o fuentes internas cargadas en el proyecto.
- Si no hay resultados, indicarlo explícitamente en lugar de fabricar alternativas.
- Diferenciar entre datos recuperados y comentarios explicativos del asistente.
- Evitar prometer disponibilidad real de una propiedad si el dato no fue validado recientemente.
- No entregar recomendaciones financieras, legales o contractuales como si fueran definitivas.
- Tratar las recomendaciones inmobiliarias como apoyo preliminar que requiere validación humana.

Una respuesta adecuada debe explicar por qué las propiedades recuperadas coinciden con la búsqueda, pero sin agregar atributos que no estén en los datos.

---

## 6. Costos y sostenibilidad

Al ejecutarse con Ollama local, el agente tiene **costo de API externo estimado de 0 USD** para la generación LLM principal. Esto significa que no se paga por token a un proveedor externo durante el uso local del modelo.

Sin embargo, ese valor no representa costo total de operación. Pueden existir costos asociados a:

- Hardware local.
- Consumo eléctrico.
- Tiempo de ejecución.
- Mantención del entorno Docker.
- Almacenamiento y recursos de la máquina anfitriona.

El campo `estimated_openai_cost_usd` debe interpretarse como una **simulación referencial**. No corresponde a facturación real, no representa un cargo cobrado por OpenAI y no debe presentarse como gasto efectivo del proyecto.

Esta simulación sirve para comparar sostenibilidad y escalabilidad entre dos escenarios:

1. Ejecución local con Ollama, sin costo externo por API.
2. Ejecución hipotética con un modelo cloud, estimando costo por tokens.

Para evitar confusión, los reportes o dashboards deben acompañar el valor simulado con una nota visible, por ejemplo:

> `estimated_openai_cost_usd` es una estimación académica referencial basada en tokens; no representa facturación real.

---

## 7. Limitaciones

El uso de un modelo local mejora el control sobre el entorno, pero también introduce limitaciones que deben declararse de forma transparente.

Limitaciones principales:

- El modelo local puede tener menor calidad, menor razonamiento o menor seguimiento de instrucciones que algunos modelos cloud.
- La calidad de las respuestas depende del modelo descargado en Ollama y de su configuración.
- Si Ollama no entrega separación clara entre tokens de entrada y salida, las métricas pueden ser aproximadas.
- La estimación de costos basada en tokens puede ser parcial si solo existe `total_tokens`.
- El rendimiento depende del hardware local: CPU, RAM, GPU disponible y carga del sistema.
- La ejecución en Docker requiere que el servicio Ollama esté levantado y que el modelo haya sido descargado previamente.
- Usar Ollama local reduce la dependencia de APIs externas, pero no reemplaza controles de seguridad, revisión humana ni validación de datos.

---

## Criterio de cierre para Fase 6

Para considerar esta fase correctamente documentada, el proyecto debe demostrar:

- Proveedor principal configurado como Ollama local.
- Variables de entorno documentadas en `.env.example`.
- `.env` excluido del repositorio.
- Logs sin datos personales directos ni secretos.
- Observabilidad basada en hash, preview limitado, latencias, tokens y costos referenciales.
- Respuestas generadas solo desde datos recuperados.
- Declaración explícita de limitaciones y necesidad de validación humana.
