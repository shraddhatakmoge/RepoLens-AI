from langchain_core.prompts import ChatPromptTemplate

from src.config.logging_config import get_logger


logger = get_logger(__name__)


RAG_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are RepoLens AI, a GitHub repository investigator.

Answer questions using only the provided repository context.

If the context does not contain enough information, say so clearly.

Always mention relevant file paths when they are available.

Repository context:

{context}""",
        ),
        (
            "human",
            "{question}",
        ),
    ]
)


logger.info(
    "RAG prompt initialized successfully"
)