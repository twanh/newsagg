from pydantic import BaseModel

from src.models.schema import Tag


class ArticleSummary(BaseModel):
    """Structured summary of a single news article."""

    summary: str
    topic: Tag
    key_points: list[str]
