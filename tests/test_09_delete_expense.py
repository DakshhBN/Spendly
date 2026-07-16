"""
tests/test_09_delete_expense.py

Tests for the Spendly Step 9 "Delete Expense" feature.

Spec: .claude/specs/09-delete-expense-profile-page.md

Coverage (all derived from the spec's Definition of Done and the route/unit
test table in the spec):

Unit tests — delete_expense() helper:
  1.  delete_expense with valid expense_id and correct user_id removes the row
  2.  delete_expense with valid expense_id but wrong user_id leaves the row intact
  3.  delete_expense with a non-existent expense_id raises no error, DB unchanged

Route tests — POST /expenses/<id>/delete:
  4.  Unauthenticated POST -> 302 to /login
  5.  Unauthenticated POST -> DB row untouched
  6.  Authenticated POST, own expense -> 302 to /profile
  7.  Authenticated POST, own expense -> row removed from DB
  8.  Authenticated POST, own expense -> flash "Expense deleted." visible on profile
  9.  Authenticated POST, own expense -> expense no longer appears in profile transaction list
  10. Authenticated POST, other user's expense -> 404
  11. Authenticated POST, other user's expense -> row still in DB
  12. Authenticated POST, non-existent id -> 404

HTTP method guard:
  13. GET /expenses/<id>/delete -> 405

Profile template:
  14. Actions column header present
  15. Delete button present per expense row
  16. Delete form action points to the correct /expenses/<id>/delete URL
  17. Delete form uses method="post"
  18. Both Edit and Delete actions appear on each row

Security / edge cases:
  19. Spoofed user_id in POST body cannot delete another user's expense
  20. Non-integer path segment /expenses/abc/delete -> 404 (Flask type converter)
"""

import pytest
from werkzeug.security import generate_password_hash
from database.db import get_db, init_db
from database.queries import delete_expense


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Seed expense owned by the primary test user
SEED_EXPENSE = {
    "amount": 750.0,
    "category": "Food",
    "date": "2026-07-10",
    "description": "Test grocery run",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app(monkeypatch, tmp_path):
    """
    Flask app configured for testing with an isolated on-disk SQLite DB.

    DB_PATH is monkeypatched before any get_db() call so each test module
    gets its own SQLite file under pytest's tmp_path. init_db() creates the
    schema in that isolated file.
    """
    db_file = str(tmp_path / "test_delete_expense.db")
    monkeypatch.setattr("database.db.DB_PATH", db_file)
    init_db()

    import app as flask_app_module
    flask_app_module.app.config["TESTING"] = True
    flask_app_module.app.config["SECRET_KEY"] = "test-secret-delete-expense"
    return flask_app_module.app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db_users(app):
    """
    Inserts two users into the isolated DB and seeds one expense per user.

    Returns a dict with:
      - primary_id:       user who owns the primary test expense
      - other_id:         a second user used for ownership-guard tests
      - expense_id:       the primary user's seeded expense row id
      - other_expense_id: the other user's seeded expense row id
    """
    conn = get_db()

    cur = conn.execute(
        "INSERT INTO users (name, email, password_hash, created_at)"
        " VALUES (?, ?, ?, ?)",
        (
            "Primary User",
            "primary@spendly.com",
            generate_password_hash("primarypass123"),
            "2026-07-01 00:00:00",
        ),
    )
    primary_id = cur.lastrowid

    cur2 = conn.execute(
        "INSERT INTO users (name, email, password_hash, created_at)"
        " VALUES (?, ?, ?, ?)",
        (
            "Other User",
            "other@spendly.com",
            generate_password_hash("otherpass123"),
            "2026-07-01 00:00:00",
        ),
    )
    other_id = cur2.lastrowid

    # Primary user's expense — the one we will delete in happy-path tests
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

    # Other user's expense — used to probe ownership enforcement
    cur4 = conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description)"
        " VALUES (?, ?, ?, ?, ?)",
        (other_id, 200.0, "Transport", "2026-07-05", "Other user bus fare"),
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
# Private DB helpers (raw SQL — never derived from the implementation)
# ---------------------------------------------------------------------------

