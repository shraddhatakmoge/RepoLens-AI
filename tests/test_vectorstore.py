import asyncio

from src.ingestion.loader import load_repository
from src.ingestion.splitter import split_documents
from src.vectorstore.pinecone_store import add_documents, similarity_search


async def main():
    documents = await load_repository(
        owner="octocat",
        repo="Hello-World",
    )

    chunks = split_documents(documents)

    print("Chunks:", len(chunks))

    add_documents(chunks)

    print("Uploaded to Pinecone.")

    results = similarity_search(
        "What is this repository?",
        k=3,
    )

    print("\nRESULTS:")

    for result in results:
        print("\n---")
        print(result.page_content)
        print(result.metadata)


asyncio.run(main())