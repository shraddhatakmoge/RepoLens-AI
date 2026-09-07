from fastmcp import FastMCP

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

    logger.info(
        "Starting RepoLens MCP server"
    )

    logger.info(
        "MCP server address: http://127.0.0.1:8001"
    )

    mcp.run(
        transport="http",
        host="127.0.0.1",
        port=8001,
    )