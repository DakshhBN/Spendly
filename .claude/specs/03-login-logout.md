# Spec: Login and Logout

## Overview
Upgrade the stub `GET /login` route into a fully functional authentication flow and implement the `GET /logout` stub. Users can sign in with their email and password; on success a session is started and they are redirected to the profile page. Logout clears the session and redirects to the landing page. The navbar in `base.html` is updated to show context-sensitive links — "Sign in / Get started" for guests, and the user's name plus "Sign out" for authenticated users. This step unlocks all future logged-in-only features.

## Depends on
- Step 01 — Database setup (`users` table, `get_db()`)
- Step 02 — Registration (`create_user()`, password hashing in place)

## Routes
- `GET /login` — render login form; redirect to `/profile` if already logged in — public
- `POST /login` — validate credentials, start session, redirect to `/profile` — public
- `GET /logout` — clear session, redirect to `/` — safe to call as guest (just redirects)

## Database changes
No new tables or columns.

A new DB helper must be added to `database/db.py`:
- `get_user_by_email(email)` — queries `users` by email, returns the row as `sqlite3.Row`, or `None` if not found. Used by the login route before password verification.

## Templates
- **Create:** None

- **Modify:** `templates/login.html`
  - Remove the `{% if error %}` block — replace with Flask's `get_flashed_messages()` pattern (consistent with `register.html`)
  - Change the hardcoded `action="/login"` to `action="{{ url_for('login') }}"`
  - Keep all existing visual design and CSS classes unchanged

- **Modify:** `templates/base.html`
  - In `<div class="nav-links">`, add a Jinja2 `{% if session.user_id %}` branch:
    - Logged-in: show `Hi, {{ session.user_name }}` text and a "Sign out" link pointing to `url_for('logout')`
    - Guest: keep existing "Sign in" and "Get started" links

## Files to change
- `app.py` — upgrade `login()` to handle `GET` and `POST`; implement `logout()`; import `get_user_by_email`
- `database/db.py` — add `get_user_by_email(email)` helper
- `templates/login.html` — replace `{% if error %}` with flash messages; use `url_for` for form action
- `templates/base.html` — conditional nav links based on `session.user_id`

## Files to create
None.

## New dependencies
No new dependencies. Uses `werkzeug.security.check_password_hash` (already installed) and Flask's built-in `session`, `flash`, `redirect`, `url_for`.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never use f-strings in SQL
- Verify passwords with `werkzeug.security.check_password_hash` — never compare plaintext
- Use a single generic error message on failed login: "Invalid email or password" — never reveal which field was wrong
- Set `session["user_id"]` and `session["user_name"]` on successful login
- `logout()` must call `session.clear()` before redirecting
- Guard against already-logged-in users: if `session.user_id` is set on `GET /login`, redirect to `/profile`
- Use `url_for()` for every internal link — never hardcode URLs
- All templates extend `base.html`
- Use CSS variables — never hardcode hex values

## Definition of done
- [ ] `GET /login` renders the login form for guests
- [ ] `GET /login` redirects an already-logged-in user to `/profile`
- [ ] Submitting valid credentials sets `session["user_id"]` and `session["user_name"]` and redirects to `/profile`
- [ ] Submitting an unknown email shows "Invalid email or password" — no DB detail leaked
- [ ] Submitting a correct email with a wrong password shows the same generic error
- [ ] `GET /logout` clears the session and redirects to the landing page
- [ ] After logout, visiting `/login` shows the guest form (session is fully cleared)
- [ ] Navbar shows "Sign in / Get started" for guests and "Hi, \<name\> / Sign out" for logged-in users
- [ ] Flash messages in `login.html` use the same pattern as `register.html`
