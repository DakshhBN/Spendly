"""
tests/test_07_add_expense.py

Tests for the Step 7 "Add Expense" feature in Spendly.

Coverage:
1.  GET  /expenses/add while logged out       → 302 to /login
2.  GET  /expenses/add while logged in        → 200, form renders
3.  Form contains Amount (₹), Category dropdown, Date, Description fields
4.  Date field defaults to today's date on first load
5.  Valid POST → inserts row into expenses, redirects to /profile with flash
6.  New expense appears in transaction list on profile page after insert
7.  POST with blank Amount           → 200, validation error, form re-rendered
8.  POST with zero Amount            → 200, validation error, form re-rendered
9.  POST with negative Amount        → 200, validation error, form re-rendered
10. POST with non-numeric Amount     → 200, validation error, form re-rendered
11. POST with no Category selected   → 200, validation error, form re-rendered
12. POST with invalid Category value → 200, validation error, form re-rendered
13. POST with blank Date             → 200, validation error, form re-rendered
14. POST with invalid Date           → 200, validation error, form re-rendered
15. POST while logged out            → 302 to /login, no DB row inserted
16. Description is optional          → blank description succeeds; stored as None
17. No DB row inserted on validation failure
"""

import pytest
from datetime import date
from werkzeug.security import generate_password_hash
from database.db import get_db, init_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app(monkeypatch, tmp_path):
    """
    Flask app configured for testing with an isolated on-disk SQLite DB.

    Strategy:
    - Patch database.db.DB_PATH *before* any get_db() call so the test gets
      its own SQLite file in tmp_path.
    - Explicitly call init_db() after patching so the isolated file has the
      correct schema (the module-level init_db() in app.py ran against the
      real DB_PATH on first import, not our temp file).
    """
    db_file = str(tmp_path / "test_add_expense.db")
    monkeypatch.setattr("database.db.DB_PATH", db_file)
    init_db()   # create tables in the isolated temp DB

    import app as flask_app_module
    flask_app_module.app.config["TESTING"] = True
    flask_app_module.app.config["SECRET_KEY"] = "test-secret-add-expense"
    return flask_app_module.app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db_user(app):
    """
    Inserts one test user into the isolated DB that `app` already initialised
    (via `init_db()` called at import time with the monkeypatched DB_PATH).
    Depends on `app` so the DB_PATH patch is in effect when get_db() is called.
    """
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
        (
            "Test User",
            "test@spendly.com",
            generate_password_hash("testpass123"),
            "2026-07-01 00:00:00",
        ),
    )
    user_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {"user_id": user_id, "email": "test@spendly.com", "password": "testpass123"}


@pytest.fixture
def auth_client(client, db_user):
    """Test client with an active session for `db_user`."""
    with client.session_transaction() as sess:
        sess["user_id"] = db_user["user_id"]
        sess["user_name"] = "Test User"
    return client


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

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


def _get_expenses(user_id):
    """Return all expense rows for the given user as a list of sqlite3.Row objects."""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()


VALID_FORM = {
    "amount": "250.00",
    "category": "Food",
    "date": "2026-07-15",
    "description": "Groceries",
}

CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]


# ===========================================================================
# 1. Auth guard — GET
# ===========================================================================

class TestAddExpenseAuthGuard:
    """Unauthenticated requests must be redirected to /login."""

    def test_get_unauthenticated_redirects_to_login(self, client):
        r = client.get("/expenses/add")
        assert r.status_code == 302, "GET /expenses/add without auth must return 302"
        assert "/login" in r.headers["Location"], (
            "Unauthenticated GET must redirect to /login"
        )

    def test_post_unauthenticated_redirects_to_login(self, client):
        r = client.post("/expenses/add", data=VALID_FORM)
        assert r.status_code == 302, "POST /expenses/add without auth must return 302"
        assert "/login" in r.headers["Location"], (
            "Unauthenticated POST must redirect to /login"
        )

    def test_post_unauthenticated_inserts_no_db_row(self, client, db_user):
        before = _expense_count(db_user["user_id"])
        client.post("/expenses/add", data=VALID_FORM)
        after = _expense_count(db_user["user_id"])
        assert after == before, (
            "Unauthenticated POST must not insert any expense row into the DB"
        )


# ===========================================================================
# 2. GET — happy path
# ===========================================================================

