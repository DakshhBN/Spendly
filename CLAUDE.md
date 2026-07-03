# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Spendly** — a Flask-based personal expense tracker. The repo is structured as a step-by-step learning project; several routes and the entire database layer are intentional stubs for students to implement.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the development server (http://localhost:5001)
python app.py

# Run tests
pytest

# Run a single test file
pytest tests/test_db.py
```

## Architecture

**Stack:** Python / Flask · Jinja2 templates · SQLite · vanilla CSS + JS

```
app.py            — Flask app and all route definitions
database/db.py    — SQLite helpers (get_db, init_db, seed_db) — stub, not yet implemented
templates/        — Jinja2 HTML templates (base.html + page templates)
static/css/       — landing.css (landing page), style.css (app pages)
static/js/main.js — client-side JS (currently a placeholder)
```

**Route structure in `app.py`:**
- Implemented: `/`, `/register`, `/login`, `/terms`, `/privacy`
- Placeholder stubs (marked "coming in Step N"): `/logout`, `/profile`, `/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete`

**Database (`database/db.py`):**
- `get_db()` — SQLite connection with `row_factory` and foreign keys enabled
- `init_db()` — `CREATE TABLE IF NOT EXISTS` for all tables
- `seed_db()` — sample data for development

The database file is excluded from git via `.gitignore`.

## Notes

- Currency is Indian Rupee (₹); keep this consistent in templates and display logic.
- The `!` prefix on `flask==3.1.3` in `requirements.txt` is a typo — pip treats it as a comment. Fix to `flask==3.1.3` when editing that file.
