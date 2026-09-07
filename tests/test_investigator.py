import asyncio

from src.ingestion.loader import load_repository
from src.ingestion.splitter import split_documents
from src.investigator.investigator import RepositoryInvestigator


async def main():
    documents = await load_repository(
        owner="octocat",
        repo="Hello-World",
    )

    chunks = split_documents(documents)

    context = "\n\n".join(
        f"File: {doc.metadata.get('path')}\n{doc.page_content}"
        for doc in chunks
    )

    investigator = RepositoryInvestigator()

    result = investigator.analyze(context)

    print("\nANALYSIS:\n")
    print(result.model_dump_json(indent=2))


asyncio.run(main())