class TestAddExpenseGet:
    """GET /expenses/add while authenticated."""

    def test_get_authenticated_returns_200(self, auth_client):
        r = auth_client.get("/expenses/add")
        assert r.status_code == 200, "GET /expenses/add while logged in must return 200"

    def test_get_renders_add_expense_page(self, auth_client):
        r = auth_client.get("/expenses/add")
        # The page must contain the submit button labelled "Add Expense"
        assert b"Add Expense" in r.data, (
            "Page must contain 'Add Expense' label/button text"
        )

    # -----------------------------------------------------------------------
    # 3. Form fields present
    # -----------------------------------------------------------------------

    def test_form_has_amount_field(self, auth_client):
        r = auth_client.get("/expenses/add")
        # Amount input — type="number"
        assert b'type="number"' in r.data or b"amount" in r.data, (
            "Form must contain a numeric amount input"
        )

    def test_form_amount_labelled_in_rupees(self, auth_client):
        r = auth_client.get("/expenses/add")
        assert "₹".encode() in r.data, (
            "Amount field must be labelled in Rupees (₹)"
        )

    def test_form_has_category_select(self, auth_client):
        r = auth_client.get("/expenses/add")
        assert b"<select" in r.data, "Form must contain a <select> element for Category"

    def test_form_category_options_present(self, auth_client):
        r = auth_client.get("/expenses/add")
        for cat in CATEGORIES:
            assert cat.encode() in r.data, (
                f"Category option '{cat}' must appear in the dropdown"
            )

    def test_form_has_date_field(self, auth_client):
        r = auth_client.get("/expenses/add")
        assert b'type="date"' in r.data, "Form must contain a date input of type='date'"

    def test_form_has_description_field(self, auth_client):
        r = auth_client.get("/expenses/add")
        assert b"description" in r.data or b"<textarea" in r.data, (
            "Form must contain a description field (textarea)"
        )

    def test_form_method_is_post(self, auth_client):
        r = auth_client.get("/expenses/add")
        assert b'method="post"' in r.data or b"method='post'" in r.data, (
            "Form must use method=post"
        )

    def test_form_action_is_add_expense_route(self, auth_client):
        r = auth_client.get("/expenses/add")
        assert b"/expenses/add" in r.data, (
            "Form action must be /expenses/add"
        )

    # -----------------------------------------------------------------------
    # 4. Date field defaults to today's date
    # -----------------------------------------------------------------------

    def test_date_field_defaults_to_today(self, auth_client):
        today = date.today().strftime("%Y-%m-%d")
        r = auth_client.get("/expenses/add")
        assert today.encode() in r.data, (
            f"Date field must default to today's date ({today}) on first load"
        )


# ===========================================================================
# 5 & 6. POST — happy path
# ===========================================================================

