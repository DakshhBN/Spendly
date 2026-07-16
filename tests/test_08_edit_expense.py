"""
tests/test_08_edit_expense.py

Tests for the Step 8 "Edit Expense" feature in Spendly.

Coverage (all derived from the spec's Definition of Done):
1.  GET  /expenses/<id>/edit while logged out           -> 302 to /login
2.  POST /expenses/<id>/edit while logged out           -> 302 to /login, no DB change
3.  GET  /expenses/9999/edit (non-existent id)          -> 302 to /profile, flash "Expense not found."
4.  GET  /expenses/<id>/edit for another user's expense -> 302 to /profile, flash "Expense not found."
5.  POST /expenses/<id>/edit for another user's expense -> 302 to /profile, flash "Expense not found.", no DB change
6.  GET  /expenses/<id>/edit (valid, own expense)       -> 200, form pre-filled with current values
7.  GET  form title/heading is "Edit Expense", button labelled "Save Changes"
8.  GET  form has a cancel link pointing to /profile
9.  POST valid data                                     -> DB row updated, 302 to /profile, flash "Expense updated successfully."
10. POST valid data — DB side effects verified (all fields updated correctly)
11. POST amount=-5   (negative)                         -> 200, no DB change, flash shown
12. POST amount=0    (zero)                             -> 200, no DB change
13. POST amount=10000001 (too large)                    -> 200, no DB change
14. POST category="Invalid" (not in CATEGORIES)         -> 200, no DB change
15. POST date="not-a-date"                              -> 200, no DB change
16. POST description of 201 chars                       -> 200, no DB change
17. Profile page has "Actions" column header and an Edit link per expense row
"""

import pytest
from werkzeug.security import generate_password_hash
from database.db import get_db, init_db


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]

# A pre-seeded expense for the primary test user
SEED_EXPENSE = {
    "amount": 500.0,
    "category": "Food",
    "date": "2026-07-10",
    "description": "Original description",
}

# Valid form data used for successful edit submissions
VALID_EDIT_FORM = {
    "amount": "750.50",
    "category": "Health",
    "date": "2026-08-01",
    "description": "Updated description",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app(monkeypatch, tmp_path):
    """
    Flask app configured for testing with an isolated on-disk SQLite DB.

    DB_PATH is monkeypatched before any get_db() call so the test gets its
    own SQLite file under tmp_path. init_db() is then called explicitly to
    create the schema in that isolated file.
    """
    db_file = str(tmp_path / "test_edit_expense.db")
    monkeypatch.setattr("database.db.DB_PATH", db_file)
    init_db()

    import app as flask_app_module
    flask_app_module.app.config["TESTING"] = True
    flask_app_module.app.config["SECRET_KEY"] = "test-secret-edit-expense"
    return flask_app_module.app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db_users(app):
    """
    Inserts two users into the isolated DB:
    - primary_user: owns the seeded test expense
    - other_user:   used to test ownership enforcement

    Returns a dict with both users' IDs and the seeded expense ID.
    """
    conn = get_db()

    cur = conn.execute(
        "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
        (
            "Primary User",
            "primary@spendly.com",
            generate_password_hash("primarypass123"),
            "2026-07-01 00:00:00",
        ),
    )
    primary_id = cur.lastrowid

    cur2 = conn.execute(
        "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
        (
            "Other User",
            "other@spendly.com",
            generate_password_hash("otherpass123"),
            "2026-07-01 00:00:00",
        ),
    )
    other_id = cur2.lastrowid

    # Seed one expense for the primary user
    cur3 = conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description)"
        " VALUES (?, ?, ?, ?, ?)",
        (
            primary_id,
            SEED_EXPENSE["amount"],
            SEED_EXPENSE["category"],
            SEED_EXPENSE["date"],
            SEED_EXPENSE["description"],
        ),
    )
    expense_id = cur3.lastrowid

    # Seed one expense for the other user so we can probe ownership enforcement
    cur4 = conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description)"
        " VALUES (?, ?, ?, ?, ?)",
        (other_id, 100.0, "Transport", "2026-07-05", "Other user's expense"),
    )
    other_expense_id = cur4.lastrowid

    conn.commit()
    conn.close()

    return {
        "primary_id": primary_id,
        "other_id": other_id,
        "expense_id": expense_id,
        "other_expense_id": other_expense_id,
    }


