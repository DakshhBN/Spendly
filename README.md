# Spendly

A simple personal expense tracker built with Flask. Track spending in Indian Rupees (₹) across categories, with summaries and a recent-transactions view.

**Live demo:** [https://spendly-ln3t.onrender.com/](https://spendly-ln3t.onrender.com/)

## Features

- User registration and login (password hashing via Werkzeug)
- Add, edit, and delete expenses
- Categorize spending (Food, Transport, Bills, Health, Entertainment, Shopping, Other)
- Summary stats and category breakdown, filterable by date range
- CSRF protection on state-changing forms

## Tech Stack

- **Backend:** Python / Flask
- **Templates:** Jinja2
- **Database:** SQLite
- **Frontend:** Vanilla CSS + JS

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
app.py              — Flask app and all route definitions
database/db.py       — SQLite connection, schema init, and seed data
database/queries.py  — Read queries (summary stats, breakdowns, etc.)
templates/           — Jinja2 HTML templates (base.html + page templates)
static/css/          — landing.css (landing page), style.css (app pages)
static/js/main.js    — client-side JS
tests/               — pytest test suite
```

## Deployment

Includes a `Procfile` for deployment on platforms like Railway or Heroku, running via Gunicorn:

```
web: gunicorn app:app --bind 0.0.0.0:$PORT
```
