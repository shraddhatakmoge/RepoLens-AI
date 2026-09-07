import asyncio

from fastmcp import Client


async def main():
    async with Client("http://127.0.0.1:8000/mcp") as client:
        tools = await client.list_tools()

        print("AVAILABLE TOOLS:")

        for tool in tools:
            print(f"- {tool.name}")

        result = await client.call_tool(
            "get_repository",
            {
                "owner": "octocat",
                "repo": "Hello-World",
            },
        )

        print("\nGET REPOSITORY:")
        print(result.data)


asyncio.run(main())