@pytest.fixture
def auth_client(client, db_users):
    """Test client with an active session for the primary user."""
    with client.session_transaction() as sess:
        sess["user_id"] = db_users["primary_id"]
        sess["user_name"] = "Primary User"
    return client


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _get_expense(expense_id):
    """Fetch a single expense row from the DB by its id."""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
    finally:
        conn.close()


def _expense_count(user_id):
    """Return the number of expense rows in the DB for the given user."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row[0]
    finally:
        conn.close()


# ===========================================================================
# 1–2. Auth guard
# ===========================================================================

class TestEditExpenseAuthGuard:
    """Unauthenticated requests must be redirected to /login."""

    def test_get_unauthenticated_redirects_to_login(self, client, db_users):
        expense_id = db_users["expense_id"]
        r = client.get(f"/expenses/{expense_id}/edit")
        assert r.status_code == 302, (
            "GET /expenses/<id>/edit without auth must return 302"
        )
        assert "/login" in r.headers["Location"], (
            "Unauthenticated GET must redirect to /login"
        )

    def test_post_unauthenticated_redirects_to_login(self, client, db_users):
        expense_id = db_users["expense_id"]
        r = client.post(f"/expenses/{expense_id}/edit", data=VALID_EDIT_FORM)
        assert r.status_code == 302, (
            "POST /expenses/<id>/edit without auth must return 302"
        )
        assert "/login" in r.headers["Location"], (
            "Unauthenticated POST must redirect to /login"
        )

    def test_post_unauthenticated_does_not_change_db(self, client, db_users):
        expense_id = db_users["expense_id"]
        before = _get_expense(expense_id)
        client.post(f"/expenses/{expense_id}/edit", data=VALID_EDIT_FORM)
        after = _get_expense(expense_id)
        assert after["amount"] == before["amount"], (
            "Unauthenticated POST must not update the expense amount in the DB"
        )
        assert after["category"] == before["category"], (
            "Unauthenticated POST must not update the expense category in the DB"
        )


# ===========================================================================
# 3–5. Not found / ownership guard
# ===========================================================================

class TestEditExpenseNotFound:
    """Requests for non-existent or unowned expenses must be rejected."""

    def test_get_nonexistent_id_redirects_to_profile(self, auth_client):
        r = auth_client.get("/expenses/9999/edit")
        assert r.status_code == 302, (
            "GET for a non-existent expense id must return 302"
        )
        assert "/profile" in r.headers["Location"], (
            "GET for a non-existent id must redirect to /profile"
        )

    def test_get_nonexistent_id_flashes_not_found(self, auth_client):
        r = auth_client.get("/expenses/9999/edit", follow_redirects=True)
        assert b"Expense not found." in r.data, (
            "Flash message 'Expense not found.' must appear for a non-existent id"
        )

    def test_get_other_users_expense_redirects_to_profile(self, auth_client, db_users):
        """A valid expense that belongs to a different user must not be accessible."""
        other_expense_id = db_users["other_expense_id"]
        r = auth_client.get(f"/expenses/{other_expense_id}/edit")
        assert r.status_code == 302, (
            "GET for another user's expense must return 302"
        )
        assert "/profile" in r.headers["Location"], (
            "GET for another user's expense must redirect to /profile"
        )

    def test_get_other_users_expense_flashes_not_found(self, auth_client, db_users):
        other_expense_id = db_users["other_expense_id"]
        r = auth_client.get(
            f"/expenses/{other_expense_id}/edit", follow_redirects=True
        )
        assert b"Expense not found." in r.data, (
            "Flash message 'Expense not found.' must appear when accessing another user's expense"
        )

    def test_post_other_users_expense_redirects_to_profile(self, auth_client, db_users):
        other_expense_id = db_users["other_expense_id"]
        r = auth_client.post(
            f"/expenses/{other_expense_id}/edit", data=VALID_EDIT_FORM
        )
        assert r.status_code == 302, (
            "POST for another user's expense must return 302"
        )
        assert "/profile" in r.headers["Location"], (
            "POST for another user's expense must redirect to /profile"
        )

    def test_post_other_users_expense_does_not_change_db(self, auth_client, db_users):
        other_expense_id = db_users["other_expense_id"]
        before = _get_expense(other_expense_id)
        auth_client.post(
            f"/expenses/{other_expense_id}/edit", data=VALID_EDIT_FORM
        )
        after = _get_expense(other_expense_id)
        assert after["amount"] == before["amount"], (
            "POST for another user's expense must not update that row's amount"
        )
        assert after["category"] == before["category"], (
            "POST for another user's expense must not update that row's category"
        )


# ===========================================================================
# 6–8. Happy path GET — form pre-filled with current values
# ===========================================================================

class TestEditExpenseGet:
    """GET /expenses/<id>/edit while authenticated and the expense is owned."""

    def test_get_valid_expense_returns_200(self, auth_client, db_users):
        expense_id = db_users["expense_id"]
        r = auth_client.get(f"/expenses/{expense_id}/edit")
        assert r.status_code == 200, (
            "GET /expenses/<id>/edit for a valid owned expense must return 200"
        )

    def test_get_form_contains_current_amount(self, auth_client, db_users):
        expense_id = db_users["expense_id"]
        r = auth_client.get(f"/expenses/{expense_id}/edit")
        # The seeded amount is 500.0; check for "500" in the rendered HTML
        assert b"500" in r.data, (
            "Edit form must show the current expense amount pre-filled"
        )

    def test_get_form_contains_current_date(self, auth_client, db_users):
        expense_id = db_users["expense_id"]
        r = auth_client.get(f"/expenses/{expense_id}/edit")
        assert SEED_EXPENSE["date"].encode() in r.data, (
            "Edit form must show the current expense date pre-filled"
        )

    def test_get_form_contains_current_category_selected(self, auth_client, db_users):
        expense_id = db_users["expense_id"]
        r = auth_client.get(f"/expenses/{expense_id}/edit")
        # The seeded category is "Food" — it should appear in the response
        assert b"Food" in r.data, (
            "Edit form must pre-select the current expense category"
        )

    def test_get_form_contains_current_description(self, auth_client, db_users):
        expense_id = db_users["expense_id"]
        r = auth_client.get(f"/expenses/{expense_id}/edit")
        assert SEED_EXPENSE["description"].encode() in r.data, (
            "Edit form must show the current expense description pre-filled"
        )

    def test_get_page_title_is_edit_expense(self, auth_client, db_users):
        expense_id = db_users["expense_id"]
        r = auth_client.get(f"/expenses/{expense_id}/edit")
        assert b"Edit Expense" in r.data, (
            "Page heading or title must read 'Edit Expense'"
        )

    def test_get_submit_button_labelled_save_changes(self, auth_client, db_users):
        expense_id = db_users["expense_id"]
        r = auth_client.get(f"/expenses/{expense_id}/edit")
        assert b"Save Changes" in r.data, (
            "Submit button must be labelled 'Save Changes'"
        )

    def test_get_cancel_link_points_to_profile(self, auth_client, db_users):
        expense_id = db_users["expense_id"]
        r = auth_client.get(f"/expenses/{expense_id}/edit")
        assert b"/profile" in r.data, (
            "Edit form must contain a cancel link pointing back to /profile"
        )

    def test_get_form_action_points_to_edit_route(self, auth_client, db_users):
        expense_id = db_users["expense_id"]
        r = auth_client.get(f"/expenses/{expense_id}/edit")
        expected_action = f"/expenses/{expense_id}/edit".encode()
        assert expected_action in r.data, (
            "Form action must point to the edit expense route for the correct expense id"
        )

    def test_get_form_has_category_dropdown(self, auth_client, db_users):
        expense_id = db_users["expense_id"]
        r = auth_client.get(f"/expenses/{expense_id}/edit")
        assert b"<select" in r.data, (
            "Edit form must contain a <select> element for Category"
        )

    def test_get_form_all_category_options_present(self, auth_client, db_users):
        expense_id = db_users["expense_id"]
        r = auth_client.get(f"/expenses/{expense_id}/edit")
        for cat in CATEGORIES:
            assert cat.encode() in r.data, (
                f"Category option '{cat}' must appear in the edit form dropdown"
            )

    def test_get_form_has_date_input(self, auth_client, db_users):
        expense_id = db_users["expense_id"]
        r = auth_client.get(f"/expenses/{expense_id}/edit")
        assert b'type="date"' in r.data, (
            "Edit form must contain a date input of type='date'"
        )

    def test_get_form_amount_uses_rupee_currency(self, auth_client, db_users):
        expense_id = db_users["expense_id"]
        r = auth_client.get(f"/expenses/{expense_id}/edit")
        assert "₹".encode() in r.data, (
            "Edit form must reference the Rupee symbol (₹) for the amount field"
        )


# ===========================================================================
# 9–10. Happy path POST — DB updated, redirect, flash message
# ===========================================================================

class TestEditExpensePostSuccess:
    """Valid POST updates the DB row and redirects to /profile with a flash."""

    def test_valid_post_redirects_to_profile(self, auth_client, db_users):
        expense_id = db_users["expense_id"]
        r = auth_client.post(f"/expenses/{expense_id}/edit", data=VALID_EDIT_FORM)
        assert r.status_code == 302, "Valid POST must return 302"
        assert "/profile" in r.headers["Location"], (
            "Successful POST must redirect to /profile"
        )

    def test_valid_post_shows_success_flash(self, auth_client, db_users):
        expense_id = db_users["expense_id"]
        r = auth_client.post(
            f"/expenses/{expense_id}/edit",
            data=VALID_EDIT_FORM,
            follow_redirects=True,
        )
        assert b"Expense updated successfully." in r.data, (
            "Flash message 'Expense updated successfully.' must appear after a valid POST"
        )

    def test_valid_post_updates_amount_in_db(self, auth_client, db_users):
        expense_id = db_users["expense_id"]
        auth_client.post(f"/expenses/{expense_id}/edit", data=VALID_EDIT_FORM)
        row = _get_expense(expense_id)
        assert row["amount"] == pytest.approx(750.50), (
            "Updated amount must be persisted correctly in the DB"
        )

    def test_valid_post_updates_category_in_db(self, auth_client, db_users):
        expense_id = db_users["expense_id"]
        auth_client.post(f"/expenses/{expense_id}/edit", data=VALID_EDIT_FORM)
        row = _get_expense(expense_id)
        assert row["category"] == "Health", (
            "Updated category must be persisted correctly in the DB"
        )

    def test_valid_post_updates_date_in_db(self, auth_client, db_users):
        expense_id = db_users["expense_id"]
        auth_client.post(f"/expenses/{expense_id}/edit", data=VALID_EDIT_FORM)
        row = _get_expense(expense_id)
        assert row["date"] == "2026-08-01", (
            "Updated date must be persisted correctly in the DB"
        )

    def test_valid_post_updates_description_in_db(self, auth_client, db_users):
        expense_id = db_users["expense_id"]
        auth_client.post(f"/expenses/{expense_id}/edit", data=VALID_EDIT_FORM)
        row = _get_expense(expense_id)
        assert row["description"] == "Updated description", (
            "Updated description must be persisted correctly in the DB"
        )

    def test_valid_post_updates_only_target_row(self, auth_client, db_users):
        """Editing one expense must not affect the other user's expense row."""
        expense_id = db_users["expense_id"]
        other_expense_id = db_users["other_expense_id"]
        before_other = _get_expense(other_expense_id)
        auth_client.post(f"/expenses/{expense_id}/edit", data=VALID_EDIT_FORM)
        after_other = _get_expense(other_expense_id)
        assert after_other["amount"] == before_other["amount"], (
            "Editing one expense must not modify other users' expense rows"
        )

    def test_valid_post_blank_description_stored_as_none(self, auth_client, db_users):
        """Submitting a blank description must store NULL in the DB."""
        expense_id = db_users["expense_id"]
        data = {**VALID_EDIT_FORM, "description": ""}
        auth_client.post(f"/expenses/{expense_id}/edit", data=data)
        row = _get_expense(expense_id)
        assert row["description"] is None, (
            "A blank description on edit must be stored as NULL in the DB"
        )

    def test_valid_post_blank_description_still_redirects(self, auth_client, db_users):
        """A blank description is optional and must not block a successful edit."""
        expense_id = db_users["expense_id"]
        data = {**VALID_EDIT_FORM, "description": ""}
        r = auth_client.post(f"/expenses/{expense_id}/edit", data=data)
        assert r.status_code == 302, (
            "Blank description must not prevent a successful edit redirect"
        )

    def test_valid_post_updated_values_appear_on_profile(self, auth_client, db_users):
        """After a successful edit the new category must be visible on the profile page."""
        expense_id = db_users["expense_id"]
        auth_client.post(f"/expenses/{expense_id}/edit", data=VALID_EDIT_FORM)
        r = auth_client.get("/profile")
        assert b"Health" in r.data, (
            "The updated category 'Health' must appear on the profile page after a successful edit"
        )

    def test_all_valid_categories_accepted_on_edit(self, auth_client, db_users):
        """Every allowed category must be accepted by the edit route."""
        for cat in CATEGORIES:
            # Re-seed the expense back to its original state each iteration
            conn = get_db()
            conn.execute(
                "UPDATE expenses SET amount=?, category=?, date=?, description=?"
                " WHERE id=?",
                (
                    SEED_EXPENSE["amount"],
                    SEED_EXPENSE["category"],
                    SEED_EXPENSE["date"],
                    SEED_EXPENSE["description"],
                    db_users["expense_id"],
                ),
            )
            conn.commit()
            conn.close()

            data = {**VALID_EDIT_FORM, "category": cat}
            r = auth_client.post(
                f"/expenses/{db_users['expense_id']}/edit", data=data
            )
            assert r.status_code == 302, (
                f"Category '{cat}' must be accepted in an edit POST and produce a redirect"
            )