def _row_exists(expense_id: int) -> bool:
    """Return True if an expense row with the given id exists in the DB."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def _get_expense_row(expense_id: int):
    """Fetch a single expense row by id (ignoring user ownership)."""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
    finally:
        conn.close()


# ===========================================================================
# Unit tests — delete_expense() query helper
# ===========================================================================

class TestDeleteExpenseUnit:
    """
    Direct unit tests for the delete_expense(expense_id, user_id) helper in
    database/queries.py.  Tests operate on the DB directly, not via HTTP.
    """

    def test_correct_owner_removes_row(self, app, db_users):
        """delete_expense with matching owner must remove the expense row."""
        expense_id = db_users["expense_id"]
        primary_id = db_users["primary_id"]

        assert _row_exists(expense_id), "Row must exist before deletion"

        delete_expense(expense_id, primary_id)

        assert not _row_exists(expense_id), (
            "delete_expense must remove the row when expense_id and user_id both match"
        )

    def test_wrong_user_id_leaves_row_intact(self, app, db_users):
        """delete_expense with a mismatched user_id must NOT remove the row."""
        expense_id = db_users["expense_id"]
        other_id = db_users["other_id"]   # does not own this expense

        delete_expense(expense_id, other_id)

        assert _row_exists(expense_id), (
            "delete_expense must NOT delete a row that belongs to a different user"
        )

    def test_wrong_user_id_raises_no_error(self, app, db_users):
        """delete_expense with a wrong user_id must not raise any exception."""
        try:
            delete_expense(db_users["expense_id"], db_users["other_id"])
        except Exception as exc:
            pytest.fail(
                f"delete_expense raised an unexpected exception for a wrong user_id: {exc}"
            )

    def test_nonexistent_expense_id_raises_no_error(self, app, db_users):
        """delete_expense for a non-existent id must not raise any exception."""
        nonexistent_id = 99999
        primary_id = db_users["primary_id"]

        try:
            delete_expense(nonexistent_id, primary_id)
        except Exception as exc:
            pytest.fail(
                f"delete_expense raised an unexpected exception for a non-existent id: {exc}"
            )

    def test_nonexistent_expense_id_leaves_db_unchanged(self, app, db_users):
        """delete_expense for a non-existent id must not affect any existing row."""
        expense_id = db_users["expense_id"]
        before = _get_expense_row(expense_id)

        delete_expense(99999, db_users["primary_id"])

        after = _get_expense_row(expense_id)
        assert after["amount"] == before["amount"], (
            "Calling delete_expense with a non-existent id must not touch other rows"
        )

    def test_delete_is_scoped_to_owner(self, app, db_users):
        """
        Deleting user A's expense must leave user B's expense untouched,
        even when both are in the DB at the same time.
        """
        other_expense_id = db_users["other_expense_id"]
        expense_id = db_users["expense_id"]

        # Delete the primary user's expense
        delete_expense(expense_id, db_users["primary_id"])

        # The other user's expense must still be present
        assert _row_exists(other_expense_id), (
            "Deleting one user's expense must not remove a different user's expense"
        )


# ===========================================================================
# Auth guard — unauthenticated requests
# ===========================================================================

class TestDeleteExpenseAuthGuard:
    """Unauthenticated POST requests must be redirected to /login."""

    def test_unauthenticated_post_redirects_to_login(self, client, db_users):
        expense_id = db_users["expense_id"]
        r = client.post(f"/expenses/{expense_id}/delete")
        assert r.status_code == 302, (
            "POST /expenses/<id>/delete without auth must return 302"
        )
        assert "/login" in r.headers["Location"], (
            "Unauthenticated POST must redirect to /login"
        )

    def test_unauthenticated_post_does_not_delete_row(self, client, db_users):
        """Unauthenticated POST must not remove any expense from the DB."""
        expense_id = db_users["expense_id"]
        client.post(f"/expenses/{expense_id}/delete")
        assert _row_exists(expense_id), (
            "Unauthenticated POST must not delete the expense row"
        )


# ===========================================================================
# HTTP method guard — GET must be rejected
# ===========================================================================

class TestDeleteExpenseMethodGuard:
    """The delete route only accepts POST; GET must return 405."""

    def test_get_authenticated_returns_405(self, auth_client, db_users):
        expense_id = db_users["expense_id"]
        r = auth_client.get(f"/expenses/{expense_id}/delete")
        assert r.status_code == 405, (
            "GET /expenses/<id>/delete must return 405 Method Not Allowed"
        )

    def test_get_unauthenticated_returns_405(self, client, db_users):
        """
        Even for an unauthenticated client, GET to the delete route must
        return 405 — method rejection happens before auth checks.
        """
        expense_id = db_users["expense_id"]
        r = client.get(f"/expenses/{expense_id}/delete")
        assert r.status_code == 405, (
            "GET /expenses/<id>/delete must return 405 regardless of auth state"
        )

    def test_get_does_not_delete_row(self, auth_client, db_users):
        """A GET request (even authenticated) must not remove any expense."""
        expense_id = db_users["expense_id"]
        auth_client.get(f"/expenses/{expense_id}/delete")
        assert _row_exists(expense_id), (
            "GET to the delete route must not remove the expense from the DB"
        )


# ===========================================================================
# Happy path — authenticated POST, own expense
# ===========================================================================

class TestDeleteExpenseHappyPath:
    """Valid POST by the expense owner must delete the row and redirect."""

    def test_successful_delete_returns_302(self, auth_client, db_users):
        expense_id = db_users["expense_id"]
        r = auth_client.post(f"/expenses/{expense_id}/delete")
        assert r.status_code == 302, (
            "Successful POST /expenses/<id>/delete must return 302"
        )

    def test_successful_delete_redirects_to_profile(self, auth_client, db_users):
        expense_id = db_users["expense_id"]
        r = auth_client.post(f"/expenses/{expense_id}/delete")
        assert "/profile" in r.headers["Location"], (
            "After successful deletion, the response must redirect to /profile"
        )

    def test_successful_delete_removes_row_from_db(self, auth_client, db_users):
        expense_id = db_users["expense_id"]
        assert _row_exists(expense_id), "Expense must exist before the DELETE request"

        auth_client.post(f"/expenses/{expense_id}/delete")

        assert not _row_exists(expense_id), (
            "Expense row must no longer exist in the DB after a successful delete"
        )

    def test_successful_delete_shows_flash_message(self, auth_client, db_users):
        """Flash message 'Expense deleted.' must appear on the profile page."""
        expense_id = db_users["expense_id"]
        r = auth_client.post(
            f"/expenses/{expense_id}/delete", follow_redirects=True
        )
        assert b"Expense deleted." in r.data, (
            "Flash message 'Expense deleted.' must appear after a successful deletion"
        )

    def test_deleted_expense_not_in_profile_transaction_list(self, auth_client, db_users):
        """After deletion, the description must not appear in the profile table."""
        expense_id = db_users["expense_id"]
        description = SEED_EXPENSE["description"].encode()

        auth_client.post(
            f"/expenses/{expense_id}/delete", follow_redirects=True
        )

        r = auth_client.get("/profile")
        assert description not in r.data, (
            "The deleted expense's description must not appear in the profile transaction list"
        )

    def test_delete_does_not_affect_other_users_expense(self, auth_client, db_users):
        """Deleting one expense must leave the other user's expense intact."""
        expense_id = db_users["expense_id"]
        other_expense_id = db_users["other_expense_id"]

        auth_client.post(f"/expenses/{expense_id}/delete")

        assert _row_exists(other_expense_id), (
            "Deleting the primary user's expense must not remove the other user's expense"
        )

    def test_profile_returns_200_after_deletion(self, auth_client, db_users):
        """Profile page must still render correctly after an expense is deleted."""
        expense_id = db_users["expense_id"]
        auth_client.post(f"/expenses/{expense_id}/delete")
        r = auth_client.get("/profile")
        assert r.status_code == 200, (
            "Profile page must return 200 even after an expense has been deleted"
        )


