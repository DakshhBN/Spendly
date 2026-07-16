# Spec: Edit Expense

## Overview
Step 8 replaces the `/expenses/<int:id>/edit` stub with a working edit flow that
lets logged-in users update an existing expense. The user clicks an Edit link on
the profile page, lands on a pre-filled form, changes any field, and submits.
The route validates input, verifies ownership of the expense, updates the row in
the `expenses` table, and redirects to the profile page with a success flash
message. This completes the read-write cycle for individual expenses and sets up
the ownership-check pattern that Step 9 (delete) will reuse.

## Depends on
- Step 1: Database setup (`expenses` table exists with all required columns)
- Step 3: Login / Logout (`session["user_id"]` set on login)
- Step 5: Backend routes (profile page is live)
- Step 7: Add Expense (form style, `CATEGORIES` constant, and `_valid_date` helper
  already exist in `app.py`)

## Routes
- `GET /expenses/<int:id>/edit` — render the edit form pre-filled with the
  expense's current values — logged-in only
- `POST /expenses/<int:id>/edit` — validate and update the expense, then redirect
  to `/profile` — logged-in only

## Database changes
No new tables or columns. Two new helpers are needed:

- `get_expense_by_id(expense_id, user_id)` in `database/db.py` — fetches the
  single expense row matching `id = expense_id AND user_id = user_id`; returns
  `None` if not found or not owned by the user (ownership check built-in)
- `update_expense(expense_id, user_id, amount, category, date, description)` in
  `database/db.py` — issues `UPDATE expenses SET ... WHERE id = ? AND user_id = ?`
  to prevent users from editing another user's expenses

`get_recent_transactions` in `database/queries.py` currently selects only
`date, description, category, amount`. It must also select `id` so the profile
template can generate Edit links per row.

## Templates
- **Create:** `templates/edit_expense.html`
  - Extends `base.html`
  - Mirrors `add_expense.html` in structure and CSS classes
  - Page title and heading read "Edit Expense" (not "Add Expense")
  - Subtitle reads "Update your transaction"
  - Form `action` points to `url_for('edit_expense', id=expense.id)`
  - All fields pre-filled with the expense's current values:
    - Amount (`type="number"`, `step="0.01"`, `min="0.01"`, required)
    - Date (`type="date"`, required)
    - Category (`<select>`, required, current category pre-selected)
    - Description (`<textarea>`, optional, max 200 chars)
  - On POST validation failure, fields keep the submitted (not original) values
  - Submit button labelled "Save Changes"
  - Cancel link goes back to `/profile`
  - Displays flashed error messages above the form

- **Modify:** `templates/profile.html`
  - Add a fifth column header "Actions" to the `<thead>` of the expense table
  - In `<tbody>`, add a `<td>` with an Edit link:
    `<a href="{{ url_for('edit_expense', id=e.id) }}" class="btn-edit">Edit</a>`
  - The Actions column and its Edit links must always be visible (not hidden behind hover)

## Files to change
- `app.py`
  - Import `get_expense_by_id` and `update_expense` from `database.db`
  - Replace the `edit_expense` stub with a full GET/POST handler:
    - Redirect to `/login` if `session["user_id"]` is absent
    - GET: call `get_expense_by_id(id, user_id)` — if `None`, flash "Expense not
      found." and redirect to `/profile`; otherwise render `edit_expense.html`
      passing the expense row and `categories=CATEGORIES`
    - POST: validate all fields using the same rules as `add_expense` (reuse
      `_valid_date`, same amount bounds, same category whitelist); on failure
      re-render `edit_expense.html` with error flashes and submitted values; on
      success call `update_expense(...)`, flash "Expense updated successfully.",
      and redirect to `/profile`
- `database/db.py` — add `get_expense_by_id` and `update_expense` helpers
- `database/queries.py` — add `id` to the `SELECT` in `get_recent_transactions`
- `templates/profile.html` — add Actions column as described above
- `templates/edit_expense.html` — new file (see Templates section)

## Files to create
- `templates/edit_expense.html` — the edit-expense form template

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format values into SQL
- Passwords hashed with werkzeug (existing behaviour — do not change)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Currency must always display as ₹ — never £ or $
- `update_expense` must include `user_id` in its `WHERE` clause (ownership
  enforced at the DB level, not just in Python)
- `get_expense_by_id` must filter by both `id` AND `user_id` — never fetch by id alone
- On GET with an unknown or unowned id: flash "Expense not found." and redirect to `/profile`
- Amount validation: positive number, max ₹1,00,00,000 (10,000,000)
- Category must be one of the `CATEGORIES` list in `app.py`
- Date must pass `_valid_date` check
- Description is optional — store `None` if blank; max 200 chars if provided
- Edit links on the profile table must be visible at all times (not hover-only)

## Definition of done
- [ ] Visiting `/expenses/<id>/edit` while logged out redirects to `/login`
- [ ] Visiting `/expenses/<id>/edit` for an id that doesn't exist or belongs to
  another user redirects to `/profile` with "Expense not found."
- [ ] Visiting `/expenses/<id>/edit` for a valid expense renders the edit form
  with all fields pre-filled with the current values
- [ ] The form shows the correct category pre-selected in the dropdown
- [ ] Submitting valid changes updates the row and redirects to `/profile` with
  "Expense updated successfully."
- [ ] The updated values are immediately visible in the profile transaction list
- [ ] Submitting with an invalid amount shows a validation error and re-renders
  the form
- [ ] Submitting with an invalid date shows a validation error and re-renders
  the form
- [ ] Submitting with an invalid category shows a validation error and re-renders
  the form
- [ ] Profile page expense table has an "Actions" column with an Edit link per row
- [ ] Edit links are visible without hovering