# ===========================================================================
# 11–16. Validation failures — form re-renders, no DB change
# ===========================================================================

class TestEditExpenseValidation:
    """Invalid POST submissions must re-render the form and leave the DB unchanged."""

    # ---- Amount validation -------------------------------------------------

    @pytest.mark.parametrize("bad_amount,label", [
        ("-5",          "negative amount"),
        ("-0.01",       "small negative amount"),
        ("0",           "zero amount"),
        ("0.00",        "zero as decimal"),
        ("10000001",    "amount exceeding 10,000,000"),
        ("10000000.01", "amount just over the maximum"),
        ("",            "blank amount"),
        ("abc",         "non-numeric string"),
    ])
    def test_invalid_amount_returns_200(self, auth_client, db_users, bad_amount, label):
        expense_id = db_users["expense_id"]
        data = {**VALID_EDIT_FORM, "amount": bad_amount}
        r = auth_client.post(f"/expenses/{expense_id}/edit", data=data)
        assert r.status_code == 200, (
            f"POST with {label} must re-render the form (200), not redirect"
        )

    @pytest.mark.parametrize("bad_amount", ["-5", "0", "10000001", "", "abc"])
    def test_invalid_amount_does_not_change_db(self, auth_client, db_users, bad_amount):
        expense_id = db_users["expense_id"]
        before = _get_expense(expense_id)
        auth_client.post(
            f"/expenses/{expense_id}/edit",
            data={**VALID_EDIT_FORM, "amount": bad_amount},
        )
        after = _get_expense(expense_id)
        assert after["amount"] == before["amount"], (
            f"No DB change expected when amount='{bad_amount}'"
        )

    @pytest.mark.parametrize("bad_amount", ["-5", "0", "10000001", "abc"])
    def test_invalid_amount_shows_error_message(self, auth_client, db_users, bad_amount):
        expense_id = db_users["expense_id"]
        data = {**VALID_EDIT_FORM, "amount": bad_amount}
        r = auth_client.post(f"/expenses/{expense_id}/edit", data=data)
        assert b"Amount" in r.data or b"amount" in r.data.lower() or b"positive" in r.data, (
            f"An error message about the amount must appear in the response for amount='{bad_amount}'"
        )

    # ---- Category validation -----------------------------------------------

    @pytest.mark.parametrize("bad_category,label", [
        ("Invalid",     "non-existent category"),
        ("",            "empty category"),
        ("food",        "lowercase (case-sensitive)"),
        ("FOOD",        "uppercase"),
        ("<script>",    "injection-like value"),
    ])
    def test_invalid_category_returns_200(self, auth_client, db_users, bad_category, label):
        expense_id = db_users["expense_id"]
        data = {**VALID_EDIT_FORM, "category": bad_category}
        r = auth_client.post(f"/expenses/{expense_id}/edit", data=data)
        assert r.status_code == 200, (
            f"POST with {label} must re-render the form (200), not redirect"
        )

    @pytest.mark.parametrize("bad_category", ["Invalid", "", "food"])
    def test_invalid_category_does_not_change_db(self, auth_client, db_users, bad_category):
        expense_id = db_users["expense_id"]
        before = _get_expense(expense_id)
        auth_client.post(
            f"/expenses/{expense_id}/edit",
            data={**VALID_EDIT_FORM, "category": bad_category},
        )
        after = _get_expense(expense_id)
        assert after["category"] == before["category"], (
            f"No DB change expected when category='{bad_category}'"
        )

    # ---- Date validation ---------------------------------------------------

    @pytest.mark.parametrize("bad_date,label", [
        ("not-a-date",  "non-date string"),
        ("",            "blank date"),
        ("15-07-2026",  "DD-MM-YYYY format"),
        ("07/15/2026",  "MM/DD/YYYY format"),
        ("2026-13-01",  "invalid month"),
        ("2026-07-32",  "invalid day"),
        ("yesterday",   "natural language date"),
    ])
    def test_invalid_date_returns_200(self, auth_client, db_users, bad_date, label):
        expense_id = db_users["expense_id"]
        data = {**VALID_EDIT_FORM, "date": bad_date}
        r = auth_client.post(f"/expenses/{expense_id}/edit", data=data)
        assert r.status_code == 200, (
            f"POST with {label} must re-render the form (200), not redirect"
        )

    @pytest.mark.parametrize("bad_date", ["not-a-date", "", "2026-13-01"])
    def test_invalid_date_does_not_change_db(self, auth_client, db_users, bad_date):
        expense_id = db_users["expense_id"]
        before = _get_expense(expense_id)
        auth_client.post(
            f"/expenses/{expense_id}/edit",
            data={**VALID_EDIT_FORM, "date": bad_date},
        )
        after = _get_expense(expense_id)
        assert after["date"] == before["date"], (
            f"No DB change expected when date='{bad_date}'"
        )

    # ---- Description validation --------------------------------------------

    def test_description_201_chars_returns_200(self, auth_client, db_users):
        """Description longer than 200 chars must be rejected."""
        expense_id = db_users["expense_id"]
        data = {**VALID_EDIT_FORM, "description": "X" * 201}
        r = auth_client.post(f"/expenses/{expense_id}/edit", data=data)
        assert r.status_code == 200, (
            "POST with a 201-character description must re-render the form (200)"
        )

    def test_description_201_chars_does_not_change_db(self, auth_client, db_users):
        expense_id = db_users["expense_id"]
        before = _get_expense(expense_id)
        auth_client.post(
            f"/expenses/{expense_id}/edit",
            data={**VALID_EDIT_FORM, "description": "X" * 201},
        )
        after = _get_expense(expense_id)
        assert after["description"] == before["description"], (
            "No DB change expected when description exceeds 200 characters"
        )

    def test_description_exactly_200_chars_is_accepted(self, auth_client, db_users):
        """Exactly 200 characters is the boundary — must be accepted."""
        expense_id = db_users["expense_id"]
        data = {**VALID_EDIT_FORM, "description": "A" * 200}
        r = auth_client.post(f"/expenses/{expense_id}/edit", data=data)
        assert r.status_code == 302, (
            "A 200-character description is at the limit and must be accepted"
        )


