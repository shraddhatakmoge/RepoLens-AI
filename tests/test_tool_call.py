from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_groq import ChatGroq

from src.config.settings import settings


@tool
def list_files() -> str:
    """List the files in the repository."""
    return "README.md, chatbot.py, sequentialchain.py, simple_Chain.py"


llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0,
    api_key=settings.groq_api_key,
    include_reasoning=False,
)


agent = create_agent(
    model=llm,
    tools=[list_files],
    system_prompt="Use the list_files tool when the user asks about repository files.",
)


result = agent.invoke(
    {
        "messages": [
            {
                "role": "user",
                "content": "List all files in the repository.",
            }
        ]
    }
)

print(result["messages"][-1].content)