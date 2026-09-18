from dataclasses import dataclass
from dataclasses import field
import datetime
import enum


class Tag(enum.Enum):
    # TODO: Update with relevant tags
    POLITICS = "Politics"
    ECONOMY = "Economy"
    SPORTS = "Sports"
    ENTERTAINMENT = "Entertainment"
    TECHNOLOGY = "Technology"
    HEALTH = "Health"
    SCIENCE = "Science"
    WORLD = "World"
    LOCAL = "Local"


class RelevanceRank(enum.Enum):
    """Enum for the relevance rank of news articles."""

    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


@dataclass()
class Article:
    # The title of the news article
    title: str
    # Metadata
    source: str
    url: str

    published_on: datetime.datetime
    scraped_on: datetime.datetime

    # Raw
    text: str
    raw_tags: list[Tag]

    # Names of the authors
    authors: list[str] = field(default_factory=list)
    summary: str | None = None
    rank: RelevanceRank | None = None
