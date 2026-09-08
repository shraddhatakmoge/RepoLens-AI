import uuid
import asyncio

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(
        asyncio.WindowsSelectorEventLoopPolicy()
    )

from fastapi import FastAPI
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.agent.agent import RepoLensAgent
from src.config.logging_config import (
    get_logger,
    setup_logging,
)
from src.database.chat_sessions import (
    create_chat_session,
    delete_chat_session,
    get_chat_sessions,
    init_chat_sessions,
    update_chat_session,
)
from src.ingestion.loader import load_repository
from src.ingestion.splitter import split_documents
from src.vectorstore.pinecone_store import add_documents


setup_logging()

logger = get_logger(__name__)


app = FastAPI(
    title="RepoLens AI API",
    version="1.0.0",
)


init_chat_sessions()

logger.info("RepoLens AI API started")


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    repo: str = Field(min_length=1)
    thread_id: str = Field(min_length=1)


class CreateChatRequest(BaseModel):
    owner: str = Field(min_length=1)
    repo: str = Field(min_length=1)


class RenameChatRequest(BaseModel):
    title: str = Field(min_length=1)


class IndexRepositoryRequest(BaseModel):
    owner: str = Field(min_length=1)
    repo: str = Field(min_length=1)


async def prepare_repository(
    owner: str,
    repo: str,
):
    logger.info(
        "Repository indexing started: %s/%s",
        owner,
        repo,
    )

    try:
        documents = await load_repository(
            owner=owner,
            repo=repo,
        )

        if not documents:
            logger.warning(
                "Repository contains no useful files: %s/%s",
                owner,
                repo,
            )

            raise HTTPException(
                status_code=404,
                detail="No useful files found in the repository.",
            )

        logger.info(
            "Repository loaded: %s/%s | files=%s",
            owner,
            repo,
            len(documents),
        )

        chunks = split_documents(documents)

        if not chunks:
            logger.warning(
                "Repository produced no chunks: %s/%s",
                owner,
                repo,
            )

            raise HTTPException(
                status_code=422,
                detail="Repository could not be processed into searchable content.",
            )

        logger.info(
            "Repository split into chunks: %s/%s | chunks=%s",
            owner,
            repo,
            len(chunks),
        )

        namespace = f"{owner}-{repo}"

        add_documents(
            documents=chunks,
            namespace=namespace,
        )

        logger.info(
            "Repository indexed successfully: %s/%s | files=%s | chunks=%s",
            owner,
            repo,
            len(documents),
            len(chunks),
        )

        return len(documents), len(chunks)

    except HTTPException:
        raise

    except Exception:
        logger.exception(
            "Repository preparation failed: %s/%s",
            owner,
            repo,
        )
        raise


@app.get("/health")
async def health():

    logger.info("Health check requested")

    return {
        "status": "ok",
        "service": "RepoLens AI API",
    }


@app.get("/chats")
async def get_chats():

    logger.info("Fetching chat sessions")

    try:
        chats = get_chat_sessions()

        logger.info(
            "Chat sessions fetched: count=%s",
            len(chats),
        )

        return chats

    except Exception:
        logger.exception(
            "Failed to fetch chat sessions"
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to fetch chat sessions.",
        )


@app.post("/chats")
async def create_chat(
    request: CreateChatRequest,
):

    owner = request.owner.strip()
    repo = request.repo.strip()

    if not owner or not repo:
        raise HTTPException(
            status_code=400,
            detail="Owner and repository are required.",
        )

    thread_id = str(uuid.uuid4())

    logger.info(
        "Creating chat: thread_id=%s | repository=%s/%s",
        thread_id,
        owner,
        repo,
    )

    try:
        create_chat_session(
            thread_id=thread_id,
            owner=owner,
            repo=repo,
        )

        logger.info(
            "Chat created successfully: thread_id=%s",
            thread_id,
        )

        return {
            "thread_id": thread_id,
            "owner": owner,
            "repo": repo,
            "title": "New Chat",
        }

    except Exception:
        logger.exception(
            "Failed to create chat: thread_id=%s",
            thread_id,
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to create chat.",
        )


@app.get("/chats/{thread_id}")
async def get_chat(
    thread_id: str,
):

    logger.info(
        "Fetching chat: thread_id=%s",
        thread_id,
    )

    try:
        chats = get_chat_sessions()

        chat = next(
            (
                chat
                for chat in chats
                if chat["thread_id"] == thread_id
            ),
            None,
        )

        if chat is None:
            logger.warning(
                "Chat not found: thread_id=%s",
                thread_id,
            )

            raise HTTPException(
                status_code=404,
                detail="Chat not found.",
            )

        agent = RepoLensAgent()

        history = await agent.get_history(
            owner=chat["owner"],
            repo=chat["repo"],
            thread_id=thread_id,
        )

        logger.info(
            "Chat history fetched: thread_id=%s | messages=%s",
            thread_id,
            len(history),
        )

        return {
            "chat": chat,
            "history": history,
        }

    except HTTPException:
        raise

    except Exception:
        logger.exception(
            "Failed to fetch chat: thread_id=%s",
            thread_id,
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to fetch chat history.",
        )


