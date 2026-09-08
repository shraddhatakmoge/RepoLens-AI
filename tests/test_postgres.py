import asyncio

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.config.settings import settings


async def test():

    async with AsyncPostgresSaver.from_conn_string(
        settings.database_url
    ) as checkpointer:

        await checkpointer.setup()

        print(
            "PostgreSQL checkpointer setup successful"
        )


asyncio.run(
    test(),
    loop_factory=lambda: asyncio.SelectorEventLoop(),
)