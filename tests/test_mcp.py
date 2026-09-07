import asyncio

from fastmcp import Client


async def main():
    async with Client("http://127.0.0.1:8000/mcp") as client:
        file_result = await client.call_tool(
            "list_files",
            {
                "owner": "shraddhatakmoge",
                "repo": "Langchain",
            },
        )

        print("TOTAL:", file_result.data["total_files"])

        result = await client.call_tool(
            "read_file",
            {
                "owner": "shraddhatakmoge",
                "repo": "Langchain",
                "path": "README.md",
            },
        )

        print("PATH:", result.data["path"])
        print("CONTENT:")
        print(result.data["content"])


asyncio.run(main())