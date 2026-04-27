import streamlit as st

from app.main import RealEstateAgent

agent = RealEstateAgent()

st.set_page_config(page_title="Agente Inmobiliario IA", layout="wide")
st.title("Agente Inmobiliario IA")
st.write(
    "Esta interfaz usa el agente inmobiliario para responder consultas sobre propiedades y buscar resultados relevantes."
)

query = st.text_input("Consulta sobre propiedades", placeholder="Ej. departamento de 3 dormitorios en Las Condes")

if st.button("Consultar"):
    if not query:
        st.warning("Ingresa una consulta antes de presionar Consultar.")
    else:
        with st.spinner("Consultando al agente..."):
            response = agent.respond(query)
        st.markdown("### Respuesta")
        st.write(response)
