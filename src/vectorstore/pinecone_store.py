from pathlib import Path
import pickle

from langchain_pinecone import PineconeVectorStore
from rank_bm25 import BM25Okapi


from src.config.logging_config import get_logger
from src.config.settings import settings
from src.embeddings.embedder import embeddings


logger = get_logger(__name__)


vectorstore = PineconeVectorStore(
    index_name=settings.pinecone_index_name,
    embedding=embeddings,
    pinecone_api_key=settings.pinecone_api_key,
)




BM25_DIR = Path("data/bm25")
BM25_DIR.mkdir(parents=True, exist_ok=True)


def _bm25_path(namespace: str):
    return BM25_DIR / f"{namespace}.pkl"


def _tokenize(text: str):
    return text.lower().split()


def _load_bm25_data(namespace: str):

    path = _bm25_path(namespace)

    if not path.exists():
        logger.info(
            "BM25 index not found: namespace=%s",
            namespace,
        )
        return [], None

    try:
        with open(path, "rb") as file:
            data = pickle.load(file)

        documents = data["documents"]

        tokenized_documents = [
            _tokenize(document.page_content)
            for document in documents
        ]

        bm25 = BM25Okapi(
            tokenized_documents
        )

        logger.info(
            "BM25 index loaded: namespace=%s | documents=%s",
            namespace,
            len(documents),
        )

        return documents, bm25

    except Exception:
        logger.exception(
            "Failed to load BM25 index: namespace=%s",
            namespace,
        )
        raise


def add_documents(
    documents,
    namespace: str,
):

    documents = list(documents)

    logger.info(
        "Adding documents to vector store: namespace=%s | documents=%s",
        namespace,
        len(documents),
    )

    try:
        vectorstore.add_documents(
            documents,
            namespace=namespace,
        )

        logger.info(
            "Documents added to Pinecone: namespace=%s | documents=%s",
            namespace,
            len(documents),
        )

        path = _bm25_path(namespace)

        existing_documents, _ = _load_bm25_data(
            namespace
        )

        all_documents = (
            existing_documents
            + documents
        )

        with open(path, "wb") as file:
            pickle.dump(
                {
                    "documents": all_documents,
                },
                file,
            )

        logger.info(
            "BM25 index updated: namespace=%s | total_documents=%s",
            namespace,
            len(all_documents),
        )

    except Exception:
        logger.exception(
            "Failed to add documents: namespace=%s",
            namespace,
        )
        raise


def similarity_search(
    query: str,
    namespace: str,
    k: int = 20,
):

    logger.info(
        "Dense search started: namespace=%s | k=%s | query_length=%s",
        namespace,
        k,
        len(query),
    )

    try:
        results = vectorstore.similarity_search(
            query,
            k=k,
            namespace=namespace,
        )

        logger.info(
            "Dense search completed: namespace=%s | results=%s",
            namespace,
            len(results),
        )

        return results

    except Exception:
        logger.exception(
            "Dense search failed: namespace=%s",
            namespace,
        )
        raise


def bm25_search(
    query: str,
    namespace: str,
    k: int = 20,
):

    logger.info(
        "BM25 search started: namespace=%s | k=%s | query_length=%s",
        namespace,
        k,
        len(query),
    )

    try:
        documents, bm25 = _load_bm25_data(
            namespace
        )

        if not documents or bm25 is None:
            logger.warning(
                "BM25 search skipped: no index data | namespace=%s",
                namespace,
            )
            return []

        scores = bm25.get_scores(
            _tokenize(query)
        )

        ranked_indexes = sorted(
            range(len(scores)),
            key=lambda index: scores[index],
            reverse=True,
        )[:k]

        results = [
            documents[index]
            for index in ranked_indexes
        ]

        logger.info(
            "BM25 search completed: namespace=%s | results=%s",
            namespace,
            len(results),
        )

        return results

    except Exception:
        logger.exception(
            "BM25 search failed: namespace=%s",
            namespace,
        )
        raise


def _document_key(document):

    return (
        document.metadata.get("source")
        or document.metadata.get("file_path")
        or document.metadata.get("path")
        or document.page_content
    )


def reciprocal_rank_fusion(
    result_lists,
    k: int = 15,
    rrf_constant: int = 60,
):

    logger.info(
        "RRF started: result_lists=%s | k=%s | rrf_constant=%s",
        len(result_lists),
        k,
        rrf_constant,
    )

    scores = {}
    documents = {}

    for results in result_lists:

        for rank, document in enumerate(
            results,
            start=1,
        ):

            key = _document_key(
                document
            )

            scores[key] = (
                scores.get(key, 0)
                + (
                    1
                    / (
                        rrf_constant
                        + rank
                    )
                )
            )

            documents[key] = document

    ranked_documents = sorted(
        documents.values(),
        key=lambda document: scores[
            _document_key(document)
        ],
        reverse=True,
    )

    results = ranked_documents[:k]

    logger.info(
        "RRF completed: unique_documents=%s | candidates=%s",
        len(documents),
        len(results),
    )

    return results


def rerank_documents(
    query: str,
    documents,
    k: int = 4,
):

    if not documents:
        logger.warning(
            "Reranking skipped: no candidate documents"
        )
        return []

    logger.info(
        "Reranking started: candidates=%s | final_k=%s",
        len(documents),
        k,
    )

    try:
        pairs = [
    (
        query,
        f"File: {document.metadata.get('path', '')}\n\n"
        f"{document.page_content}",
    )
    for document in documents
]

        scores = reranker.predict(
            pairs
        )

        ranked_documents = sorted(
            zip(
                documents,
                scores,
            ),
            key=lambda item: item[1],
            reverse=True,
        )

        results = [
            document
            for document, score
            in ranked_documents[:k]
        ]

        logger.info(
            "Reranking completed: candidates=%s | results=%s",
            len(documents),
            len(results),
        )

        return results

    except Exception:
        logger.exception(
            "Reranking failed"
        )
        raise


def hybrid_search(
    query: str,
    namespace: str,
    k: int = 4,
):

    logger.info(
        "Advanced hybrid search started: namespace=%s | k=%s | query_length=%s",
        namespace,
        k,
        len(query),
    )

    try:
        dense_results = similarity_search(
            query=query,
            namespace=namespace,
            k=20,
        )

        sparse_results = bm25_search(
            query=query,
            namespace=namespace,
            k=20,
        )

        fused_results = reciprocal_rank_fusion(
            result_lists=[
                dense_results,
                sparse_results,
            ],
            k=15,
        )

        final_results = fused_results[:k]

        logger.info(
            "Advanced hybrid search completed: namespace=%s | dense=%s | sparse=%s | fused=%s | final=%s",
            namespace,
            len(dense_results),
            len(sparse_results),
            len(fused_results),
            len(final_results),
        )

        return final_results

    except Exception:
        logger.exception(
            "Advanced hybrid search failed: namespace=%s",
            namespace,
        )
        raise