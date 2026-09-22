import datetime
import webbrowser
from typing import ClassVar

from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.coordinate import Coordinate
from textual.events import Key
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Label

from src.models.db import ArticleDB
from src.models.schema import Article, Tag
from src.scraper.registry import SOURCE_SCRAPERS
from src.service.scheduler import Scheduler
from src.tui.htmltext import clean_title, html_to_blocks
from src.tui.theme import AYU_MIRAGE

DIGIT_TIMEOUT = 1.5
MUTED = "#607080"
HEADLINE_TRUNCATE = 90

SOURCE_DISPLAY_NAMES = {
    "nos_algemeen": "NOS",
    "nos_binnenland": "NOS binnenland",
    "nos_tech": "NOS tech",
    "consultancy_nl": "Consultancy",
    "tweakers": "Tweakers",
}


def display_name(source: str) -> str:
    return SOURCE_DISPLAY_NAMES.get(source, source)


Row = tuple[tuple[str, str, str], str | None]


class SchedulerEvent(Message):
    """Posted (via call_from_thread) from the scheduler thread."""

    def __init__(self, kind: str) -> None:
        super().__init__()
        self.kind = kind


class ArticleScreen(ModalScreen):
    BINDINGS: ClassVar = [
        Binding("q", "close", "Back"),
        Binding("escape", "close", show=False),
        Binding("o", "browser", "Open in browser"),
        Binding("j", "scroll_down", show=False),
        Binding("k", "scroll_up", show=False),
        Binding("g", "scroll_home", show=False),
        Binding("G", "scroll_end", show=False),
    ]

    def __init__(self, db: ArticleDB, url: str) -> None:
        super().__init__()
        self.db = db
        self.url = url

    def compose(self) -> ComposeResult:
        with Horizontal(id="topbar"):
            yield Label("newsagg", id="brand")
            yield Label("", id="digitbuf")
            yield Label(
                datetime.datetime.now().strftime("%a %d %b %H:%M:%S"),
                id="clock",
            )
        article = self.db.get_by_url(self.url)
        with VerticalScroll(id="article-body"):
            if article:
                yield Label(clean_title(article.title), id="article-title")
                yield Label(self._meta(article), id="article-meta")
                if article.summary:
                    yield Label(article.summary, id="article-summary")
                if article.key_points:
                    yield Label(
                        "\n".join(f"• {p}" for p in article.key_points),
                        id="article-keys",
                    )
                blocks = html_to_blocks(article.text) if article.text else []
                if not blocks:
                    yield Label("(no text)", classes="article-para")
                for kind, segment in blocks:
                    if kind == "heading":
                        yield Label(segment, classes="article-heading")
                    elif kind == "li":
                        yield Label(
                            Text("• ", style="bold") + segment,
                            classes="article-para",
                        )
                    else:
                        yield Label(segment, classes="article-para")
            else:
                yield Label("Article not found.", classes="article-para")
        yield Label(
            "q/escape back · o open in browser · j/k scroll · g/G top/end",
            id="footer-info",
        )
        yield Footer()

    @staticmethod
    def _meta(article: Article) -> str:
        published = article.published_on.strftime("%a %d %b %H:%M")
        return f"{display_name(article.source)}  ·  {published}  ·  {article.url}"

    def action_close(self) -> None:
        self.dismiss()

    def action_scroll_down(self) -> None:
        self.query_one("#article-body", VerticalScroll).scroll_down()

    def action_scroll_up(self) -> None:
        self.query_one("#article-body", VerticalScroll).scroll_up()

    def action_scroll_home(self) -> None:
        self.query_one("#article-body", VerticalScroll).scroll_home()

    def action_scroll_end(self) -> None:
        self.query_one("#article-body", VerticalScroll).scroll_end()

    def action_browser(self) -> None:
        webbrowser.open(self.url)


class PageIndexScreen(ModalScreen):
    BINDINGS: ClassVar = [
        Binding("escape", "close", "Back"),
        Binding("i", "close", "Back", show=False),
        Binding("j", "cursor_down", show=False),
        Binding("k", "cursor_up", show=False),
    ]

    def __init__(self, pages: dict[int, tuple[str, object]]) -> None:
        super().__init__()
        self.pages = pages

    def compose(self) -> ComposeResult:
        table = DataTable(id="page-index", cursor_type="row", zebra_stripes=True)
        table.add_column("Page", width=8)
        table.add_column("Title")
        for number, (title, _) in sorted(self.pages.items()):
            table.add_row(str(number), title, key=str(number))
        yield table

    def action_cursor_down(self) -> None:
        self.query_one("#page-index", DataTable).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#page-index", DataTable).action_cursor_up()

    def action_close(self) -> None:
        self.dismiss()

    @on(DataTable.RowSelected)
    def page_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key.value:
            event.stop()
            self.dismiss()
            self.app._goto(int(event.row_key.value))


