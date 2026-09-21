import os
from src.models.db import ArticleDB

from src.scraper.registry import SOURCE_SCRAPERS
from src.agents.agents.summarize_agent import summarize_articles

from dotenv import load_dotenv


def main() -> int:

    print("Welcome to newsagg!")

    load_dotenv()

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
            # Check that the URL is not already in the DB
            existing_article = db.get_by_url(article.url)
            if existing_article:
                print(
                    f"Article already exists in the database: {article.title} ({article.url}), added by source {article.source}"
                )
                continue

            db.save(article)

    # Summarize articles that don't have a summary yet

    unsummarized = db.get_without_summary()
    if unsummarized:
        print(f"Summarizing {len(unsummarized)} articles...")
        summaries = summarize_articles(unsummarized)
        for article, article_summary in zip(unsummarized, summaries, strict=True):
            db.update_summary(
                article.url,
                article_summary.summary,
                article_summary.topic,
                article_summary.key_points,
            )

            print("Updated article summary in the database:")
            print(f"Title: {article.title}")
            print(f"URL: {article.url}")
            print(f"Summary: {article_summary.summary}")
    else:
        print("No articles to summarize.")

    # Give a news overview
    print("Generating news overview...")
    overview = db.get_all()

    for article in overview:
        print(f"Title: {article.title}")
        print(f"URL: {article.url}")
        print(f"Summary: {article.summary}")
        print(f"Topic: {article.topic}")
        print(f"Key Points: {article.key_points}")
        print("-" * 40)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
