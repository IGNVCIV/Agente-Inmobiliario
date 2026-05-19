from app.main import RealEstateAgent


def main():
    agent = RealEstateAgent()
    agent.memory.limpiar()

    print("\n=== Demostración End-to-End del Agente Inmobiliario ===\n")

    query_1 = "Busco departamento de 3 dormitorios en Las Condes por menos de 2500 UF"
    print("Consulta 1:", query_1)
    print("Respuesta 1:")
    print(agent.respond(query_1))

    query_2 = "¿Y ahora con piscina y cerca del metro?"
    print("\nConsulta 2 (follow-up):", query_2)
    print("Respuesta 2:")
    print(agent.respond(query_2))

    print("\n=== Historial Guardado en Memoria ===")
    agent.memory.mostrar_historial()


if __name__ == "__main__":
    main()
