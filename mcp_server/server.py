from fastmcp import FastMCP
import os
from src.config.logging_config import (
    get_logger,
    setup_logging,
)

from mcp_server.tools.commits import get_commits
from mcp_server.tools.files import list_files, read_file
from mcp_server.tools.repository import get_readme, get_repository
from mcp_server.tools.search import search_code


setup_logging()

logger = get_logger(__name__)


mcp = FastMCP("RepoLens")


mcp.tool(get_repository)
mcp.tool(list_files)
mcp.tool(read_file)
mcp.tool(search_code)
mcp.tool(get_readme)
mcp.tool(get_commits)


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 8001))

    logger.info(
        "Starting RepoLens MCP server"
    )

    logger.info(
        "MCP server address: http://0.0.0.0:%s",
        port,
    )

    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=port,
    )