import json

from fastmcp import Client
from langchain_core.documents import Document

from src.config.logging_config import get_logger
from src.ingestion.file_splitter import is_useful_file


logger = get_logger(__name__)


async def _get_contents(
    client,
    owner: str,
    repo: str,
    path: str = "/",
    ref: str | None = None,
) -> list | dict:
    arguments = {
        "owner": owner,
        "repo": repo,
        "path": path,
    }

    if ref:
        arguments["ref"] = ref

    result = await client.call_tool(
        "get_file_contents",
        arguments,
    )

    if not result.content:
        return []

    for content in result.content:
        if hasattr(content, "text"):
            text = content.text

            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text

    return []


async def _collect_files(
    client,
    owner: str,
    repo: str,
    path: str = "/",
    ref: str | None = None,
) -> tuple[list[dict], str | None]:
    entries = await _get_contents(
        client=client,
        owner=owner,
        repo=repo,
        path=path,
        ref=ref,
    )

    if not isinstance(entries, list):
        return [], ref

    files = []
    current_ref = ref

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        entry_type = entry.get("type")
        entry_path = entry.get("path")
        entry_sha = entry.get("sha")

        if not entry_path:
            continue

        if current_ref is None and entry_sha:
            current_ref = entry.get("commit_sha") or current_ref

        if entry_type == "file":
            files.append(
                {
                    "path": entry_path,
                    "sha": entry_sha,
                }
            )

        elif entry_type == "dir":
            nested_files, nested_ref = await _collect_files(
                client=client,
                owner=owner,
                repo=repo,
                path=entry_path,
                ref=current_ref,
            )

            files.extend(nested_files)

            if current_ref is None:
                current_ref = nested_ref

    return files, current_ref


async def _get_repository_ref(
    client,
    owner: str,
    repo: str,
) -> str | None:
    entries = await _get_contents(
        client=client,
        owner=owner,
        repo=repo,
        path="/",
    )

    if not isinstance(entries, list):
        return None

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        url = entry.get("url", "")

        if "ref=" in url:
            ref = url.split("ref=", 1)[1]

            if ref:
                return ref

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        html_url = entry.get("html_url", "")

        if "/blob/" in html_url:
            parts = html_url.split("/blob/", 1)

            if len(parts) == 2:
                ref = parts[1].split("/", 1)[0]

                if ref:
                    return ref

    return None


async def _read_file(
    client,
    owner: str,
    repo: str,
    path: str,
    ref: str,
) -> dict | None:
    result = await client.call_tool(
        "get_file_contents",
        {
            "owner": owner,
            "repo": repo,
            "path": path,
            "ref": ref,
        },
    )

    for content in result.content:
        if hasattr(content, "resource"):
            resource = content.resource

            if hasattr(resource, "text"):
                return {
                    "path": path,
                    "content": resource.text,
                }

        if hasattr(content, "text"):
            text = content.text

            if text.startswith("successfully downloaded"):
                continue

    return None


async def load_repository(
    owner: str,
    repo: str,
    github_token: str,
) -> tuple[list[Document], str]:
    if not github_token:
        raise ValueError(
            "GitHub authentication token is required."
        )

    mcp_url = "https://api.githubcopilot.com/mcp/"

    logger.info(
        "Repository loading started: repository=%s/%s",
        owner,
        repo,
    )

    documents = []

    try:
        async with Client(
            mcp_url,
            auth=github_token,
        ) as client:

            await client.list_tools()

            logger.info(
                "Connected to GitHub official MCP server for repository loading"
            )

            ref = await _get_repository_ref(
                client=client,
                owner=owner,
                repo=repo,
            )

            if not ref:
                logger.warning(
                    "Could not determine repository ref: repository=%s/%s",
                    owner,
                    repo,
                )

                ref = "refs/heads/main"

            logger.info(
                "Repository ref selected: repository=%s/%s | ref=%s",
                owner,
                repo,
                ref,
            )

            files, discovered_ref = await _collect_files(
                client=client,
                owner=owner,
                repo=repo,
                path="/",
                ref=ref,
            )

            if discovered_ref:
                ref = discovered_ref

            logger.info(
                "Repository files discovered: repository=%s/%s | files=%s",
                owner,
                repo,
                len(files),
            )

            for file in files:
                path = file.get("path")

                if not path:
                    continue

                if not is_useful_file(path):
                    logger.debug(
                        "Skipping unsupported repository file: %s",
                        path,
                    )
                    continue

                try:
                    data = await _read_file(
                        client=client,
                        owner=owner,
                        repo=repo,
                        path=path,
                        ref=ref,
                    )

                    if not data:
                        logger.warning(
                            "No content returned for repository file: %s",
                            path,
                        )
                        continue

                    content = data.get(
                        "content",
                        "",
                    )

                    if not content or not content.strip():
                        logger.debug(
                            "Skipping empty repository file: %s",
                            path,
                        )
                        continue

                    documents.append(
                        Document(
                            page_content=content,
                            metadata={
                                "path": path,
                                "repository": f"{owner}/{repo}",
                                "sha": file.get("sha"),
                            },
                        )
                    )

                    logger.debug(
                        "Repository file loaded: %s",
                        path,
                    )

                except Exception:
                    logger.exception(
                        "Failed to load repository file: %s",
                        path,
                    )

                    continue

        logger.info(
            "Repository loading completed: repository=%s/%s | documents=%s",
            owner,
            repo,
            len(documents),
        )

        return documents, ref

    except Exception:
        logger.exception(
            "Repository loading failed: repository=%s/%s",
            owner,
            repo,
        )
        raise