class NewsAggApp(App):
    CSS_PATH = "styles.tcss"
    BINDINGS: ClassVar = [
        Binding("q", "quit", "Quit"),
        Binding("r", "scrape_now", "Scrape"),
        Binding("i", "page_index", "Pages"),
        Binding("h", "prev_page", "Prev"),
        Binding("l", "next_page", "Next"),
        Binding("j", "cursor_down", show=False),
        Binding("k", "cursor_up", show=False),
        Binding("g", "cursor_top", show=False),
        Binding("G", "cursor_bottom", show=False),
        Binding("n", "next_page", show=False),
        Binding("p", "prev_page", show=False),
    ]
    page: reactive[int] = reactive(100)

    def __init__(self, db: ArticleDB) -> None:
        super().__init__()
        self.register_theme(AYU_MIRAGE)
        self.theme = "ayu-mirage"
        self.db = db
        self.scheduler = Scheduler(db)
        self.pages = self._build_pages()
        self._buffer = ""
        self._buffer_timer = None

    def _build_pages(self) -> dict[int, tuple[str, object]]:
        pages: dict[int, tuple[str, object]] = {
            100: ("INDEX", lambda: self._headlines(self.db.get_recent(30)))
        }
        for i, tag in enumerate(Tag, start=101):
            pages[i] = (
                tag.value.upper(),
                lambda t=tag: self._headlines(self.db.get_recent(30, topic=t)),
            )
        sources = sorted({name for name, _ in SOURCE_SCRAPERS})
        for i, name in enumerate(sources, start=200):
            pages[i] = (
                display_name(name).upper(),
                lambda s=name: self._headlines(self.db.get_recent(30, source=s)),
            )
        pages[900] = ("STATUS", self._status_rows)
        return pages

    @staticmethod
    def _headlines(articles: list[Article]) -> list[Row]:
        rows = []
        for a in articles:
            time_part = a.published_on.strftime("%H:%M")
            title = clean_title(a.title)
            if len(title) > HEADLINE_TRUNCATE:
                title = title[: HEADLINE_TRUNCATE - 3] + "..."
            rows.append(((time_part, display_name(a.source), title), a.url))
        return rows

    def _status_rows(self) -> list[Row]:
        rows = []
        for name, result in sorted(self.scheduler.results.items()):
            label = display_name(name)
            if result.error:
                rows.append(
                    (
                        (
                            label,
                            Text("ERROR", style="red"),
                            Text(result.error, style="red"),
                        ),
                        None,
                    )
                )
            else:
                finished = result.finished_at.strftime("%H:%M:%S")
                rows.append(
                    (
                        (
                            label,
                            Text("ok", style="green"),
                            f"+{result.new_count} new  {finished}",
                        ),
                        None,
                    )
                )
        if self.scheduler.last_cycle:
            next_run = self.scheduler.last_cycle + datetime.timedelta(
                seconds=self.scheduler.interval
            )
            summarized = self.scheduler.last_summary_count
            rows.append(
                (
                    (
                        "cycle",
                        Text("info", style=MUTED),
                        Text(
                            f"last {self.scheduler.last_cycle:%H:%M:%S}  "
                            f"next {next_run:%H:%M:%S}  "
                            f"summarized {summarized}",
                            style=MUTED,
                        ),
                    ),
                    None,
                )
            )
        if self.scheduler.last_error:
            rows.append(
                (
                    (
                        "cycle",
                        Text("ERROR", style="red"),
                        Text(self.scheduler.last_error, style="red"),
                    ),
                    None,
                )
            )
        return rows

    def compose(self) -> ComposeResult:
        with Horizontal(id="topbar"):
            yield Label("newsagg", id="brand")
            yield Label("", id="digitbuf")
            yield Label(
                datetime.datetime.now().strftime("%a %d %b %H:%M:%S"),
                id="clock",
            )
        yield Label("", id="pagetitle")
        yield DataTable(id="headlines", cursor_type="row", zebra_stripes=True)
        yield Label(
            "page 100-900 · h/j/k/l navigate · i pages · enter read · "
            "r scrape · q quit",
            id="footer-info",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(1, self._tick_clock)
        self.run_worker(self._run_scheduler, thread=True, exclusive=True)
        self._show_page()

    def on_unmount(self) -> None:
        self.scheduler.stop()

    def _run_scheduler(self) -> None:
        self.scheduler.loop(self._post_scheduler_event)

    def _tick_clock(self) -> None:
        now = datetime.datetime.now().strftime("%a %d %b %H:%M:%S")
        for screen in self.screen_stack:
            for clock in screen.query("#clock"):
                clock.update(now)

    def _post_scheduler_event(self, event: str) -> None:
        # called from the scheduler thread
        self.call_from_thread(self.post_message, SchedulerEvent(event))

    @on(SchedulerEvent)
    def scheduler_event(self, event: SchedulerEvent) -> None:
        if event.kind == "scrape":
            new = sum(r.new_count for r in self.scheduler.results.values())
            if new:
                self.notify(f"{new} new article(s)")
            self._show_page()
        elif event.kind == "summary":
            count = self.scheduler.last_summary_count or 0
            if count:
                self.notify(f"Summarized {count} article(s)")

    def action_scrape_now(self) -> None:
        self.scheduler.wakeup.set()

    def _headline_table(self) -> DataTable | None:
        if len(self.screen_stack) > 1:
            return None
        return self.query_one("#headlines", DataTable)

    def action_cursor_down(self) -> None:
        if table := self._headline_table():
            table.action_cursor_down()

    def action_cursor_up(self) -> None:
        if table := self._headline_table():
            table.action_cursor_up()

    def action_cursor_top(self) -> None:
        if table := self._headline_table():
            table.move_cursor(row=0)

    def action_cursor_bottom(self) -> None:
        if table := self._headline_table():
            table.move_cursor(row=max(0, table.row_count - 1))

    def action_page_index(self) -> None:
        self.push_screen(PageIndexScreen(self.pages))

    # -- pages ----------------------------------------------------------

    def watch_page(self) -> None:
        if self.is_mounted:
            self._show_page()

    def _show_page(self) -> None:
        title, loader = self.pages[self.page]
        self.query_one("#pagetitle", Label).update(f"P{self.page}  {title}")
        table = self.query_one("#headlines", DataTable)
        current_key = None
        if table.row_count:
            try:
                current_key = table.coordinate_to_cell_key(
                    Coordinate(table.cursor_row, 0)
                ).row_key.value
            except Exception:  # noqa: BLE001
                current_key = None
        table.clear(columns=True)
        table.add_column("Time", width=6, key="time")
        table.add_column("Source", width=18, key="source")
        table.add_column("Headline", key="headline")
        rows = loader()
        if not rows:
            table.add_row(
                "--",
                "--",
                Text("(no articles yet)", style=MUTED),
            )
        restore_row = 0
        for i, (cells, key) in enumerate(rows):
            table.add_row(*cells, key=key)
            if key and key == current_key:
                restore_row = i
        table.move_cursor(row=restore_row, scroll=False)

    def _goto(self, page: int) -> None:
        if page in self.pages:
            self.page = page

    def action_next_page(self) -> None:
        numbers = sorted(self.pages)
        idx = numbers.index(self.page)
        self._goto(numbers[(idx + 1) % len(numbers)])

    def action_prev_page(self) -> None:
        numbers = sorted(self.pages)
        idx = numbers.index(self.page)
        self._goto(numbers[(idx - 1) % len(numbers)])

    def on_key(self, event: Key) -> None:
        if len(self.screen_stack) > 1:
            return
        if event.character and event.character.isdigit():
            self._buffer += event.character
            self.query_one("#digitbuf", Label).update(f"P{self._buffer}")
            if self._buffer_timer:
                self._buffer_timer.stop()
            self._buffer_timer = self.set_timer(DIGIT_TIMEOUT, self._flush_buffer)
            if len(self._buffer) >= 3:
                self._flush_buffer()

    def _flush_buffer(self) -> None:
        if self._buffer_timer:
            self._buffer_timer.stop()
            self._buffer_timer = None
        if self._buffer:
            self._goto(int(self._buffer))
        self._buffer = ""
        self.query_one("#digitbuf", Label).update("")

    @on(DataTable.RowSelected)
    def row_selected(self, event: DataTable.RowSelected) -> None:
        url = event.row_key.value
        if url and url.startswith("http"):
            self.push_screen(ArticleScreen(self.db, url))


def run_tui(db: ArticleDB) -> None:
    NewsAggApp(db).run()

