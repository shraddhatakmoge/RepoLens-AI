from pydantic import BaseModel, Field


class RepositoryAnalysis(BaseModel):
    summary: str
    architecture: str
    technologies: list[str]
    strengths: list[str]
    weaknesses: list[str]
    recommendations: list[str]