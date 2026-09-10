from datetime import datetime, timedelta, timezone
import json

from fastmcp import Client
from langchain.agents import create_agent
from langchain.agents.middleware import (
    ClearToolUsesEdit,
    ContextEditingMiddleware,
)
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.config.logging_config import get_logger
from src.config.settings import settings
from src.rag.retriever import retrieve


logger = get_logger(__name__)


MAX_SEARCH_CHARS = 4000
MAX_FILE_CHARS = 6000
MAX_FILE_LIST_CHARS = 5000
RECENT_COMMIT_DAYS = 30


class RepoLensAgent:

    def __init__(self):

        logger.info(
            "Initializing RepoLens agent"
        )

        self.llm = ChatGroq(
            model="openai/gpt-oss-120b",
            temperature=0,
            api_key=settings.groq_api_key,
            max_tokens=2048,
        )

        logger.info(
            "LLM initialized: model=openai/gpt-oss-120b"
        )

    @staticmethod
    def _extract_json(result):

        if not result.content:
            return None

        for content in result.content:

            text = getattr(
                content,
                "text",
                None,
            )

            if not text:
                continue

            try:
                return json.loads(text)
            except json.JSONDecodeError:
                continue

        return None

    @staticmethod
    def _extract_resource_text(result):

        if not result.content:
            return ""

        for content in result.content:

            resource = getattr(
                content,
                "resource",
                None,
            )

            if resource is None:
                continue

            text = getattr(
                resource,
                "text",
                None,
            )

            if text is not None:
                return text

        return ""

    @staticmethod
    def _extract_text(result):

        if not result.content:
            return ""

        parts = []

        for content in result.content:

            text = getattr(
                content,
                "text",
                None,
            )

            if text:
                parts.append(text)

        return "\n".join(parts)

    async def _is_repository_question(
        self,
        question: str,
    ) -> bool:

        logger.info(
            "Checking question intent: question_length=%s",
            len(question),
        )

        try:

            response = await self.llm.ainvoke(
                [
                    SystemMessage(
                        content="""
Determine whether the user's message requires information
from a GitHub repository.

Return exactly one word:

YES

if the message requires repository information, repository
code, repository files, implementation details, repository
architecture, repository behavior, or information that
should be obtained from repository tools or indexed code.

Return:

NO

if the message can be answered without accessing the
repository, including normal conversation, casual discussion,
general questions, or unrelated questions.

If the message is an ambiguous follow-up to a repository
discussion and repository context may be required, return YES.

Return only YES or NO.
"""
                    ),
                    HumanMessage(
                        content=question
                    ),
                ]
            )

            result = response.content

            if isinstance(result, list):

                parts = []

                for block in result:

                    if isinstance(block, dict):

                        text = block.get("text")

                        if text:
                            parts.append(text)

                result = "".join(parts)

            result = str(result).strip().upper()

            is_repository_question = result.startswith(
                "YES"
            )

            logger.info(
                "Question intent detected: repository_question=%s",
                is_repository_question,
            )

            return is_repository_question

        except Exception:

            logger.exception(
                "Question intent detection failed"
            )

            return True

    def _create_normal_agent(
        self,
        checkpointer,
    ):

        logger.info(
            "Creating normal conversation agent"
        )

        agent = create_agent(
            model=self.llm,
            tools=[],
            checkpointer=checkpointer,
            system_prompt="""
You are a helpful AI assistant.

Answer the user's message naturally and concisely.

Do not use repository tools.

Do not assume information about a GitHub repository
unless the user explicitly asks about one.
""",
        )

        logger.info(
            "Normal conversation agent created successfully"
        )

        return agent

    async def _stream_normal_response(
        self,
        question: str,
        thread_id: str,
        checkpointer,
    ):

        logger.info(
            "Normal response started: question_length=%s | thread_id=%s",
            len(question),
            thread_id,
        )

        agent = self._create_normal_agent(
            checkpointer
        )

        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }

        chunk_count = 0

        try:

            async for (
                message_chunk,
                metadata,
            ) in agent.astream(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": question,
                        }
                    ]
                },
                config=config,
                stream_mode="messages",
            ):

                if (
                    message_chunk.type
                    != "AIMessageChunk"
                ):
                    continue

                if isinstance(
                    message_chunk.content,
                    str,
                ):

                    if message_chunk.content:

                        chunk_count += 1

                        yield message_chunk.content

                elif isinstance(
                    message_chunk.content,
                    list,
                ):

                    for block in (
                        message_chunk.content
                    ):

                        if isinstance(
                            block,
                            dict,
                        ):

                            text = block.get(
                                "text"
                            )

                            if text:

                                chunk_count += 1

                                yield text

            logger.info(
                "Normal response completed: thread_id=%s | chunks=%s",
                thread_id,
                chunk_count,
            )

        except Exception:

            logger.exception(
                "Normal response failed: thread_id=%s",
                thread_id,
            )

            raise

    async def _create_agent(
        self,
        owner: str,
        repo: str,
        checkpointer,
        github_token: str,
    ):

        if not github_token:
            raise ValueError(
                "GitHub authentication token is required."
            )

        namespace = f"{owner}-{repo}"

        logger.info(
            "Creating agent: repository=%s/%s",
            owner,
            repo,
        )

        client = Client(
            "https://api.githubcopilot.com/mcp/",
            auth=github_token,
        )

        await client.__aenter__()

        logger.info(
            "Connected to GitHub official MCP server"
        )

        await client.list_tools()

        logger.info(
            "GitHub official MCP tools discovered successfully"
        )

        @tool
        async def list_repository_files() -> str:
            """List the files and folders in the repository."""

            logger.info(
                "MCP tool called: list_repository_files | repository=%s/%s",
                owner,
                repo,
            )

            try:

                result = await client.call_tool(
                    "get_file_contents",
                    {
                        "owner": owner,
                        "repo": repo,
                    },
                )

                data = self._extract_json(result)

                if data is None:

                    logger.warning(
                        "Could not parse repository listing: repository=%s/%s",
                        owner,
                        repo,
                    )

                    return (
                        "Unable to retrieve the repository "
                        "file structure."
                    )

                if isinstance(data, dict):
                    data = [data]

                files = []

                for entry in data:

                    if not isinstance(
                        entry,
                        dict,
                    ):
                        continue

                    path = entry.get(
                        "path"
                    )

                    if path:
                        files.append(
                            path
                        )

                logger.info(
                    "Repository files listed: repository=%s/%s | files=%s",
                    owner,
                    repo,
                    len(files),
                )

                text = "\n".join(files)

                if len(text) > MAX_FILE_LIST_CHARS:

                    text = (
                        text[:MAX_FILE_LIST_CHARS]
                        + "\n\n[File list truncated.]"
                    )

                return (
                    f"Repository: {owner}/{repo}\n"
                    f"Total entries: {len(files)}\n\n"
                    f"{text}"
                )

            except Exception:

                logger.exception(
                    "MCP tool failed: list_repository_files | repository=%s/%s",
                    owner,
                    repo,
                )

                raise

        @tool
        async def read_repository_file(
            path: str,
        ) -> str:
            """Read a specific file from the repository."""

            logger.info(
                "MCP tool called: read_repository_file | repository=%s/%s | path=%s",
                owner,
                repo,
                path,
            )

            try:

                result = await client.call_tool(
                    "get_file_contents",
                    {
                        "owner": owner,
                        "repo": repo,
                        "path": path,
                    },
                )

                content = self._extract_resource_text(
                    result
                )

                if not content:

                    logger.warning(
                        "No file content returned: repository=%s/%s | path=%s",
                        owner,
                        repo,
                        path,
                    )

                    return (
                        f"No content was returned for "
                        f"file: {path}"
                    )

                logger.info(
                    "Repository file read: repository=%s/%s | path=%s | chars=%s",
                    owner,
                    repo,
                    path,
                    len(content),
                )

                if len(content) > MAX_FILE_CHARS:

                    content = (
                        content[:MAX_FILE_CHARS]
                        + "\n\n[File content truncated.]"
                    )

                return (
                    f"File: {path}\n\n"
                    f"{content}"
                )

            except Exception:

                logger.exception(
                    "MCP tool failed: read_repository_file | repository=%s/%s | path=%s",
                    owner,
                    repo,
                    path,
                )

                raise

        @tool
        async def search_repository(
            query: str,
        ) -> str:
            """Search the indexed repository for relevant code and documentation."""

            logger.info(
                "RAG search started: repository=%s/%s | query_length=%s",
                owner,
                repo,
                len(query),
            )

            try:

                documents = retrieve(
                    query,
                    namespace=namespace,
                    k=4,
                )

                logger.info(
                    "RAG search completed: repository=%s/%s | results=%s",
                    owner,
                    repo,
                    len(documents),
                )

                if not documents:

                    logger.warning(
                        "No RAG results found: repository=%s/%s",
                        owner,
                        repo,
                    )

                    return (
                        "No relevant repository context "
                        "was found."
                    )

                parts = []
                total_chars = 0

                for document in documents:

                    path = document.metadata.get(
                        "path",
                        "unknown",
                    )

                    content = document.page_content

                    remaining = (
                        MAX_SEARCH_CHARS
                        - total_chars
                    )

                    if remaining <= 0:
                        break

                    content = content[:remaining]

                    parts.append(
                        f"File: {path}\n"
                        f"{content}"
                    )

                    total_chars += len(content)

                result = "\n\n".join(parts)

                if total_chars >= MAX_SEARCH_CHARS:

                    result += (
                        "\n\n[Search results truncated.]"
                    )

                logger.info(
                    "RAG context prepared: repository=%s/%s | results=%s | chars=%s",
                    owner,
                    repo,
                    len(documents),
                    total_chars,
                )

                return result

            except Exception:

                logger.exception(
                    "RAG search failed: repository=%s/%s",
                    owner,
                    repo,
                )

                raise

        @tool
        async def get_repository_commits(
            limit: int = 10,
        ) -> str:
            """Get the latest commits from the repository regardless of their age."""

            logger.info(
                "MCP tool called: get_repository_commits | repository=%s/%s | limit=%s",
                owner,
                repo,
                limit,
            )

            try:

                result = await client.call_tool(
                    "list_commits",
                    {
                        "owner": owner,
                        "repo": repo,
                        "per_page": min(
                            limit,
                            100,
                        ),
                    },
                )

                data = self._extract_json(
                    result
                )

                if data is None:

                    text = self._extract_text(
                        result
                    )

                    if text:
                        return text

                    return "No commits were found."

                if isinstance(
                    data,
                    dict,
                ):

                    commits = (
                        data.get("commits")
                        or data.get("items")
                        or []
                    )

                elif isinstance(
                    data,
                    list,
                ):

                    commits = data

                else:

                    commits = []

                if not commits:
                    return "No commits were found."

                lines = []

                for commit in commits[:limit]:

                    if not isinstance(
                        commit,
                        dict,
                    ):
                        continue

                    commit_data = commit.get(
                        "commit",
                        {},
                    )

                    if not isinstance(
                        commit_data,
                        dict,
                    ):
                        commit_data = {}

                    message = (
                        commit.get("message")
                        or commit_data.get(
                            "message",
                            "",
                        )
                    )

                    author_data = commit_data.get(
                        "author",
                        {},
                    )

                    if not isinstance(
                        author_data,
                        dict,
                    ):
                        author_data = {}

                    author = (
                        commit.get("author")
                        or author_data
                    )

                    if isinstance(
                        author,
                        dict,
                    ):

                        author_name = (
                            author.get("name")
                            or author.get("login")
                            or ""
                        )

                        date = (
                            author.get("date")
                            or ""
                        )

                    else:

                        author_name = str(
                            author
                        )

                        date = ""

                    sha = (
                        commit.get("sha")
                        or commit.get("oid")
                        or ""
                    )

                    url = (
                        commit.get("html_url")
                        or commit.get("url")
                        or ""
                    )

                    lines.append(
                        f"Commit: {sha[:7]}\n"
                        f"Author: {author_name}\n"
                        f"Date: {date}\n"
                        f"Message: {message}\n"
                        f"URL: {url}"
                    )

                if not lines:
                    return "No commits were found."

                logger.info(
                    "Repository commits fetched: repository=%s/%s | commits=%s",
                    owner,
                    repo,
                    len(lines),
                )

                return "\n\n".join(lines)

            except Exception:

                logger.exception(
                    "MCP tool failed: get_repository_commits | repository=%s/%s",
                    owner,
                    repo,
                )

                raise

        @tool
        async def get_recent_repository_commits() -> str:
            """Check whether the repository has commits within the last 30 days."""

            logger.info(
                "MCP tool called: get_recent_repository_commits | repository=%s/%s | recent_days=%s",
                owner,
                repo,
                RECENT_COMMIT_DAYS,
            )

            try:

                result = await client.call_tool(
                    "list_commits",
                    {
                        "owner": owner,
                        "repo": repo,
                        "per_page": 10,
                    },
                )

                data = self._extract_json(
                    result
                )

                if isinstance(
                    data,
                    dict,
                ):

                    commits = (
                        data.get("commits")
                        or data.get("items")
                        or []
                    )

                elif isinstance(
                    data,
                    list,
                ):

                    commits = data

                else:

                    commits = []

                now = datetime.now(
                    timezone.utc
                )

                cutoff = (
                    now
                    - timedelta(
                        days=RECENT_COMMIT_DAYS
                    )
                )

                recent_commits = []

                for commit in commits:

                    if not isinstance(
                        commit,
                        dict,
                    ):
                        continue

                    commit_data = commit.get(
                        "commit",
                        {},
                    )

                    if not isinstance(
                        commit_data,
                        dict,
                    ):
                        commit_data = {}

                    author_data = commit_data.get(
                        "author",
                        {},
                    )

                    if not isinstance(
                        author_data,
                        dict,
                    ):
                        author_data = {}

                    commit_date = (
                        commit.get("date")
                        or author_data.get("date")
                    )

                    if not commit_date:
                        continue

                    try:

                        parsed_date = datetime.fromisoformat(
                            commit_date.replace(
                                "Z",
                                "+00:00",
                            )
                        )

                        if parsed_date.tzinfo is None:

                            parsed_date = parsed_date.replace(
                                tzinfo=timezone.utc
                            )

                    except ValueError:

                        continue

                    if parsed_date >= cutoff:
                        recent_commits.append(
                            commit
                        )

                logger.info(
                    "Recent commits checked: repository=%s/%s | recent_commits=%s | cutoff=%s",
                    owner,
                    repo,
                    len(recent_commits),
                    cutoff.isoformat(),
                )

                if recent_commits:

                    lines = []

                    for commit in recent_commits:

                        commit_data = commit.get(
                            "commit",
                            {},
                        )

                        if not isinstance(
                            commit_data,
                            dict,
                        ):
                            commit_data = {}

                        author_data = commit_data.get(
                            "author",
                            {},
                        )

                        if not isinstance(
                            author_data,
                            dict,
                        ):
                            author_data = {}

                        message = (
                            commit.get(
                                "message"
                            )
                            or commit_data.get(
                                "message",
                                "",
                            )
                        )

                        author = (
                            commit.get(
                                "author"
                            )
                            or author_data.get(
                                "name",
                                "",
                            )
                        )

                        date = (
                            commit.get(
                                "date"
                            )
                            or author_data.get(
                                "date",
                                "",
                            )
                        )

                        if isinstance(
                            author,
                            dict,
                        ):

                            author = (
                                author.get(
                                    "login"
                                )
                                or author.get(
                                    "name"
                                )
                                or ""
                            )

                        lines.append(
                            f"Message: {message}\n"
                            f"Author: {author}\n"
                            f"Date: {date}"
                        )

                    return (
                        f"Found {len(recent_commits)} "
                        f"commit(s) in the last "
                        f"{RECENT_COMMIT_DAYS} days.\n\n"
                        + "\n\n".join(lines)
                    )

                if commits:

                    latest_commit = commits[0]

                    commit_data = latest_commit.get(
                        "commit",
                        {},
                    )

                    if not isinstance(
                        commit_data,
                        dict,
                    ):
                        commit_data = {}

                    author_data = commit_data.get(
                        "author",
                        {},
                    )

                    if not isinstance(
                        author_data,
                        dict,
                    ):
                        author_data = {}

                    latest_date = (
                        latest_commit.get(
                            "date"
                        )
                        or author_data.get(
                            "date",
                            "unknown date",
                        )
                    )

                    latest_message = (
                        latest_commit.get(
                            "message"
                        )
                        or commit_data.get(
                            "message",
                            "unknown message",
                        )
                    )

                    return (
                        f"No commits were found in the last "
                        f"{RECENT_COMMIT_DAYS} days.\n\n"
                        f"The latest available commit was "
                        f"on {latest_date} "
                        f"with the message: "
                        f"{latest_message}"
                    )

                return (
                    f"No commits were found in the last "
                    f"{RECENT_COMMIT_DAYS} days."
                )

            except Exception:

                logger.exception(
                    "MCP tool failed: get_recent_repository_commits | repository=%s/%s",
                    owner,
                    repo,
                )

                raise

        agent = create_agent(
            model=self.llm,
            tools=[
                list_repository_files,
                read_repository_file,
                search_repository,
                get_repository_commits,
                get_recent_repository_commits,
            ],
            middleware=[
                ContextEditingMiddleware(
                    edits=[
                        ClearToolUsesEdit(
                            trigger=5000,
                            keep=2,
                        )
                    ]
                )
            ],
            checkpointer=checkpointer,
            system_prompt=f"""
You are RepoLens AI, a GitHub repository investigator.

You are investigating {owner}/{repo}.

Only use repository tools when the user's message requires
information about the repository.

Use list_repository_files when the user asks about:
- files
- folders
- repository structure
- listing repository files

Use read_repository_file when the user asks about:
- a specific file
- file contents
- implementation details requiring direct inspection

Use search_repository when the user asks:
- how something works
- why something is implemented
- conceptual questions about the repository
- questions requiring semantic search
- where a particular feature is implemented

Use get_repository_commits when the user asks:
- latest commits
- last N commits
- commit history
- commit messages
- who made a commit
- when a commit was made

Use get_recent_repository_commits when the user asks:
- are there recent commits?
- any recent activity?
- has this repository been active recently?
- were there any commits recently?
- recent changes

IMPORTANT:

"Recent" means commits from the last {RECENT_COMMIT_DAYS} days.

Do not call a commit "recent" if it is older than
{RECENT_COMMIT_DAYS} days.

The get_recent_repository_commits tool calculates the
actual date cutoff using the current UTC date. Trust its
result when determining whether the repository has recent
activity.

"Latest" and "recent" are NOT the same thing.

If the user asks for "latest commits" or "last 5 commits",
return the newest commits regardless of their age.

If the user asks whether there are "recent commits",
use get_recent_repository_commits.

IMPORTANT RESPONSE STYLE:

Do not expose raw tool output directly to the user.

Use the information returned by repository tools to create
a clear, natural, human-friendly answer.

For commit-related questions:

- Keep answers concise.
- Do not show commit SHA values or GitHub URLs unless the
  user asks for them.
- Do not create large tables unless the user specifically
  asks for detailed commit information.
- For "are there recent commits?", clearly state whether
  there are commits within the last {RECENT_COMMIT_DAYS} days.
- If there are no recent commits, mention the date of the
  latest available commit when useful.
- Never describe an old commit as recent.

For other repository questions, explain the result in simple
language and mention relevant file paths when useful.

Do not invent repository information.

If the available repository information is insufficient,
clearly say so.

Keep answers focused and concise.
""",
        )

        logger.info(
            "RepoLens agent created successfully: repository=%s/%s",
            owner,
            repo,
        )

        return agent, client

    async def stream(
        self,
        question: str,
        owner: str,
        repo: str,
        thread_id: str,
        github_token: str,
    ):

        if not github_token:
            raise ValueError(
                "GitHub authentication token is required."
            )

        logger.info(
            "Agent stream started: repository=%s/%s | thread_id=%s | question_length=%s",
            owner,
            repo,
            thread_id,
            len(question),
        )

        is_repository_question = (
            await self._is_repository_question(
                question
            )
        )

        checkpointer = AsyncPostgresSaver.from_conn_string(
            settings.database_url
        )

        async with checkpointer as checkpointer:

            await checkpointer.setup()

            if not is_repository_question:

                async for chunk in self._stream_normal_response(
                    question=question,
                    thread_id=thread_id,
                    checkpointer=checkpointer,
                ):

                    yield chunk

                return

            agent, client = await self._create_agent(
                owner=owner,
                repo=repo,
                checkpointer=checkpointer,
                github_token=github_token,
            )

            config = {
                "configurable": {
                    "thread_id": thread_id
                }
            }

            chunk_count = 0

            try:

                async for (
                    message_chunk,
                    metadata,
                ) in agent.astream(
                    {
                        "messages": [
                            {
                                "role": "user",
                                "content": question,
                            }
                        ]
                    },
                    config=config,
                    stream_mode="messages",
                ):

                    if (
                        message_chunk.type
                        != "AIMessageChunk"
                    ):
                        continue

                    if isinstance(
                        message_chunk.content,
                        str,
                    ):

                        if message_chunk.content:

                            chunk_count += 1

                            yield message_chunk.content

                    elif isinstance(
                        message_chunk.content,
                        list,
                    ):

                        for block in (
                            message_chunk.content
                        ):

                            if isinstance(
                                block,
                                dict,
                            ):

                                text = block.get(
                                    "text"
                                )

                                if text:

                                    chunk_count += 1

                                    yield text

                logger.info(
                    "Agent stream completed: repository=%s/%s | thread_id=%s | chunks=%s",
                    owner,
                    repo,
                    thread_id,
                    chunk_count,
                )

            except Exception:

                logger.exception(
                    "Agent stream failed: repository=%s/%s | thread_id=%s",
                    owner,
                    repo,
                    thread_id,
                )

                raise

            finally:

                await client.__aexit__(
                    None,
                    None,
                    None,
                )

                logger.info(
                    "MCP connection closed: repository=%s/%s | thread_id=%s",
                    owner,
                    repo,
                    thread_id,
                )

    async def get_history(
        self,
        owner: str,
        repo: str,
        thread_id: str,
        github_token: str,
    ):

        if not github_token:
            raise ValueError(
                "GitHub authentication token is required."
            )

        logger.info(
            "Fetching conversation history: repository=%s/%s | thread_id=%s",
            owner,
            repo,
            thread_id,
        )

        checkpointer = AsyncPostgresSaver.from_conn_string(
            settings.database_url
        )

        async with checkpointer as checkpointer:

            await checkpointer.setup()

            agent, client = await self._create_agent(
                owner=owner,
                repo=repo,
                checkpointer=checkpointer,
                github_token=github_token,
            )

            config = {
                "configurable": {
                    "thread_id": thread_id
                }
            }

            try:

                state = await agent.aget_state(
                    config
                )

                if not state:

                    logger.info(
                        "No conversation state found: thread_id=%s",
                        thread_id,
                    )

                    return []

                messages = state.values.get(
                    "messages",
                    [],
                )

                history = []

                for message in messages:

                    if message.type == "human":
                        role = "user"

                    elif message.type == "ai":
                        role = "assistant"

                    else:
                        continue

                    content = message.content

                    if isinstance(
                        content,
                        str,
                    ):

                        text = content

                    elif isinstance(
                        content,
                        list,
                    ):

                        parts = []

                        for block in content:

                            if isinstance(
                                block,
                                dict,
                            ):

                                block_text = block.get(
                                    "text"
                                )

                                if block_text:
                                    parts.append(
                                        block_text
                                    )

                        text = "".join(parts)

                    else:

                        text = str(content)

                    if text:

                        history.append(
                            {
                                "role": role,
                                "content": text,
                            }
                        )

                logger.info(
                    "Conversation history fetched: thread_id=%s | messages=%s",
                    thread_id,
                    len(history),
                )

                return history

            except Exception:

                logger.exception(
                    "Failed to fetch conversation history: thread_id=%s",
                    thread_id,
                )

                raise

            finally:

                await client.__aexit__(
                    None,
                    None,
                    None,
                )

    async def delete_thread(
        self,
        thread_id: str,
    ):

        logger.info(
            "Deleting LangGraph thread: thread_id=%s",
            thread_id,
        )

        checkpointer = AsyncPostgresSaver.from_conn_string(
            settings.database_url
        )

        async with checkpointer as checkpointer:

            await checkpointer.setup()

            try:

                await checkpointer.adelete_thread(
                    thread_id
                )

                logger.info(
                    "LangGraph thread deleted: thread_id=%s",
                    thread_id,
                )

            except Exception:

                logger.exception(
                    "Failed to delete LangGraph thread: thread_id=%s",
                    thread_id,
                )

                raise

    async def ask(
        self,
        question: str,
        owner: str,
        repo: str,
        thread_id: str,
        github_token: str,
    ):

        if not github_token:
            raise ValueError(
                "GitHub authentication token is required."
            )

        logger.info(
            "Agent ask started: repository=%s/%s | thread_id=%s",
            owner,
            repo,
            thread_id,
        )

        chunks = []

        try:

            async for chunk in self.stream(
                question=question,
                owner=owner,
                repo=repo,
                thread_id=thread_id,
                github_token=github_token,
            ):

                chunks.append(
                    chunk
                )

            answer = "".join(
                chunks
            )

            logger.info(
                "Agent ask completed: repository=%s/%s | thread_id=%s | answer_chars=%s",
                owner,
                repo,
                thread_id,
                len(answer),
            )

            return answer

        except Exception:

            logger.exception(
                "Agent ask failed: repository=%s/%s | thread_id=%s",
                owner,
                repo,
                thread_id,
            )

            raise