class TestAddExpensePostSuccess:
    """Valid POST inserts a DB row and redirects to /profile."""

    def test_valid_post_redirects_to_profile(self, auth_client):
        r = auth_client.post("/expenses/add", data=VALID_FORM)
        assert r.status_code == 302, "Valid POST must return 302"
        assert "/profile" in r.headers["Location"], (
            "Successful POST must redirect to /profile"
        )

    def test_valid_post_flash_message(self, auth_client):
        r = auth_client.post("/expenses/add", data=VALID_FORM, follow_redirects=True)
        assert b"Expense added successfully" in r.data, (
            "Flash message 'Expense added successfully.' must appear after valid POST"
        )

    def test_valid_post_inserts_db_row(self, auth_client, db_user):
        before = _expense_count(db_user["user_id"])
        auth_client.post("/expenses/add", data=VALID_FORM)
        after = _expense_count(db_user["user_id"])
        assert after == before + 1, (
            "A valid POST must insert exactly one new row into the expenses table"
        )

    def test_valid_post_stores_correct_amount(self, auth_client, db_user):
        auth_client.post("/expenses/add", data=VALID_FORM)
        rows = _get_expenses(db_user["user_id"])
        assert len(rows) > 0, "Expected at least one expense row after valid POST"
        assert rows[0]["amount"] == pytest.approx(250.00), (
            "Stored amount must match the submitted value"
        )

    def test_valid_post_stores_correct_category(self, auth_client, db_user):
        auth_client.post("/expenses/add", data=VALID_FORM)
        rows = _get_expenses(db_user["user_id"])
        assert rows[0]["category"] == "Food", (
            "Stored category must match the submitted value"
        )

    def test_valid_post_stores_correct_date(self, auth_client, db_user):
        auth_client.post("/expenses/add", data=VALID_FORM)
        rows = _get_expenses(db_user["user_id"])
        assert rows[0]["date"] == "2026-07-15", (
            "Stored date must match the submitted ISO date string"
        )

    def test_valid_post_stores_correct_description(self, auth_client, db_user):
        auth_client.post("/expenses/add", data=VALID_FORM)
        rows = _get_expenses(db_user["user_id"])
        assert rows[0]["description"] == "Groceries", (
            "Stored description must match the submitted value"
        )

    def test_valid_post_stores_correct_user_id(self, auth_client, db_user):
        auth_client.post("/expenses/add", data=VALID_FORM)
        rows = _get_expenses(db_user["user_id"])
        assert rows[0]["user_id"] == db_user["user_id"], (
            "Expense must be associated with the logged-in user's id"
        )

    # -----------------------------------------------------------------------
    # 6. New expense appears on the profile page
    # -----------------------------------------------------------------------

    def test_new_expense_appears_on_profile_page(self, auth_client):
        form_data = {
            "amount": "999.50",
            "category": "Shopping",
            "date": "2026-07-20",
            "description": "New jacket",
        }
        auth_client.post("/expenses/add", data=form_data)
        r = auth_client.get("/profile")
        assert r.status_code == 200, "Profile page must return 200 after adding expense"
        assert b"Shopping" in r.data, (
            "Newly added category 'Shopping' must appear on the profile page"
        )

    # -----------------------------------------------------------------------
    # Description optional — blank description succeeds
    # -----------------------------------------------------------------------

    def test_blank_description_is_accepted(self, auth_client, db_user):
        data = {**VALID_FORM, "description": ""}
        r = auth_client.post("/expenses/add", data=data)
        assert r.status_code == 302, (
            "Omitting description must not cause a validation error"
        )
        rows = _get_expenses(db_user["user_id"])
        assert len(rows) > 0, "Expense must still be inserted when description is blank"
        # Description should be stored as None (NULL) when blank
        assert rows[0]["description"] is None, (
            "A blank description must be stored as NULL in the database"
        )

    def test_whitespace_only_description_stored_as_none(self, auth_client, db_user):
        data = {**VALID_FORM, "description": "   "}
        r = auth_client.post("/expenses/add", data=data)
        assert r.status_code == 302, (
            "Whitespace-only description must not cause a validation error"
        )
        rows = _get_expenses(db_user["user_id"])
        assert rows[0]["description"] is None, (
            "Whitespace-only description must be stored as NULL"
        )

    def test_all_valid_categories_accepted(self, auth_client, db_user):
        """Every allowed category must be accepted without a validation error."""
        for cat in CATEGORIES:
            data = {**VALID_FORM, "category": cat}
            r = auth_client.post("/expenses/add", data=data)
            assert r.status_code == 302, (
                f"Category '{cat}' must be accepted and produce a redirect"
            )


# ===========================================================================
# 7–10. POST — Amount validation errors
# ===========================================================================

class TestAddExpenseAmountValidation:
    """Server-side amount validation."""

    @pytest.mark.parametrize("bad_amount,label", [
        ("",        "blank amount"),
        ("0",       "zero amount"),
        ("-1",      "negative amount"),
        ("-0.01",   "small negative amount"),
        ("abc",     "non-numeric amount"),
        ("!@#",     "special-character amount"),
        ("0.00",    "zero as decimal"),
    ])
    def test_invalid_amount_returns_200(self, auth_client, bad_amount, label):
        data = {**VALID_FORM, "amount": bad_amount}
        r = auth_client.post("/expenses/add", data=data)
        assert r.status_code == 200, (
            f"POST with {label} must re-render the form (200), not redirect"
        )

    @pytest.mark.parametrize("bad_amount,label", [
        ("",        "blank amount"),
        ("0",       "zero amount"),
        ("-1",      "negative amount"),
        ("abc",     "non-numeric amount"),
    ])
    def test_invalid_amount_shows_error_message(self, auth_client, bad_amount, label):
        data = {**VALID_FORM, "amount": bad_amount}
        r = auth_client.post("/expenses/add", data=data)
        # Error message text specified in the spec: "Amount must be a positive number."
        assert b"Amount" in r.data or b"positive" in r.data or b"amount" in r.data.lower(), (
            f"An error message about the amount must appear for {label}"
        )

    @pytest.mark.parametrize("bad_amount", ["", "0", "-5", "abc"])
    def test_invalid_amount_inserts_no_db_row(self, auth_client, db_user, bad_amount):
        before = _expense_count(db_user["user_id"])
        auth_client.post("/expenses/add", data={**VALID_FORM, "amount": bad_amount})
        after = _expense_count(db_user["user_id"])
        assert after == before, (
            f"No DB row must be inserted when amount='{bad_amount}'"
        )


