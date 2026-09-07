from langchain_huggingface import HuggingFaceEmbeddings

from src.config.logging_config import get_logger


logger = get_logger(__name__)


logger.info(
    "Initializing embedding model: sentence-transformers/all-MiniLM-L6-v2"
)


embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)


logger.info(
    "Embedding model initialized successfully"
)