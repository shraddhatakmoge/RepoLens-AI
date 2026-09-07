from langchain_groq import ChatGroq

from src.config.logging_config import get_logger
from src.config.settings import settings
from src.rag.prompts import RAG_PROMPT
from src.rag.retriever import retrieve


logger = get_logger(__name__)


def get_llm():

    logger.info(
        "Initializing RAG LLM: model=openai/gpt-oss-120b"
    )

    llm = ChatGroq(
        model="openai/gpt-oss-120b",
        temperature=0,
        api_key=settings.groq_api_key,
    )

    logger.info(
        "RAG LLM initialized successfully"
    )

    return llm


def format_documents(documents):

    logger.info(
        "Formatting retrieved documents: documents=%s",
        len(documents),
    )

    context = "\n\n".join(
        f"File: {doc.metadata.get('path')}\n{doc.page_content}"
        for doc in documents
    )

    logger.info(
        "Document context formatted: documents=%s | chars=%s",
        len(documents),
        len(context),
    )

    return context


def ask_repository(
    question: str,
    owner: str,
    repo: str,
    k: int = 4,
):

    namespace = f"{owner}-{repo}"

    logger.info(
        "RAG chain started: repository=%s/%s | k=%s | question_length=%s",
        owner,
        repo,
        k,
        len(question),
    )

    try:
        documents = retrieve(
            query=question,
            namespace=namespace,
            k=k,
        )

        logger.info(
            "Documents retrieved: repository=%s/%s | documents=%s",
            owner,
            repo,
            len(documents),
        )

        context = format_documents(
            documents
        )

        prompt = RAG_PROMPT.invoke(
            {
                "context": context,
                "question": question,
            }
        )

        logger.info(
            "RAG prompt created: repository=%s/%s",
            owner,
            repo,
        )

        response = get_llm().invoke(
            prompt
        )

        logger.info(
            "RAG response generated: repository=%s/%s | response_chars=%s",
            owner,
            repo,
            len(response.content),
        )

        return response.content

    except Exception:
        logger.exception(
            "RAG chain failed: repository=%s/%s",
            owner,
            repo,
        )
        raise