# ===========================================================================
# 11. POST — Category validation errors
# ===========================================================================

class TestAddExpenseCategoryValidation:
    """Server-side category validation."""

    @pytest.mark.parametrize("bad_category,label", [
        ("",            "empty category"),
        ("Groceries",   "non-existent category"),
        ("food",        "lowercase category (case-sensitive)"),
        ("FOOD",        "uppercase category"),
        ("<script>",    "injection-like category"),
        ("null",        "string null category"),
    ])
    def test_invalid_category_returns_200(self, auth_client, bad_category, label):
        data = {**VALID_FORM, "category": bad_category}
        r = auth_client.post("/expenses/add", data=data)
        assert r.status_code == 200, (
            f"POST with {label} must re-render the form (200), not redirect"
        )

    @pytest.mark.parametrize("bad_category", ["", "Groceries", "food"])
    def test_invalid_category_shows_error_message(self, auth_client, bad_category):
        data = {**VALID_FORM, "category": bad_category}
        r = auth_client.post("/expenses/add", data=data)
        assert b"category" in r.data.lower() or b"valid" in r.data.lower(), (
            f"An error message about the category must appear for '{bad_category}'"
        )

    @pytest.mark.parametrize("bad_category", ["", "Groceries", "food"])
    def test_invalid_category_inserts_no_db_row(self, auth_client, db_user, bad_category):
        before = _expense_count(db_user["user_id"])
        auth_client.post("/expenses/add", data={**VALID_FORM, "category": bad_category})
        after = _expense_count(db_user["user_id"])
        assert after == before, (
            f"No DB row must be inserted when category='{bad_category}'"
        )


# ===========================================================================
# 12–13. POST — Date validation errors
# ===========================================================================

class TestAddExpenseDateValidation:
    """Server-side date validation."""

    @pytest.mark.parametrize("bad_date,label", [
        ("",              "blank date"),
        ("not-a-date",    "non-date string"),
        ("15-07-2026",    "DD-MM-YYYY format"),
        ("07/15/2026",    "MM/DD/YYYY format"),
        ("2026-13-01",    "invalid month"),
        ("2026-07-32",    "invalid day"),
        ("2026-07",       "partial date without day"),
        ("yesterday",     "natural language date"),
    ])
    def test_invalid_date_returns_200(self, auth_client, bad_date, label):
        data = {**VALID_FORM, "date": bad_date}
        r = auth_client.post("/expenses/add", data=data)
        assert r.status_code == 200, (
            f"POST with {label} must re-render the form (200), not redirect"
        )

    @pytest.mark.parametrize("bad_date", ["", "not-a-date", "15-07-2026"])
    def test_invalid_date_shows_error_message(self, auth_client, bad_date):
        data = {**VALID_FORM, "date": bad_date}
        r = auth_client.post("/expenses/add", data=data)
        assert b"date" in r.data.lower() or b"valid" in r.data.lower(), (
            f"An error message about the date must appear for '{bad_date}'"
        )

    @pytest.mark.parametrize("bad_date", ["", "not-a-date", "2026-13-01"])
    def test_invalid_date_inserts_no_db_row(self, auth_client, db_user, bad_date):
        before = _expense_count(db_user["user_id"])
        auth_client.post("/expenses/add", data={**VALID_FORM, "date": bad_date})
        after = _expense_count(db_user["user_id"])
        assert after == before, (
            f"No DB row must be inserted when date='{bad_date}'"
        )


# ===========================================================================
# Multiple simultaneous validation failures
# ===========================================================================

class TestAddExpenseMultipleValidationFailures:
    """When multiple fields are invalid, all errors must be shown and no row inserted."""

    def test_all_fields_invalid_returns_200(self, auth_client):
        r = auth_client.post("/expenses/add", data={
            "amount": "-99",
            "category": "Not a category",
            "date": "not-a-date",
            "description": "some description",
        })
        assert r.status_code == 200, (
            "POST with multiple invalid fields must re-render the form (200)"
        )

    def test_all_fields_invalid_inserts_no_db_row(self, auth_client, db_user):
        before = _expense_count(db_user["user_id"])
        auth_client.post("/expenses/add", data={
            "amount": "",
            "category": "",
            "date": "",
            "description": "",
        })
        after = _expense_count(db_user["user_id"])
        assert after == before, (
            "No DB row must be inserted when all submitted fields are invalid"
        )

    def test_amount_and_date_invalid_no_db_row(self, auth_client, db_user):
        before = _expense_count(db_user["user_id"])
        auth_client.post("/expenses/add", data={
            "amount": "0",
            "category": "Food",
            "date": "bad-date",
            "description": "test",
        })
        after = _expense_count(db_user["user_id"])
        assert after == before, (
            "No DB row must be inserted when amount and date are both invalid"
        )


