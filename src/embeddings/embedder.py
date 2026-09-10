import logging

from langchain_core.embeddings import Embeddings
from pinecone import Pinecone

from src.config.settings import settings


logger = logging.getLogger(__name__)


class PineconeEmbeddings(Embeddings):

    model = "llama-text-embed-v2"
    dimension = 384
    batch_size = 96

    def __init__(
        self,
        *args,
        **kwargs,
    ):
        self.client = Pinecone(
            api_key=settings.pinecone_api_key
        )

        logger.info(
            "Pinecone embeddings initialized: model=%s | dimension=%s",
            self.model,
            self.dimension,
        )

    def _extract_values(
        self,
        result,
    ):
        vectors = []

        for item in result.data:

            values = getattr(
                item,
                "values",
                None,
            )

            if values is None and isinstance(
                item,
                dict,
            ):
                values = item.get("values")

            if values is None:
                raise ValueError(
                    "Pinecone embedding response "
                    "did not contain vector values."
                )

            vectors.append(list(values))

        return vectors

    def _embed_batch(
        self,
        texts: list[str],
        input_type: str,
    ) -> list[list[float]]:

        if not texts:
            return []

        result = self.client.inference.embed(
            model=self.model,
            inputs=texts,
            parameters={
                "input_type": input_type,
                "truncate": "END",
                "dimension": self.dimension,
            },
        )

        return self._extract_values(result)

    def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:

        if not texts:
            return []

        logger.info(
            "Embedding documents with Pinecone: texts=%s",
            len(texts),
        )

        embeddings = []

        for start in range(
            0,
            len(texts),
            self.batch_size,
        ):

            batch = texts[
                start:start + self.batch_size
            ]

            logger.info(
                "Pinecone embedding batch: start=%s | batch_size=%s",
                start,
                len(batch),
            )

            batch_embeddings = self._embed_batch(
                batch,
                input_type="passage",
            )

            embeddings.extend(batch_embeddings)

        if len(embeddings) != len(texts):
            raise ValueError(
                "Number of embeddings does not match "
                "number of input texts."
            )

        logger.info(
            "Pinecone document embeddings completed: texts=%s",
            len(embeddings),
        )

        return embeddings

    def embed_query(
        self,
        text: str,
    ) -> list[float]:

        if not text or not text.strip():
            raise ValueError(
                "Query text cannot be empty."
            )

        logger.info(
            "Embedding query with Pinecone: chars=%s",
            len(text),
        )

        embeddings = self._embed_batch(
            [text],
            input_type="query",
        )

        if not embeddings:
            raise ValueError(
                "Pinecone returned no query embedding."
            )

        return embeddings[0]


embeddings = PineconeEmbeddings()

GeminiEmbeddings = PineconeEmbeddings
CustomGeminiEmbeddings = PineconeEmbeddings
GeminiEmbedding = PineconeEmbeddings