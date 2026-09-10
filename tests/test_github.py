import asyncio

from fastmcp import Client

from src.config.settings import settings


MCP_URL = "https://api.githubcopilot.com/mcp/"


async def main():
    async with Client(
        MCP_URL,
        auth=settings.github_token,
    ) as client:

        print("Connected to GitHub official MCP server")
        print("Protocol version:", client.protocol_version)

        tools = await client.list_tools()

        print("\nAvailable tools:\n")

        for tool in tools:
            print(f"\nNAME: {tool.name}")
            print(f"DESCRIPTION: {tool.description}")
            print(f"INPUT SCHEMA: {tool.inputSchema}")

        print("\nTesting get_file_contents on repository root...\n")

        result = await client.call_tool(
    "get_file_contents",
    {
        "owner": "shraddhatakmoge",
        "repo": "Langchain",
        "path": "README.md",
        "ref": "9f7b66af246912aa862d0fee2b5e72a66b9b235f",
    },
)

        print("\nRESULT TYPE:")
        print(type(result))

        print("\nRESULT DATA:")
        print(result.data)

        print("\nRESULT CONTENT:")
        print(result.content)

        print("\nCONTENT ITEMS:")

        for index, content in enumerate(result.content):
        
            print(f"\n--- ITEM {index} ---")
            print("TYPE:", type(content))
            print("VALUE:", content)
            print("HAS TEXT:", hasattr(content, "text"))
            print("HAS RESOURCE:", hasattr(content, "resource"))
        
            if hasattr(content, "text"):
                print("TEXT:", content.text)
        
            if hasattr(content, "resource"):
                print("RESOURCE:", content.resource)

if __name__ == "__main__":
    asyncio.run(main())