# ===========================================================================
# Ownership enforcement — other user's expense
# ===========================================================================

class TestDeleteExpenseOwnershipGuard:
    """
    An authenticated user attempting to delete an expense owned by someone
    else must receive a 404 and the row must remain in the DB.
    """

    def test_other_users_expense_returns_404(self, auth_client, db_users):
        """POST to delete another user's expense must return 404."""
        other_expense_id = db_users["other_expense_id"]
        r = auth_client.post(f"/expenses/{other_expense_id}/delete")
        assert r.status_code == 404, (
            "POST /expenses/<id>/delete for another user's expense must return 404"
        )

    def test_other_users_expense_row_stays_in_db(self, auth_client, db_users):
        """The other user's expense must still exist after the failed attempt."""
        other_expense_id = db_users["other_expense_id"]
        auth_client.post(f"/expenses/{other_expense_id}/delete")
        assert _row_exists(other_expense_id), (
            "Other user's expense row must remain in the DB when ownership check fails"
        )

    def test_own_expense_not_affected_by_rejected_delete(self, auth_client, db_users):
        """
        When the ownership guard rejects a delete attempt, the primary user's
        own expense must remain untouched as well.
        """
        expense_id = db_users["expense_id"]
        other_expense_id = db_users["other_expense_id"]

        auth_client.post(f"/expenses/{other_expense_id}/delete")

        assert _row_exists(expense_id), (
            "The primary user's own expense must still be in the DB after a rejected delete"
        )


# ===========================================================================
# Non-existent expense id
# ===========================================================================

class TestDeleteExpenseNotFound:
    """POST for an id that does not exist at all must return 404."""

    def test_nonexistent_id_returns_404(self, auth_client):
        r = auth_client.post("/expenses/99999/delete")
        assert r.status_code == 404, (
            "POST /expenses/99999/delete for a non-existent id must return 404"
        )

    def test_nonexistent_id_leaves_db_unchanged(self, auth_client, db_users):
        expense_id = db_users["expense_id"]
        auth_client.post("/expenses/99999/delete")
        assert _row_exists(expense_id), (
            "A failed delete for a non-existent id must not affect any other row in the DB"
        )