@app.patch("/chats/{thread_id}")
async def rename_chat(
    thread_id: str,
    request: RenameChatRequest,
):

    title = request.title.strip()

    if not title:
        logger.warning(
            "Rename rejected: empty title | thread_id=%s",
            thread_id,
        )

        raise HTTPException(
            status_code=400,
            detail="Chat title cannot be empty.",
        )

    logger.info(
        "Renaming chat: thread_id=%s",
        thread_id,
    )

    try:
        chats = get_chat_sessions()

        chat = next(
            (
                chat
                for chat in chats
                if chat["thread_id"] == thread_id
            ),
            None,
        )

        if chat is None:
            logger.warning(
                "Rename failed: chat not found | thread_id=%s",
                thread_id,
            )

            raise HTTPException(
                status_code=404,
                detail="Chat not found.",
            )

        update_chat_session(
            thread_id=thread_id,
            title=title,
        )

        logger.info(
            "Chat renamed successfully: thread_id=%s",
            thread_id,
        )

        return {
            "thread_id": thread_id,
            "title": title,
        }

    except HTTPException:
        raise

    except Exception:
        logger.exception(
            "Failed to rename chat: thread_id=%s",
            thread_id,
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to rename chat.",
        )


@app.delete("/chats/{thread_id}")
async def delete_chat(
    thread_id: str,
):

    logger.info(
        "Chat deletion requested: thread_id=%s",
        thread_id,
    )

    try:
        chats = get_chat_sessions()

        chat = next(
            (
                chat
                for chat in chats
                if chat["thread_id"] == thread_id
            ),
            None,
        )

        if chat is None:
            logger.warning(
                "Delete failed: chat not found | thread_id=%s",
                thread_id,
            )

            raise HTTPException(
                status_code=404,
                detail="Chat not found.",
            )

        agent = RepoLensAgent()

        await agent.delete_thread(
            thread_id
        )

        delete_chat_session(
            thread_id
        )

        logger.info(
            "Chat deleted successfully: thread_id=%s",
            thread_id,
        )

        return {
            "message": "Chat deleted successfully.",
            "thread_id": thread_id,
        }

    except HTTPException:
        raise

    except Exception:
        logger.exception(
            "Failed to delete chat: thread_id=%s",
            thread_id,
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to delete chat.",
        )


@app.post("/chat")
async def chat(
    request: ChatRequest,
):

    question = request.question.strip()
    owner = request.owner.strip()
    repo = request.repo.strip()
    thread_id = request.thread_id.strip()

    if not question:
        logger.warning(
            "Chat request rejected: empty question | thread_id=%s",
            thread_id,
        )

        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty.",
        )

    if not owner or not repo or not thread_id:
        raise HTTPException(
            status_code=400,
            detail="Owner, repository, and thread ID are required.",
        )

    logger.info(
        "Chat request received: thread_id=%s | repository=%s/%s",
        thread_id,
        owner,
        repo,
    )

    try:
        agent = RepoLensAgent()

        answer = await agent.ask(
            question=question,
            owner=owner,
            repo=repo,
            thread_id=thread_id,
        )

        if not answer:
            logger.warning(
                "Agent returned empty response: thread_id=%s",
                thread_id,
            )

            raise HTTPException(
                status_code=502,
                detail="The AI agent returned an empty response.",
            )

        logger.info(
            "Chat request completed: thread_id=%s",
            thread_id,
        )

        return {
            "answer": answer,
            "thread_id": thread_id,
        }

    except HTTPException:
        raise

    except Exception:
        logger.exception(
            "Chat request failed: thread_id=%s",
            thread_id,
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to process the chat request.",
        )


@app.post("/repositories/index")
async def index_repository(
    request: IndexRepositoryRequest,
):

    owner = request.owner.strip()
    repo = request.repo.strip()

    if not owner or not repo:
        raise HTTPException(
            status_code=400,
            detail="Owner and repository are required.",
        )

    logger.info(
        "Repository indexing request received: %s/%s",
        owner,
        repo,
    )

    try:
        documents_count, chunks_count = (
            await prepare_repository(
                owner=owner,
                repo=repo,
            )
        )

        return {
            "status": "success",
            "owner": owner,
            "repo": repo,
            "documents": documents_count,
            "chunks": chunks_count,
        }

    except HTTPException:
        raise

    except Exception:
        logger.exception(
            "Repository indexing failed: %s/%s",
            owner,
            repo,
        )

        raise HTTPException(
            status_code=500,
            detail="Repository indexing failed.",
        )