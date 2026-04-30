import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

from backend.db import cargar_propiedades_db
from backend.data_pipeline import DataPipeline


class RAGPipeline:
    def __init__(self, source: str = 'data/processed/propiedades_detalle.csv', model_name: str = 'all-MiniLM-L6-v2'):
        self.source = source
        self.pipeline = DataPipeline()
        self.vectorstore = None
        self.load_and_index_data()

    def load_and_index_data(self):
        if self.source.endswith('.db'):
            df = cargar_propiedades_db(self.source)
        else:
            df = pd.read_csv(self.source)

        df_clean = self.pipeline.clean_dataframe(df)

        documents = []
        for _, row in df_clean.iterrows():
            metadata = {
                "id": row.get("id"),
                "titulo": row.get("titulo"),
                "comuna": row.get("comuna"),
                "precio_uf": row.get("precio_uf"),
                "link": row.get("link"),
            }
            documents.append(Document(page_content=row.get("rag_text", ""), metadata=metadata))

        embeddings = HuggingFaceEmbeddings(model_name='sentence-transformers/all-MiniLM-L6-v2')
        self.vectorstore = FAISS.from_documents(documents, embeddings)

    def retrieve_properties(self, query: str, k: int = 3):
        docs = self.vectorstore.similarity_search(query, k=k)
        return [doc.metadata for doc in docs]
