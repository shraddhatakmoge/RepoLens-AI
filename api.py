import asyncio
import base64
import hashlib
import secrets
import sys
import uuid
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from src.agent.agent import RepoLensAgent
from src.config.logging_config import (
    get_logger,
    setup_logging,
)
from src.config.settings import settings
from src.database.chat_sessions import (
    create_auth_session,
    create_chat_session,
    delete_auth_session,
    delete_chat_session,
    exchange_auth_session,
    get_auth_session,
    get_chat_session,
    get_chat_sessions,
    get_indexed_repository,
    init_database,
    rename_chat_session,
    save_indexed_repository,
)
from src.ingestion.loader import load_repository
from src.ingestion.splitter import split_documents
from src.vectorstore.pinecone_store import add_documents


if sys.platform == "win32":
    asyncio.set_event_loop_policy(
        asyncio.WindowsSelectorEventLoopPolicy()
    )


setup_logging()

logger = get_logger(__name__)


app = FastAPI(
    title="RepoLens AI API",
    version="1.0.0",
)


init_database()

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


class AuthExchangeRequest(BaseModel):
    auth_code: str = Field(min_length=1)


def create_pkce_pair():

    code_verifier = (
        base64.urlsafe_b64encode(
            secrets.token_bytes(32)
        )
        .rstrip(b"=")
        .decode("utf-8")
    )

    code_challenge = (
        base64.urlsafe_b64encode(
            hashlib.sha256(
                code_verifier.encode("utf-8")
            ).digest()
        )
        .rstrip(b"=")
        .decode("utf-8")
    )

    return code_verifier, code_challenge


