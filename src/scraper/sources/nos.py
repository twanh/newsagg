import datetime
import logging

import httpx
from rss_parser import UnknownFeedTypeError, parse

from src.models.schema import Article
from src.scraper.registry import source

logger = logging.getLogger(__name__)

logger.debug("NOS scraper module loaded.")


@source("nos_algemeen", "https://feeds.nos.nl/nosnieuwsalgemeen")
@source("nos_binnenland", "https://feeds.nos.nl/nosnieuwsbinnenland")
@source("nos_tech", "https://feeds.nos.nl/nosnieuwstech")
def _generic_nos_scraper(
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

            # First check pub date and see if we can stop
            # TODO: Double check that the articles are
            # sorted correcly by pubdate in the RSS feed
            pub_date = entry_content["pub_date"]["content"]
            if start_date and pub_date.replace(tzinfo=None) < start_date:
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

    return articles
