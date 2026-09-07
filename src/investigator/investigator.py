from langchain_groq import ChatGroq

from src.config.settings import settings
from src.investigator.analyzer import RepositoryAnalysis


class RepositoryInvestigator:
    def __init__(self):
        self.llm = ChatGroq(
            model="openai/gpt-oss-120b",
            temperature=0,
            api_key=settings.groq_api_key,
        )

        self.structured_llm = self.llm.with_structured_output(
            RepositoryAnalysis
        )

    def analyze(self, context: str) -> RepositoryAnalysis:
        prompt = f"""
Analyze the following GitHub repository context.

Provide:
- A concise summary
- Architecture
- Technologies used
- Strengths
- Weaknesses
- Recommendations

Only use information present in the context.
Do not invent technologies or functionality.

Repository context:

{context}
"""

        return self.structured_llm.invoke(prompt)