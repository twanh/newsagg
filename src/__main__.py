from dotenv import load_dotenv

from src.models.db import ArticleDB
from src.tui.app import run_tui


def main() -> int:
    load_dotenv()
    db = ArticleDB("articles.db")
    run_tui(db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())