# ===========================================================================
# Edge cases
# ===========================================================================

class TestAddExpenseEdgeCases:
    """Edge cases including tiny valid amounts, large amounts, and SQL injection."""

    def test_minimum_valid_amount_accepted(self, auth_client, db_user):
        """0.01 is the minimum valid amount per the spec (min="0.01")."""
        data = {**VALID_FORM, "amount": "0.01"}
        r = auth_client.post("/expenses/add", data=data)
        assert r.status_code == 302, "Amount of 0.01 must be accepted as valid"
        rows = _get_expenses(db_user["user_id"])
        assert rows[0]["amount"] == pytest.approx(0.01), (
            "Amount 0.01 must be stored correctly"
        )

    def test_large_amount_accepted(self, auth_client, db_user):
        data = {**VALID_FORM, "amount": "999999.99"}
        r = auth_client.post("/expenses/add", data=data)
        assert r.status_code == 302, "A large but valid amount must be accepted"

    def test_sql_injection_in_description_is_safe(self, auth_client, db_user):
        """Parameterised queries must prevent SQL injection from affecting other rows."""
        data = {**VALID_FORM, "description": "'; DROP TABLE expenses; --"}
        r = auth_client.post("/expenses/add", data=data)
        assert r.status_code == 302, (
            "SQL injection in description must be handled safely and treated as valid input"
        )
        rows = _get_expenses(db_user["user_id"])
        assert len(rows) > 0, "expenses table must still exist after injection attempt"
        assert rows[0]["description"] == "'; DROP TABLE expenses; --", (
            "The description must be stored as-is (parameterised, not executed as SQL)"
        )

    def test_sql_injection_in_amount_fails_validation(self, auth_client, db_user):
        """A non-numeric amount that looks like SQL must be rejected by amount validation."""
        before = _expense_count(db_user["user_id"])
        data = {**VALID_FORM, "amount": "1; DROP TABLE expenses; --"}
        r = auth_client.post("/expenses/add", data=data)
        assert r.status_code == 200, (
            "SQL-like string in amount must fail numeric validation and re-render form"
        )
        assert _expense_count(db_user["user_id"]) == before, (
            "No DB row must be inserted when amount is a SQL injection string"
        )

    def test_very_long_description_accepted(self, auth_client, db_user):
        """Spec says max 200 chars for description; server should accept up to 200."""
        data = {**VALID_FORM, "description": "A" * 200}
        r = auth_client.post("/expenses/add", data=data)
        assert r.status_code == 302, (
            "A 200-character description must be accepted (at or under the max)"
        )

    def test_multiple_expenses_stored_independently(self, auth_client, db_user):
        """Each POST creates exactly one independent row."""
        for i in range(3):
            data = {**VALID_FORM, "amount": str(100 + i), "description": f"Expense {i}"}
            auth_client.post("/expenses/add", data=data)
        assert _expense_count(db_user["user_id"]) == 3, (
            "Three separate POSTs must create three independent expense rows"
        )

    def test_expense_linked_to_correct_user(self, client):
        """Expense must be associated with the currently logged-in user, not another user."""
        # client depends on `app`, so DB_PATH is already monkeypatched.
        # Create a second user in the same isolated DB and log in as them.
        conn = get_db()
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            ("Other User", "other@spendly.com", generate_password_hash("otherpass"), "2026-07-01 00:00:00"),
        )
        other_id = cur.lastrowid
        conn.commit()
        conn.close()

        with client.session_transaction() as sess:
            sess["user_id"] = other_id
            sess["user_name"] = "Other User"

        client.post("/expenses/add", data=VALID_FORM)
        rows = _get_expenses(other_id)
        assert len(rows) == 1, "One expense must be stored for Other User"
        assert rows[0]["user_id"] == other_id, (
            "The expense must be associated with the currently logged-in user's ID"
        )
