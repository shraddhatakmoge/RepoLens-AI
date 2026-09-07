from fastmcp import Client
from langchain_core.documents import Document

from src.config.logging_config import get_logger
from src.config.settings import settings
from src.ingestion.file_splitter import is_useful_file


logger = get_logger(__name__)


async def load_repository(
    owner: str,
    repo: str,
    mcp_url: str | None = None,
) -> list[Document]:

    if mcp_url is None:
        mcp_url = settings.mcp_server_url

    logger.info(
        "Repository loading started: repository=%s/%s",
        owner,
        repo,
    )

    logger.info(
        "Connecting to MCP server: %s",
        mcp_url,
    )

    try:
        async with Client(mcp_url) as client:

            logger.info(
                "Requesting repository file list: repository=%s/%s",
                owner,
                repo,
            )

            file_result = await client.call_tool(
                "list_files",
                {
                    "owner": owner,
                    "repo": repo,
                },
            )

            files = file_result.data["files"]

            logger.info(
                "Repository file list received: repository=%s/%s | files=%s",
                owner,
                repo,
                len(files),
            )

            documents = []
            skipped_files = 0

            for file in files:

                path = file["path"]

                if not is_useful_file(
                    path,
                    file.get("size"),
                ):
                    skipped_files += 1

                    logger.debug(
                        "Skipping file: repository=%s/%s | path=%s",
                        owner,
                        repo,
                        path,
                    )

                    continue

                logger.debug(
                    "Reading repository file: repository=%s/%s | path=%s",
                    owner,
                    repo,
                    path,
                )

                result = await client.call_tool(
                    "read_file",
                    {
                        "owner": owner,
                        "repo": repo,
                        "path": path,
                    },
                )

                data = result.data

                documents.append(
                    Document(
                        page_content=data["content"],
                        metadata={
                            "owner": owner,
                            "repo": repo,
                            "path": data["path"],
                            "sha": data["sha"],
                            "url": data["url"],
                        },
                    )
                )

            logger.info(
                "Repository loading completed: repository=%s/%s | documents=%s | skipped=%s",
                owner,
                repo,
                len(documents),
                skipped_files,
            )

            return documents

    except Exception:
        logger.exception(
            "Repository loading failed: repository=%s/%s",
            owner,
            repo,
        )
        raise