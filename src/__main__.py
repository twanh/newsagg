from src.models.db import ArticleDB

from src.scraper.registry import SOURCE_SCRAPERS


def main() -> int:

    print("Welcome to newsagg!")

    # Create a database connection
    db = ArticleDB("articles.db")
    print("Starting scraping process...")
    print(SOURCE_SCRAPERS)

    for source, scraper in SOURCE_SCRAPERS.items():
        print(f"Scraping source: {source}")

        latest_scrape_time = db.get_latest_scrape_by_source(source[0])
        print(f"Starting from {latest_scrape_time}")

        articles = scraper(*source, latest_scrape_time)
        print(f"Found {len(articles)} articles for source: {source})")

        # Save articles to the database
        for article in articles:
            db.save(article)

    # Update the database (or time of last scrape??)

    # Run through all the sources and scapre the source

    # Update entries in the database

    # Agents do the following:
    # Classify news item type
    # Rank importance
    # Rank relevance
    # Create sumaries

    # Rank all the news articles

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
