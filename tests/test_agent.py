import asyncio

from src.agent.agent import RepoLensAgent


async def main():
    agent = RepoLensAgent()

    answer = await agent.ask(
        question="What does this repository contain?",
        owner="octocat",
        repo="Hello-World",
    )

    print("\nANSWER:\n")
    print(answer)


asyncio.run(main())