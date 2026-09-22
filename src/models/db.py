import sqlite3
import json
import datetime
from contextlib import contextmanager
from zoneinfo import ZoneInfo
from src.models.schema import Article, Tag

AMSTERDAM = ZoneInfo("Europe/Amsterdam")


class ArticleDB:
    def __init__(self, path: str = "articles.db"):
        self.path = path
        self._init_schema()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    url TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    source TEXT NOT NULL,
                    published_on TEXT NOT NULL,
                    scraped_on TEXT NOT NULL,
                    text TEXT NOT NULL,
                    raw_tags TEXT NOT NULL,
                    authors TEXT NOT NULL,
                    summary TEXT,
                    topic TEXT,
                    key_points TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_source ON articles(source)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_published ON articles(published_on)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scrapes ( source TEXT PRIMARY KEY, last_scraped_on TEXT NOT NULL
                )
                """
            )

    def save(self, article: Article):
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO articles (url, title, source, published_on, scraped_on,
                                       text, raw_tags, authors, summary,
                                       topic, key_points)
                VALUES (:url, :title, :source, :published_on, :scraped_on,
                        :text, :raw_tags, :authors, :summary,
                        :topic, :key_points);
            """,
                self._to_row(article),
            )

    def save_many(self, articles: list[Article]):
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO articles (url, title, source, published_on, scraped_on,
                                       text, raw_tags, authors, summary,
                                       topic, key_points)
                VALUES (:url, :title, :source, :published_on, :scraped_on,
                        :text, :raw_tags, :authors, :summary,
                        :topic, :key_points);
            """,
                [self._to_row(a) for a in articles],
            )

    def update_summary(
        self, url: str, summary: str, topic: Tag, key_points: list[str]
    ):
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE articles
                SET summary = :summary, topic = :topic, key_points = :key_points
                WHERE url = :url;
            """,
                {
                    "url": url,
                    "summary": summary,
                    "topic": topic.value,
                    "key_points": json.dumps(key_points),
                },
            )

    def get_all(self) -> list[Article]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM articles ORDER BY published_on DESC"
            ).fetchall()
            return [self._from_row(row) for row in rows]

    def get_without_summary(self) -> list[Article]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM articles WHERE summary IS NULL ORDER BY published_on DESC"
            ).fetchall()
            return [self._from_row(row) for row in rows]

    def get_recent(
        self,
        limit: int = 50,
        topic: Tag | None = None,
        source: str | None = None,
    ) -> list[Article]:
        query = "SELECT * FROM articles"
        clauses, params = [], []
        if topic:
            clauses.append("topic = ?")
            params.append(topic.value)
        if source:
            clauses.append("source = ?")
            params.append(source)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY published_on DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._from_row(row) for row in rows]

    def get_by_source(self, source: str) -> list[Article]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM articles WHERE source = ? ORDER BY published_on DESC",
                (source,),
            ).fetchall()
            return [self._from_row(row) for row in rows]

    def get_by_url(self, url: str) -> Article | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM articles WHERE url = ?", (url,)
            ).fetchone()
            if row:
                return self._from_row(row)
            else:
                return None

    def get_latest_scrape_by_source(self, source: str) -> datetime.datetime | None:

        with self._connect() as conn:
            row = conn.execute(
                "SELECT max(scraped_on) as latest_scrape FROM articles WHERE source = ?",
                (source,),
            ).fetchone()

        if row and row["latest_scrape"]:
            return datetime.datetime.fromisoformat(row["latest_scrape"])
        else:
            return None

    def exists(self, url: str) -> bool:
        with self._connect() as conn:
            return (
                conn.execute("SELECT 1 FROM articles WHERE url = ?", (url,)).fetchone()
                is not None
            )

    @staticmethod
    def _to_row(article: Article) -> dict:
        def amsterdam_naive(dt: datetime.datetime) -> datetime.datetime:
            return dt.astimezone(AMSTERDAM).replace(tzinfo=None)

        return {
            "url": article.url,
            "title": article.title,
            "source": article.source,
            "published_on": amsterdam_naive(article.published_on).isoformat(),
            "scraped_on": amsterdam_naive(article.scraped_on).isoformat(),
            "text": article.text,
            "raw_tags": json.dumps([t.value for t in article.raw_tags]),
            "authors": json.dumps(article.authors),
            "summary": article.summary,
            "topic": article.topic.value if article.topic else None,
            "key_points": json.dumps(article.key_points),
        }

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Article:
        return Article(
            title=row["title"],
            source=row["source"],
            url=row["url"],
            published_on=datetime.datetime.fromisoformat(row["published_on"]),
            scraped_on=datetime.datetime.fromisoformat(row["scraped_on"]),
            text=row["text"],
            raw_tags=[Tag(t) for t in json.loads(row["raw_tags"])],
            authors=json.loads(row["authors"]),
            summary=row["summary"],
            topic=Tag(row["topic"]) if row["topic"] else None,
            key_points=json.loads(row["key_points"]) if row["key_points"] else [],
        )
