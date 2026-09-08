import time

from google import genai
from google.genai import types

from src.config.logging_config import get_logger
from src.config.settings import settings


logger = get_logger(__name__)


class GeminiEmbeddings:

    def __init__(self):

        self.client = genai.Client(
            api_key=settings.gemini_api_key
        )

        self.model = "gemini-embedding-001"
        self.output_dimensionality = 768
        self.batch_size = 100
        self.rate_limit_wait = 65

        logger.info(
            "Gemini embeddings initialized: model=%s | dimension=%s | batch_size=%s",
            self.model,
            self.output_dimensionality,
            self.batch_size,
        )

    def _embed_batch(
        self,
        texts: list[str],
    ) -> list[list[float]]:

        result = self.client.models.embed_content(
            model=self.model,
            contents=texts,
            config=types.EmbedContentConfig(
                output_dimensionality=self.output_dimensionality,
                task_type="RETRIEVAL_DOCUMENT",
            ),
        )

        return [
            embedding.values
            for embedding in result.embeddings
        ]

    def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:

        logger.info(
            "Embedding documents: texts=%s",
            len(texts),
        )

        embeddings = []

        for start in range(
            0,
            len(texts),
            self.batch_size,
        ):

            if start > 0:
                logger.info(
                    "Gemini embedding quota window reached. Waiting %s seconds before next batch",
                    self.rate_limit_wait,
                )

                time.sleep(self.rate_limit_wait)

            batch = texts[
                start:start + self.batch_size
            ]

            logger.info(
                "Embedding batch: start=%s | batch_size=%s",
                start,
                len(batch),
            )

            batch_embeddings = self._embed_batch(
                batch
            )

            embeddings.extend(
                batch_embeddings
            )

        logger.info(
            "Document embeddings completed: texts=%s | embeddings=%s",
            len(texts),
            len(embeddings),
        )

        return embeddings

    def embed_query(
        self,
        text: str,
    ) -> list[float]:

        logger.info(
            "Embedding query: chars=%s",
            len(text),
        )

        result = self.client.models.embed_content(
            model=self.model,
            contents=text,
            config=types.EmbedContentConfig(
                output_dimensionality=self.output_dimensionality,
                task_type="RETRIEVAL_QUERY",
            ),
        )

        return result.embeddings[0].values


embeddings = GeminiEmbeddings()