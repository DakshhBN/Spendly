# Spendly

A full-stack personal expense tracker built with Flask and SQLite. Users register, log in, and manage categorized expenses (in ₹) with date-filtered summaries and category breakdowns — implemented with server-side session authentication, CSRF protection, and parameterized SQL throughout.

**Live demo:** [https://spendly-ln3t.onrender.com/](https://spendly-ln3t.onrender.com/)

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask |
| Templating | Jinja2 |
| Database | SQLite (raw `sqlite3`, no ORM) |
| Frontend | Vanilla HTML/CSS/JS |
| WSGI Server | Gunicorn |
| Testing | pytest, pytest-flask |
| Deployment | Render |

## Technical Highlights

**Authentication & Sessions**
- Stateless-server, server-side session auth via Flask's signed cookie sessions — `session["user_id"]` gates every protected route (`/profile`, `/expenses/*`), redirecting unauthenticated requests to `/login`.
- Passwords are never stored in plaintext: hashed with Werkzeug's `generate_password_hash` (salted PBKDF2) and verified with `check_password_hash`.
- `session.clear()` on login/logout to prevent session fixation across accounts.

**Security**
- Per-session CSRF tokens (`secrets.token_hex(32)`) generated in a `before_request` hook and validated on every state-changing POST (add/edit/delete expense) via constant-effort comparison and `abort(403)` on mismatch.
- All SQL is parameterized (`?` placeholders) — no string-built queries, eliminating SQL injection risk.
- Row-level ownership checks: every expense read/update/delete is scoped by `WHERE id = ? AND user_id = ?`, so one user can never touch another's data even with a guessed expense ID.
- Server-side input validation on amount (positive, capped), category (must match an allow-list), and date, independent of client-side checks.

**Database Design**
- Two-table relational schema (`users`, `expenses`) with a foreign key from `expenses.user_id → users.id` and `PRAGMA foreign_keys = ON` enforced per connection.
- Query layer (`database/queries.py`) is decoupled from the mutation layer (`database/db.py`), with aggregation done in SQL (`SUM`, `GROUP BY`, `COALESCE`) rather than in Python.
- Category breakdown percentages are computed and remainder-corrected so they always sum to exactly 100%.

**Architecture**
- Thin route handlers in `app.py` delegate validation, persistence, and querying to dedicated modules — routes stay focused on request/response flow.
- Shared form-validation helper (`_validate_expense_form`) reused across the add and edit routes to avoid duplicated logic.
- Test suite covers backend DB connectivity, expense CRUD, and date-range filtering.

## Features

- User registration and login
- Add, edit, and delete expenses
- Categorized spending: Food, Transport, Bills, Health, Entertainment, Shopping, Other
- Summary stats and category breakdown, filterable by date range
- Flash-messaged validation feedback

## Getting Started

### Prerequisites

- Python 3.10+

### Installation

```bash
# Clone the repository
git clone https://github.com/DakshhBN/Spendly.git
cd Spendly

# Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### Running the app

```bash
python app.py
```

The app will be available at [http://localhost:5001](http://localhost:5001).

### Running tests

```bash
pytest

# Run a single test file
pytest tests/test_backend_connection.py
```

## Project Structure

```
app.py               — Flask app, route definitions, request-level validation & CSRF
database/db.py        — SQLite connection, schema init, seed data, writes (create_user, add_expense, ...)
database/queries.py   — Read-side queries (summary stats, breakdowns, recent transactions)
templates/            — Jinja2 HTML templates (base.html + page templates)
static/css/           — landing.css (landing page), style.css (app pages)
static/js/main.js     — client-side JS
tests/                — pytest test suite (DB connectivity, CRUD, date filtering)
```

## Deployment

Deployed on [Render](https://render.com), running via Gunicorn per the `Procfile`:

```
web: gunicorn app:app --bind 0.0.0.0:$PORT
```
