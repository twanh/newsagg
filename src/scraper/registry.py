import datetime
from dataclasses import dataclass, field
from collections.abc import Callable, Iterable

from src.models.schema import Article

Scraper = Callable[[str, str, datetime.datetime | None], list[Article]]

SOURCE_SCRAPERS: dict[tuple[str, str], Scraper] = {}


def source(source: str, url: str) -> Callable[[Scraper], Scraper]:

    def register(fn: Scraper) -> Scraper:

        if source in SOURCE_SCRAPERS:
            raise ValueError(f"Scraper already registered for agency '{source}'")

        SOURCE_SCRAPERS[source, url] = fn
        return fn

    return register
