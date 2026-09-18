# AGENTS.md

Python 3.14 project managed with `uv` (see `.python-version`, `uv.lock`). `src/` is a plain package executed from the repo root — it is **not pip-installable** (no `[build-system]`, no setuptools config), so all imports are absolute (`from src.models.schema import ...`) and the cwd must be the repo root.

## Commands

- Run: `uv run python -m src` (entrypoint `src/__main__.py`)
- Lint: `uvx ruff check src` — ruff is **not a project dependency**; only `[tool.ruff.lint]` config lives in `pyproject.toml`. It currently reports errors (e.g. unused imports in `src/scraper/registry.py`, blind `except Exception` in `nos.py`).
- Add deps: `uv add <pkg>`
- No tests, no CI, no type checker are configured.

## Architecture

- **Scrapers register via import side-effect.** Each source lives in `src/scraper/sources/` and self-registers with the `@source(name, url)` decorator in `src/scraper/registry.py`, which populates the `SOURCE_SCRAPERS` dict keyed by `(name, url)`. New scrapers are only picked up if imported in `src/scraper/sources/__init__.py`. Signature: `(name, url, start_date: datetime | None) -> list[Article]`.
- `src/scraper/__init__.py` imports `src.scraper.sources`, so `import src`/`import src.scraper` triggers registration.
- **Known inconsistency in the models layer:** `src/models/db.py` references a `Source` enum that is never defined, while `Article.source` is `str` in `src/models/schema.py`. Reconcile this before relying on `get_by_source`/`get_latest_scrape_by_source`.
- `src/agents/` is a stub (empty files, including a stray duplicated `src/agents/agents/` package) — planned for classification/ranking/summarization, not implemented.

## Gotchas

- `articles.db` (SQLite) is not gitignored and is recreated/updated on every run.
- ruff is configured to ignore `DTZ001/DTZ002/DTZ005`; datetime values are stored as naive `datetime.now()`.