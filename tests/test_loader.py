import asyncio

from src.ingestion.loader import load_repository


async def main():
    documents = await load_repository(
        "shraddhatakmoge",
        "Langchain",
    )

    print(f"\nDocuments loaded: {len(documents)}\n")

    for document in documents[:5]:
        print("=" * 80)
        print(document.metadata)
        print(document.page_content[:300])


if __name__ == "__main__":
    asyncio.run(main())