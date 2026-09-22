import datetime
import logging
import re

import httpx
from rss_parser import UnknownFeedTypeError, parse

from src.models.schema import Article
from src.scraper.registry import source

logger = logging.getLogger(__name__)

logger.debug("Consultancy.nl scraper module loaded.")

_DUTCH_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mrt": 3,
    "apr": 4,
    "mei": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "okt": 10,
    "nov": 11,
    "dec": 12,
}

_PUB_DATE_RE = re.compile(
    r"^[a-zA-Z]{2},\s+(\d{1,2})\s+([a-z]+)\.?\s+(\d{4})\s+(\d{2}):(\d{2}):(\d{2})",
    re.IGNORECASE,
)


def _parse_pub_date(value: str) -> datetime.datetime:
    """Parse a Consultancy.nl RSS pubDate like 'ma, 21 sep. 2026 05:10:00 UTC'."""
    match = _PUB_DATE_RE.match(value.strip())
    if not match:
        raise ValueError(f"Unparseable pubDate: {value!r}")

    day, month, year, hour, minute, second = match.groups()
    month_number = _DUTCH_MONTHS.get(month.lower())
    if month_number is None:
        raise ValueError(f"Unknown month in pubDate: {value!r}")

    return datetime.datetime(
        int(year),
        month_number,
        int(day),
        int(hour),
        int(minute),
        int(second),
    )


@source("consultancy_nl", "https://www.consultancy.nl/rss/consultancy_rssfeed.xml")
def scrape_consultancy_nl(
    name: str, url: str, start_date: datetime.datetime | None = None
) -> list[Article]:
    articles = []

    try:
        response = httpx.get(url, timeout=10)
        response.raise_for_status()
        feed = parse(response.text)

        assert hasattr(feed, "channel"), "Invalid feed structure (no channel)"
        assert hasattr(feed.channel, "items"), (
            "Invalid feed structure (no items on channel)"
        )

        for entry in feed.channel.items:
            entry_content = entry.dict().get("content", None)

            pub_date = _parse_pub_date(entry_content["pub_date"]["content"])
            if start_date and pub_date < start_date:
                break

            article = Article(
                source=name,
                url=entry_content["links"][0]["content"],
                title=entry_content["title"]["content"],
                text=entry_content["description"]["content"],
                published_on=pub_date,
                scraped_on=datetime.datetime.now(),
                raw_tags=[],
            )

            articles.append(article)

    except httpx.RequestError as e:
        logger.error("Error scraping %s: %s", name, e)

    except UnknownFeedTypeError as e:
        logger.error("Error parsing feed for %s: %s", name, e)

    except (ValueError, KeyError, IndexError) as e:
        logger.error("Error parsing feed entries for %s: %s", name, e)

    return articles