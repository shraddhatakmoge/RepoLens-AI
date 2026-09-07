from src.config.logging_config import get_logger
from src.vectorstore.pinecone_store import hybrid_search


logger = get_logger(__name__)


def retrieve(
    query: str,
    namespace: str,
    k: int = 4,
):

    logger.info(
        "Retriever started: namespace=%s | k=%s | query_length=%s",
        namespace,
        k,
        len(query),
    )

    try:
        results = hybrid_search(
            query=query,
            namespace=namespace,
            k=k,
        )

        logger.info(
            "Retriever completed: namespace=%s | results=%s",
            namespace,
            len(results),
        )

        return results

    except Exception:
        logger.exception(
            "Retriever failed: namespace=%s",
            namespace,
        )
        raise