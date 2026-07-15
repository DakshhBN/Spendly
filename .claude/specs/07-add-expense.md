# Spec: Add Expense

## Overview
Step 7 replaces the `/expenses/add` stub with a working form that lets logged-in
users record a new expense. The user fills in an amount, category, date, and
optional description, then submits. The route validates the input, inserts a row
into the `expenses` table, and redirects back to the profile page with a success
flash message. This is the first write path for expense data and makes Spendly
functional as a personal tracker.

## Depends on
- Step 1: Database setup (`expenses` table exists with `user_id`, `amount`,
  `category`, `date`, `description` columns)
- Step 3: Login / Logout (`session["user_id"]` set on login; unauthenticated
  users redirected to `/login`)
- Step 5: Backend routes (profile page is live to redirect back to after save)

## Routes
- `GET /expenses/add` — render the add-expense form — logged-in only
- `POST /expenses/add` — validate and insert the expense, then redirect — logged-in only

## Database changes
No database changes. The `expenses` table already has all required columns:
`user_id`, `amount`, `category`, `date`, `description`.

A new helper `add_expense(user_id, amount, category, date, description)` must be
added to `database/db.py` to keep SQL out of `app.py`.

## Templates
- **Create:** `templates/add_expense.html`
  - Extends `base.html`
  - Contains a form with `method="post"` and `action="/expenses/add"`
  - Fields:
    - Amount (`type="number"`, `step="0.01"`, `min="0.01"`, required) — labelled in ₹
    - Category (`<select>`, required) — options: Food, Transport, Bills, Health,
      Entertainment, Shopping, Other
    - Date (`type="date"`, required) — defaults to today's date
    - Description (`<textarea>`, optional, max 200 chars)
    - Submit button labelled "Add Expense"
  - Displays flashed error messages above the form
  - Pre-populates fields with the submitted values on validation failure so the
    user does not need to re-enter everything

## Files to change
- `app.py` — replace the `add_expense` stub with a full GET/POST handler:
  - Both methods require `session["user_id"]`; redirect to `/login` if absent
  - GET: render `add_expense.html` with today's date pre-filled
  - POST: validate input, call `add_expense(...)`, flash success, redirect to
    `/profile`; on failure, re-render the form with error messages and prior values
- `database/db.py` — add `add_expense(user_id, amount, category, date, description)`
  helper that inserts one row into `expenses`

## Files to create
- `templates/add_expense.html` — the add-expense form template

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format values into SQL
- Passwords hashed with werkzeug (existing behaviour — do not change)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Currency must always display as ₹ — never £ or $
- Amount must be validated server-side: must be a positive number greater than 0
- Category must be validated server-side: must be one of the allowed values
- Date must be validated server-side: must be a valid `YYYY-MM-DD` string (reuse
  the existing `_valid_date` helper in `app.py`)
- Description is optional — store `None` if blank
- On validation failure, re-render the form (do not redirect) with the submitted
  values pre-populated and a flash error message for each failing field
- Unauthenticated requests to both GET and POST must redirect to `/login`
- After a successful insert, redirect to `/profile` with a flash message:
  "Expense added successfully."
- The profile page already has an "Add Expense" button/link — ensure it points to
  `/expenses/add`

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login`
- [ ] Visiting `/expenses/add` while logged in renders the add-expense form
- [ ] The form has Amount (₹), Category (dropdown), Date, and Description fields
- [ ] The Date field defaults to today's date on first load
- [ ] Submitting with all valid fields inserts a row into `expenses` and redirects
  to `/profile` with the message "Expense added successfully."
- [ ] The new expense appears in the transaction list on the profile page
- [ ] Submitting with Amount left blank shows a validation error and re-renders
  the form without losing other field values
- [ ] Submitting with a negative or zero Amount shows a validation error
- [ ] Submitting with no Category selected shows a validation error
- [ ] Submitting with an invalid Date shows a validation error
- [ ] Submitting a POST request while logged out redirects to `/login` (no data
  inserted)
