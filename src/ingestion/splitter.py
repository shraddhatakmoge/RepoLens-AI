from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config.logging_config import get_logger


logger = get_logger(__name__)


def split_documents(
    documents: list[Document],
) -> list[Document]:

    logger.info(
        "Document splitting started: documents=%s",
        len(documents),
    )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
    )

    chunks = splitter.split_documents(
        documents
    )

    logger.info(
        "Document splitting completed: documents=%s | chunks=%s | chunk_size=%s | overlap=%s",
        len(documents),
        len(chunks),
        1000,
        150,
    )

    return chunks