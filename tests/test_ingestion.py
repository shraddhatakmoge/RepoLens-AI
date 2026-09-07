import asyncio

from fastmcp import Client

from src.ingestion.loader import load_repository
from src.ingestion.splitter import split_documents


async def main():
    async with Client("http://127.0.0.1:8000/mcp") as client:
        result = await client.call_tool(
            "list_files",
            {
                "owner": "octocat",
                "repo": "Hello-World",
            },
        )

        print("FILES FROM GITHUB:")
        print(result.data)

    documents = await load_repository(
        owner="octocat",
        repo="Hello-World",
    )

    print("\nDOCUMENTS:", len(documents))

    chunks = split_documents(documents)

    print("CHUNKS:", len(chunks))


asyncio.run(main())