# ===========================================================================
# 17. Profile page — Actions column and Edit links
# ===========================================================================

class TestProfileActionsColumn:
    """Profile page must have an 'Actions' column with per-row Edit links."""

    def test_profile_has_actions_column_header(self, auth_client, db_users):
        r = auth_client.get("/profile")
        assert r.status_code == 200, "Profile page must return 200"
        assert b"Actions" in r.data, (
            "Profile expense table must have an 'Actions' column header"
        )

    def test_profile_has_edit_link_for_own_expense(self, auth_client, db_users):
        expense_id = db_users["expense_id"]
        r = auth_client.get("/profile")
        expected_href = f"/expenses/{expense_id}/edit".encode()
        assert expected_href in r.data, (
            f"Profile page must contain an Edit link pointing to /expenses/{expense_id}/edit"
        )

    def test_profile_edit_link_has_edit_text(self, auth_client, db_users):
        r = auth_client.get("/profile")
        assert b"Edit" in r.data, (
            "Profile page Edit link must contain the text 'Edit'"
        )


# ===========================================================================
# Edge cases
# ===========================================================================

class TestEditExpenseEdgeCases:
    """Edge cases: boundary amounts, SQL injection, large but valid amounts."""

    def test_minimum_valid_amount_accepted(self, auth_client, db_users):
        """0.01 is the minimum valid amount; must be accepted on edit."""
        expense_id = db_users["expense_id"]
        data = {**VALID_EDIT_FORM, "amount": "0.01"}
        r = auth_client.post(f"/expenses/{expense_id}/edit", data=data)
        assert r.status_code == 302, "Amount of 0.01 must be accepted as valid on edit"
        row = _get_expense(expense_id)
        assert row["amount"] == pytest.approx(0.01), (
            "Amount 0.01 must be stored correctly after edit"
        )

    def test_maximum_valid_amount_accepted(self, auth_client, db_users):
        """10,000,000 is the stated maximum; must be accepted on edit."""
        expense_id = db_users["expense_id"]
        data = {**VALID_EDIT_FORM, "amount": "10000000"}
        r = auth_client.post(f"/expenses/{expense_id}/edit", data=data)
        assert r.status_code == 302, "Amount of 10,000,000 (the maximum) must be accepted"

    def test_sql_injection_in_description_stored_safely(self, auth_client, db_users):
        """Parameterised queries must store injection strings literally, not execute them."""
        expense_id = db_users["expense_id"]
        injection = "'; DROP TABLE expenses; --"
        data = {**VALID_EDIT_FORM, "description": injection}
        r = auth_client.post(f"/expenses/{expense_id}/edit", data=data)
        assert r.status_code == 302, (
            "SQL injection string in description must be treated as valid text"
        )
        row = _get_expense(expense_id)
        assert row is not None, "expenses table must still exist after injection attempt"
        assert row["description"] == injection, (
            "The description must be stored as-is (parameterised, not executed as SQL)"
        )

    def test_sql_injection_in_amount_fails_validation(self, auth_client, db_users):
        """A non-numeric injection string in amount must be rejected by validation."""
        expense_id = db_users["expense_id"]
        before = _get_expense(expense_id)
        data = {**VALID_EDIT_FORM, "amount": "1; DROP TABLE expenses; --"}
        r = auth_client.post(f"/expenses/{expense_id}/edit", data=data)
        assert r.status_code == 200, (
            "SQL-like string in amount must fail numeric validation and re-render form"
        )
        after = _get_expense(expense_id)
        assert after["amount"] == before["amount"], (
            "No DB change expected when amount is a SQL injection string"
        )

    def test_user_id_not_changeable_via_form(self, client, db_users):
        """
        A malicious POST that includes a spoofed user_id field must not
        allow the primary user to edit the other user's expense.
        The route reads user_id exclusively from the server-side session.
        """
        primary_id = db_users["primary_id"]
        other_expense_id = db_users["other_expense_id"]

        # Log in as the primary user
        with client.session_transaction() as sess:
            sess["user_id"] = primary_id
            sess["user_name"] = "Primary User"

        before = _get_expense(other_expense_id)
        # Attempt to edit the other user's expense, also sending user_id in POST data
        data = {**VALID_EDIT_FORM, "user_id": db_users["other_id"]}
        r = client.post(f"/expenses/{other_expense_id}/edit", data=data)
        after = _get_expense(other_expense_id)

        # Ownership check must prevent the update regardless of form fields
        assert after["amount"] == before["amount"], (
            "Submitting a spoofed user_id in POST data must not allow editing another user's expense"
        )