async def exchange_github_code(
    code: str,
    code_verifier: str,
):

    payload = {
        "client_id": settings.github_client_id,
        "client_secret": settings.github_client_secret,
        "code": code,
        "redirect_uri": settings.github_oauth_redirect_uri,
        "code_verifier": code_verifier,
    }

    headers = {
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(
        timeout=30
    ) as client:

        response = await client.post(
            "https://github.com/login/oauth/access_token",
            data=payload,
            headers=headers,
        )

        response.raise_for_status()

        data = response.json()

    if "error" in data:

        logger.error(
            "GitHub OAuth token exchange failed: %s",
            data.get("error"),
        )

        raise HTTPException(
            status_code=400,
            detail="GitHub authorization failed.",
        )

    access_token = data.get(
        "access_token"
    )

    if not access_token:

        raise HTTPException(
            status_code=400,
            detail="GitHub did not return an access token.",
        )

    return data


async def get_github_user(
    access_token: str,
):

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {access_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    async with httpx.AsyncClient(
        timeout=30
    ) as client:

        response = await client.get(
            "https://api.github.com/user",
            headers=headers,
        )

        response.raise_for_status()

        return response.json()


@app.get("/auth/github/login")
async def github_login():

    state = secrets.token_urlsafe(32)

    code_verifier, code_challenge = (
        create_pkce_pair()
    )

    params = {
        "client_id": settings.github_client_id,
        "redirect_uri": settings.github_oauth_redirect_uri,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    oauth_url = (
        "https://github.com/login/oauth/authorize?"
        + urlencode(params)
    )

    app.state.github_oauth_states[state] = {
        "code_verifier": code_verifier,
    }

    logger.info(
        "GitHub OAuth login started"
    )

    return RedirectResponse(
        url=oauth_url,
        status_code=302,
    )


@app.get("/auth/github/callback")
async def github_callback(
    code: str | None = None,
    state: str | None = None,
):

    if not code or not state:

        raise HTTPException(
            status_code=400,
            detail="Missing GitHub OAuth parameters.",
        )

    oauth_data = (
        app.state.github_oauth_states.pop(
            state,
            None,
        )
    )

    if not oauth_data:

        raise HTTPException(
            status_code=400,
            detail="Invalid or expired OAuth state.",
        )

    token_data = await exchange_github_code(
        code=code,
        code_verifier=oauth_data["code_verifier"],
    )

    access_token = token_data[
        "access_token"
    ]

    refresh_token = token_data.get(
        "refresh_token"
    )

    user = await get_github_user(
        access_token
    )

    github_login = user.get(
        "login"
    )

    if not github_login:

        raise HTTPException(
            status_code=400,
            detail="Unable to determine GitHub account.",
        )

    expires_in = token_data.get(
        "expires_in"
    )

    refresh_token_expires_in = (
        token_data.get(
            "refresh_token_expires_in"
        )
    )

    token_expires_at = None

    if expires_in:

        from datetime import (
            datetime,
            timedelta,
            timezone,
        )

        token_expires_at = (
            datetime.now(timezone.utc)
            + timedelta(
                seconds=int(
                    expires_in
                )
            )
        ).isoformat()

    refresh_token_expires_at = None

    if refresh_token_expires_in:

        from datetime import (
            datetime,
            timedelta,
            timezone,
        )

        refresh_token_expires_at = (
            datetime.now(timezone.utc)
            + timedelta(
                seconds=int(
                    refresh_token_expires_in
                )
            )
        ).isoformat()

    auth_code = str(
        uuid.uuid4()
    )

    create_auth_session(
        github_login=github_login,
        github_token=access_token,
        github_refresh_token=refresh_token,
        token_expires_at=token_expires_at,
        refresh_token_expires_at=refresh_token_expires_at,
        session_id=auth_code,
    )

    frontend_url = (
        settings.frontend_url.rstrip("/")
    )

    redirect_url = (
        f"{frontend_url}/"
        f"?auth_code={auth_code}"
    )

    logger.info(
        "GitHub OAuth completed: login=%s",
        github_login,
    )

    return RedirectResponse(
        url=redirect_url,
        status_code=302,
    )


@app.post("/auth/exchange")
async def auth_exchange(
    request: AuthExchangeRequest,
):

    new_session_id = secrets.token_urlsafe(
        32
    )

    session = exchange_auth_session(
        auth_code=request.auth_code,
        new_session_id=new_session_id,
    )

    if not session:

        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication code.",
        )

    persistent_session_id = session[
        "session_id"
    ]

    logger.info(
        "GitHub auth session exchanged: login=%s",
        session["github_login"],
    )

    return {
        "session_id": persistent_session_id,
        "github_login": session[
            "github_login"
        ],
    }


@app.post("/auth/logout")
async def auth_logout(
    request: Request,
):

    session_id = request.headers.get(
        "X-RepoLens-Session"
    )

    if session_id:

        delete_auth_session(
            session_id
        )

        logger.info(
            "GitHub auth session deleted"
        )

    return {
        "message": "Logged out successfully."
    }


def get_current_auth_session(
    request: Request,
):

    session_id = request.headers.get(
        "X-RepoLens-Session"
    )

    if not session_id:

        raise HTTPException(
            status_code=401,
            detail="GitHub authentication required.",
        )

    session = get_auth_session(
        session_id
    )

    if not session:

        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session.",
        )

    return session


async def prepare_repository(
    owner: str,
    repo: str,
    github_token: str,
):

    logger.info(
        "Repository indexing started: %s/%s",
        owner,
        repo,
    )

    try:

        documents, commit_sha = (
            await load_repository(
                owner=owner,
                repo=repo,
                github_token=github_token,
            )
        )

        indexed = get_indexed_repository(
            owner=owner,
            repo=repo,
        )

        if (
            indexed
            and indexed["commit_sha"]
            == commit_sha
        ):

            logger.info(
                "Repository already indexed: %s/%s | commit=%s",
                owner,
                repo,
                commit_sha,
            )

            return 0, 0, True

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

        chunks = split_documents(
            documents
        )

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

        save_indexed_repository(
            owner=owner,
            repo=repo,
            commit_sha=commit_sha,
        )

        logger.info(
            "Repository indexed successfully: %s/%s | files=%s | chunks=%s | commit=%s",
            owner,
            repo,
            len(documents),
            len(chunks),
            commit_sha,
        )

        return (
            len(documents),
            len(chunks),
            False,
        )

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

    logger.info(
        "Health check requested"
    )

    return {
        "status": "ok",
        "service": "RepoLens AI API",
    }


@app.get("/auth/me")
async def auth_me(
    request: Request,
):

    session = get_current_auth_session(
        request
    )

    return {
        "authenticated": True,
        "github_login": session[
            "github_login"
        ],
    }


@app.get("/chats")
async def get_chats(
    request: Request,
):

    session = get_current_auth_session(
        request
    )

    github_login = session[
        "github_login"
    ]

    logger.info(
        "Fetching chat sessions: login=%s",
        github_login,
    )

    try:

        chats = get_chat_sessions(
            github_login=github_login
        )

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
    http_request: Request,
):

    session = get_current_auth_session(
        http_request
    )

    github_login = session[
        "github_login"
    ]

    owner = request.owner.strip()
    repo = request.repo.strip()

    if not owner or not repo:

        raise HTTPException(
            status_code=400,
            detail="Owner and repository are required.",
        )

    thread_id = str(
        uuid.uuid4()
    )

    logger.info(
        "Creating chat: thread_id=%s | repository=%s/%s | login=%s",
        thread_id,
        owner,
        repo,
        github_login,
    )

    try:

        create_chat_session(
            thread_id=thread_id,
            owner=owner,
            repo=repo,
            github_login=github_login,
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
    request: Request,
):

    session = get_current_auth_session(
        request
    )

    github_login = session[
        "github_login"
    ]

    logger.info(
        "Fetching chat: thread_id=%s",
        thread_id,
    )

    try:

        chat = get_chat_session(
            thread_id=thread_id,
            github_login=github_login,
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
            github_token=session[
                "github_token"
            ],
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
    http_request: Request,
):

    session = get_current_auth_session(
        http_request
    )

    github_login = session[
        "github_login"
    ]

    title = request.title.strip()

    if not title:

        raise HTTPException(
            status_code=400,
            detail="Chat title cannot be empty.",
        )

    try:

        chat = get_chat_session(
            thread_id=thread_id,
            github_login=github_login,
        )

        if chat is None:

            raise HTTPException(
                status_code=404,
                detail="Chat not found.",
            )

        updated = rename_chat_session(
            thread_id=thread_id,
            title=title,
            github_login=github_login,
        )

        return {
            "thread_id": thread_id,
            "title": updated["title"],
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
    request: Request,
):

    session = get_current_auth_session(
        request
    )

    github_login = session[
        "github_login"
    ]

    logger.info(
        "Chat deletion requested: thread_id=%s",
        thread_id,
    )

    try:

        chat = get_chat_session(
            thread_id=thread_id,
            github_login=github_login,
        )

        if chat is None:

            raise HTTPException(
                status_code=404,
                detail="Chat not found.",
            )

        agent = RepoLensAgent()

        await agent.delete_thread(
            thread_id
        )

        delete_chat_session(
            thread_id=thread_id,
            github_login=github_login,
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
    http_request: Request,
):

    session = get_current_auth_session(
        http_request
    )

    github_login = session[
        "github_login"
    ]

    question = request.question.strip()
    thread_id = request.thread_id.strip()

    if not question:

        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty.",
        )

    if not thread_id:

        raise HTTPException(
            status_code=400,
            detail="Thread ID is required.",
        )

    chat_session = get_chat_session(
        thread_id=thread_id,
        github_login=github_login,
    )

    if chat_session is None:

        raise HTTPException(
            status_code=404,
            detail="Chat not found.",
        )

    owner = chat_session["owner"]
    repo = chat_session["repo"]

    logger.info(
        "Chat request received: thread_id=%s | repository=%s/%s | login=%s",
        thread_id,
        owner,
        repo,
        github_login,
    )

    try:

        agent = RepoLensAgent()

        answer = await agent.ask(
            question=question,
            owner=owner,
            repo=repo,
            thread_id=thread_id,
            github_token=session[
                "github_token"
            ],
        )

        if not answer:

            raise HTTPException(
                status_code=502,
                detail="The AI agent returned an empty response.",
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
    http_request: Request,
):

    session = get_current_auth_session(
        http_request
    )

    owner = request.owner.strip()
    repo = request.repo.strip()

    if not owner or not repo:

        raise HTTPException(
            status_code=400,
            detail="Owner and repository are required.",
        )

    logger.info(
        "Repository indexing request received: %s/%s | login=%s",
        owner,
        repo,
        session["github_login"],
    )

    try:

        documents_count, chunks_count, already_indexed = (
            await prepare_repository(
                owner=owner,
                repo=repo,
                github_token=session[
                    "github_token"
                ],
            )
        )

        if already_indexed:

            return {
                "status": "already_indexed",
                "owner": owner,
                "repo": repo,
                "documents": 0,
                "chunks": 0,
                "message": "Repository is already indexed at the current commit.",
            }

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


@app.on_event("startup")
async def startup():

    app.state.github_oauth_states = {}

    logger.info(
        "GitHub OAuth state storage initialized"
    )