# ===========================================================================
# Profile template — Delete button and form structure
# ===========================================================================

class TestProfileDeleteButton:
    """
    The profile transaction table must render a Delete button for each expense
    row, inside a form that POSTs to the correct delete URL.
    """

    def test_profile_has_actions_column_header(self, auth_client, db_users):
        r = auth_client.get("/profile")
        assert b"Actions" in r.data, (
            "Profile expense table must contain an 'Actions' column header"
        )

    def test_profile_has_delete_button(self, auth_client, db_users):
        r = auth_client.get("/profile")
        assert b"Delete" in r.data, (
            "Profile page must contain a 'Delete' button for each expense row"
        )

    def test_profile_delete_form_action_url(self, auth_client, db_users):
        """The delete form action must point to /expenses/<id>/delete."""
        expense_id = db_users["expense_id"]
        r = auth_client.get("/profile")
        expected_action = f"/expenses/{expense_id}/delete".encode()
        assert expected_action in r.data, (
            f"Profile page must contain a form action pointing to /expenses/{expense_id}/delete"
        )

    def test_profile_delete_form_uses_post_method(self, auth_client, db_users):
        """The delete form must use method='post' (not GET)."""
        r = auth_client.get("/profile")
        # The spec mandates a POST-only route and a <form method="post">
        assert b'method="post"' in r.data or b"method='post'" in r.data, (
            "The delete form on the profile page must use method='post'"
        )

    def test_profile_has_both_edit_and_delete_actions(self, auth_client, db_users):
        """Each expense row must show both Edit and Delete actions."""
        r = auth_client.get("/profile")
        assert b"Edit" in r.data, (
            "Profile page must show an 'Edit' action alongside the 'Delete' button"
        )
        assert b"Delete" in r.data, (
            "Profile page must show a 'Delete' action alongside the 'Edit' link"
        )

    def test_profile_delete_form_is_inline(self, auth_client, db_users):
        """
        The spec explicitly requires display:inline on the delete form so it
        sits beside the Edit link without breaking layout.
        """
        r = auth_client.get("/profile")
        assert b"display:inline" in r.data or b"display: inline" in r.data, (
            "Delete form must have style='display:inline' so it renders next to the Edit link"
        )


# ===========================================================================
# Security / edge cases
# ===========================================================================

class TestDeleteExpenseSecurity:
    """Security and edge-case tests for the delete route."""

    def test_spoofed_user_id_in_post_body_cannot_delete(self, client, db_users):
        """
        A POST that includes user_id in the form body must not bypass the
        server-side session check.  The route must read user_id exclusively
        from session, not from POST data.
        """
        primary_id = db_users["primary_id"]
        other_expense_id = db_users["other_expense_id"]

        # Log in as the primary user
        with client.session_transaction() as sess:
            sess["user_id"] = primary_id
            sess["user_name"] = "Primary User"

        # Attempt to delete the other user's expense, sending their user_id in form data
        client.post(
            f"/expenses/{other_expense_id}/delete",
            data={"user_id": str(db_users["other_id"])},
        )

        assert _row_exists(other_expense_id), (
            "Spoofed user_id in POST body must not allow deleting another user's expense"
        )

    def test_non_integer_expense_id_in_url_returns_404(self, auth_client):
        """
        Flask's <int:id> converter rejects non-integer path segments.
        The route must not be reachable with a string id like 'abc'.
        """
        r = auth_client.post("/expenses/abc/delete")
        assert r.status_code == 404, (
            "A non-integer expense id in the URL must result in a 404"
        )

    def test_delete_is_idempotent_in_effect(self, auth_client, db_users):
        """
        POSTing twice to delete the same expense: the first call must succeed,
        and the second call must return 404 (row already gone).
        This confirms there is no double-delete data corruption.
        """
        expense_id = db_users["expense_id"]

        r1 = auth_client.post(f"/expenses/{expense_id}/delete")
        assert r1.status_code == 302, "First delete must redirect (302)"

        r2 = auth_client.post(f"/expenses/{expense_id}/delete")
        assert r2.status_code == 404, (
            "Second POST to the same delete URL must return 404 because the row is already gone"
        )

    def test_session_user_cannot_be_hijacked_via_missing_cookie(
        self, client, db_users
    ):
        """
        An unauthenticated client that sends no session cookie must be
        redirected to /login — not be able to delete any expense.
        """
        expense_id = db_users["expense_id"]
        r = client.post(f"/expenses/{expense_id}/delete")
        assert r.status_code == 302, "No-session POST must redirect"
        assert "/login" in r.headers["Location"], (
            "No-session POST must redirect specifically to /login"
        )
        assert _row_exists(expense_id), (
            "No-session POST must not remove the expense from the DB"
        )
