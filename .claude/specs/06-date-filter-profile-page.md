# Spec: Date Filter for Profile Page

## Overview
Step 6 adds a date-range filter to the profile page so users can slice their
expense data by a custom time window. Currently, the summary stats, transaction
list, and category breakdown always show all-time totals. This step wires two
date inputs ("From" / "To") into the existing query helpers so that all three
data sections update in sync when the user applies a filter. The filter is
expressed as GET query parameters (`?from=YYYY-MM-DD&to=YYYY-MM-DD`), making
filtered views bookmarkable and shareable.

## Depends on
- Step 1: Database setup (`expenses` table with `date` column exists)
- Step 3: Login / Logout (`session["user_id"]` set on login)
- Step 5: Backend routes (live data flowing through `get_summary_stats`,
  `get_recent_transactions`, `get_category_breakdown`)

## Routes
No new routes. `GET /profile` is modified to accept optional query parameters:
- `from` — start date (inclusive), format `YYYY-MM-DD`
- `to`   — end date (inclusive), format `YYYY-MM-DD`

Example: `GET /profile?from=2026-07-01&to=2026-07-15`

## Database changes
No database changes. The `expenses.date` column (`TEXT`, stored as `YYYY-MM-DD`)
already supports `BETWEEN` comparisons.

## Templates
- **Modify:** `templates/profile.html`
  - Add a date-filter form above the stats cards, containing:
    - A "From" date input (pre-populated with the current `from_date` value)
    - A "To" date input (pre-populated with the current `to_date` value)
    - An "Apply" submit button
    - A "Clear" link that navigates to `/profile` (no params) to reset the filter
  - The form must use `method="get"` and `action="/profile"` so the date params
    appear in the URL

## Files to change
- `app.py` — read `from_date` and `to_date` from `request.args` in the
  `profile()` view; pass them to the three query helpers; pass them back to the
  template context so the form can pre-populate
- `database/queries.py` — add optional `from_date=None, to_date=None` keyword
  arguments to `get_summary_stats`, `get_recent_transactions`, and
  `get_category_breakdown`; build the WHERE clause conditionally
- `templates/profile.html` — add the date-filter form (see Templates section)

## Files to create
None.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format values into SQL
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Currency must always display as ₹ — never £ or $
- Date inputs must use `type="date"` (browser-native picker)
- When `from_date` or `to_date` is absent or empty, treat it as unbounded
  (no lower or upper date constraint respectively)
- Invalid date strings (non-ISO, garbage input) must be silently ignored —
  fall back to no filter rather than raising an exception
- The filter must apply consistently to all three data sections (stats,
  transactions, category breakdown) — they must never show mismatched date ranges
- Passwords hashed with werkzeug (existing behaviour — do not change)

## Definition of done
- [ ] A date-filter form with "From" and "To" date inputs appears on the
  profile page above the stats cards
- [ ] Submitting the form with `from=2026-07-01` and `to=2026-07-10` updates
  stats, transaction list, and category breakdown to show only expenses within
  that range
- [ ] The "From" and "To" inputs are pre-populated with the currently applied
  filter values after submit
- [ ] Clicking "Clear" (or visiting `/profile` with no params) resets all
  sections to all-time data
- [ ] Applying only a "From" date (no "To") shows all expenses from that date
  forward
- [ ] Applying only a "To" date (no "From") shows all expenses up to that date
- [ ] A date range with no matching expenses shows ₹0 total spent, 0
  transactions, "—" top category, empty transaction list, and empty category
  breakdown — no errors or exceptions
- [ ] The URL reflects the applied filter (`/profile?from=...&to=...`) so the
  filtered view can be bookmarked
