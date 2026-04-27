import pandas as pd

from backend.data_pipeline import DataPipeline


def test_clean_dataframe_normalizes_fields():
    df = pd.DataFrame([
        {
            "id": 1,
            "titulo": "Departamento hermoso",
            "moneda": "CLP",
            "precio_valor": "3.200.000",
            "ubicacion_raw": "Las Condes / Santiago",
            "comuna": "las condes",
            "dormitorios": "3",
            "banos": "2",
            "metros": "120",
            "descripcion": "Departamento con piscina y gimnasio.",
            "amenities": "piscina, gym",
            "link": "https://example.com",
        }
    ])

    pipeline = DataPipeline(uf_value=40000)
    cleaned = pipeline.clean_dataframe(df)

    assert cleaned.loc[0, "comuna"] == "Las Condes"
    assert cleaned.loc[0, "precio_uf"] == 80.0
    assert cleaned.loc[0, "dormitorios"] == 3
    assert cleaned.loc[0, "banos"] == 2
    assert "Descripción:" in cleaned.loc[0, "rag_text"]
    assert "Amenities: gimnasio" in cleaned.loc[0, "rag_text"] or "Amenities: piscina" in cleaned.loc[0, "rag_text"]
