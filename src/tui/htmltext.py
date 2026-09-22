import re
from html import unescape
from html.parser import HTMLParser

from rich.text import Text

Block = tuple[str, "Text"]

_INLINE_TAGS = {"b": "bold", "strong": "bold", "i": "italic", "em": "italic"}
_BLOCK_TAGS = {"p", "li", "br", "div"}
_HEADINGS = {f"h{i}" for i in range(1, 7)}


class _HTMLToBlocks(HTMLParser):
    """Convert simple HTML into rich Text blocks.

    Headings (<h1>-<h6>) become "heading" blocks, list items become "li"
    blocks, everything else is a "para" block. Inline styling (bold,
    italic) is preserved; all other tags are stripped.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[Block] = []
        self._buf = ""
        self._block: str | None = None
        self._inline: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in _HEADINGS:
            self._flush()
            self._block = "heading"
        elif tag in ("p", "li", "div"):
            self._flush()
            self._block = "li" if tag == "li" else "para"
        elif tag == "br":
            self._flush()
        elif tag in _INLINE_TAGS:
            self._inline.append(_INLINE_TAGS[tag])

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _INLINE_TAGS:
            if self._inline:
                self._inline.pop()
        elif tag in _BLOCK_TAGS or tag in _HEADINGS:
            self._flush()

    def handle_data(self, data: str) -> None:
        self._buf += data

    def _flush(self) -> None:
        content = re.sub(r"\s+", " ", self._buf).strip()
        self._buf = ""
        if not content:
            return
        kind = self._block or "para"
        style = " ".join(self._inline) or None
        self.blocks.append((kind, Text(content, style=style)))
        if kind == "heading":
            self._block = "para"
            self._inline.clear()


def html_to_blocks(text: str) -> list[Block]:
    """Parse HTML text into (kind, rich Text) blocks; plain text falls through."""
    if "<" not in text:
        return [("para", Text(text))]
    parser = _HTMLToBlocks()
    parser.feed(text)
    parser.close()
    parser._flush()
    return parser.blocks


def clean_title(text: str) -> str:
    """Strip any tags and unescape entities for single-line display."""
    plain = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", unescape(plain)).strip()