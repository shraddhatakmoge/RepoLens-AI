import numpy as np
from google import genai
from google.genai import types
from langchain_core.embeddings import Embeddings

from src.config.settings import settings


class GeminiEmbeddings(Embeddings):
    def __init__(self):
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = "gemini-embedding-001"
        self.output_dimensionality = 768

    def _normalize(self, vector: list[float]) -> list[float]:
        vector = np.array(vector, dtype=np.float32)
        norm = np.linalg.norm(vector)

        if norm == 0:
            return vector.tolist()

        return (vector / norm).tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        result = self.client.models.embed_content(
            model=self.model,
            contents=texts,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=self.output_dimensionality,
            ),
        )

        return [
            self._normalize(embedding.values)
            for embedding in result.embeddings
        ]

    def embed_query(self, text: str) -> list[float]:
        result = self.client.models.embed_content(
            model=self.model,
            contents=text,
            config=types.EmbedContentConfig(
                task_type="CODE_RETRIEVAL_QUERY",
                output_dimensionality=self.output_dimensionality,
            ),
        )

        return self._normalize(result.embeddings[0].values)


embeddings = GeminiEmbeddings()