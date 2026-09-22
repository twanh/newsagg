import datetime
import threading
from dataclasses import dataclass

from src.agents.summarize_agent import summarize_articles
from src.models.db import ArticleDB
from src.scraper.registry import SOURCE_SCRAPERS

SCRAPE_INTERVAL_SECONDS = 10 * 60


@dataclass
class SourceResult:
    source: str
    new_count: int
    finished_at: datetime.datetime
    error: str | None = None


class Scheduler:
    """Runs scrape + summarize cycles; designed to run in a thread worker."""

    def __init__(
        self, db: ArticleDB, interval: int = SCRAPE_INTERVAL_SECONDS
    ):
        self.db = db
        self.interval = interval
        self.results: dict[str, SourceResult] = {}
        self.last_cycle: datetime.datetime | None = None
        self.last_summary_count: int | None = None
        self.last_error: str | None = None
        self.wakeup = threading.Event()
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()
        self.wakeup.set()

    def run_cycle(self) -> list[SourceResult]:
        results = []
        for (name, url), scraper in SOURCE_SCRAPERS.items():
            try:
                cutoff = self.db.get_latest_scrape_by_source(name)
                articles = scraper(name, url, cutoff)
                new_count = 0
                for article in articles:
                    if not self.db.exists(article.url):
                        self.db.save(article)
                        new_count += 1
                result = SourceResult(
                    name, new_count, datetime.datetime.now()
                )
            except Exception as e:  # noqa: BLE001
                result = SourceResult(
                    name, 0, datetime.datetime.now(), error=str(e)
                )
            self.results[name] = result
            results.append(result)
        self.last_cycle = datetime.datetime.now()
        return results

    def summarize(self) -> int:
        articles = self.db.get_without_summary()
        if not articles:
            return 0
        summaries = summarize_articles(articles)
        for article, article_summary in zip(
            articles, summaries, strict=False
        ):
            self.db.update_summary(
                article.url,
                article_summary.summary,
                article_summary.topic,
                article_summary.key_points,
            )
        return len(summaries)

    def loop(
        self, on_event, wakeup: threading.Event | None = None
    ) -> None:
        """Run cycles forever; on_event(str) is called after each step."""
        while not self._stop.is_set():
            try:
                self.run_cycle()
                self.last_error = None
            except Exception as e:  # noqa: BLE001
                self.last_error = str(e)
            on_event("scrape")
            try:
                self.last_summary_count = self.summarize()
                self.last_error = None
            except Exception as e:  # noqa: BLE001
                self.last_error = str(e)
            on_event("summary")
            self.wakeup.wait(self.interval)
            self.wakeup.clear()