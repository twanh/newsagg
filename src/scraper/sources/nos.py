import datetime

import httpx
from rss_parser import parse

from src.models.schema import Article
from src.scraper.registry import source

print("NOS scraper module loaded.")


@source("nos", "https://feeds.nos.nl/nosnieuwsalgemeen")
def scrape_nos(
    name: str, url: str, start_date: datetime.datetime | None = None
) -> list[Article]:

    articles = []

    try:
        response = httpx.get(url, timeout=10)
        response.raise_for_status()
        feed = parse(response.text)

        assert hasattr(feed, "channel"), "Invalid feed structure"
        assert hasattr(feed.channel, "items"), "Invalid feed structure"
        for entry in feed.channel.items:
            entry_content = entry.dict().get("content", None)

            # First check pub date and see if we can stop
            pub_date = entry_content["pub_date"]["content"]
            if start_date and pub_date.replace(tzinfo=None) < start_date:
                break

            # Parse the rest
            # ['title', 'links', 'description', 'author', 'categories', 'comments', 'enclosures', 'guid', 'pub_date', 'source'])
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

    except Exception as e:
        print(f"Error scraping {name}: {e}")

    return articles
