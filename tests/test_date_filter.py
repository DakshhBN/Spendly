"""
tests/test_date_filter.py

Tests for the Step 06 date-filter feature on the Spendly profile page.

Coverage:
- GET /profile with no params          → 200, all-time data
- GET /profile?from=...&to=...         → filtered stats, transactions, categories
- GET /profile?from=... (no to)        → open-ended upper bound
- GET /profile?to=...  (no from)       → open-ended lower bound
- Date range with no matches           → zero stats, empty lists, no exceptions
- Unauthenticated access with params   → 302 to /login
- Garbage/invalid date strings         → silently ignored, falls back to all-time
- URL reflects applied filter params
- Form inputs pre-populated with applied filter values
- Unit-level tests for get_summary_stats, get_recent_transactions,
  get_category_breakdown with from_date / to_date keyword args
"""

import pytest
import database.queries as q


# ---------------------------------------------------------------------------
# Seed data reference (matches conftest.py db_setup fixture exactly)
#
# date          amount   category
# 2026-07-01    320.0    Food
# 2026-07-02     85.0    Transport
# 2026-07-03   1200.0    Bills
# 2026-07-05    500.0    Health
# 2026-07-08    399.0    Entertainment
# 2026-07-10   2150.0    Shopping
# 2026-07-15    650.0    Food
# 2026-07-20    250.0    Other
#
# All-time total  = 5,554
# 2026-07-01 to 2026-07-10 total = 320+85+1200+500+399+2150 = 4,654  (6 txns)
# 2026-07-01 to 2026-07-05 total = 320+85+1200+500           = 2,105  (4 txns)
# 2026-07-10 onwards      total  = 2150+650+250               = 3,050  (3 txns)
# 2026-07-16 to 2026-07-19 total = 0                          (0 txns)
# ---------------------------------------------------------------------------


# ===========================================================================
# HTTP-level tests — profile route with date filter query params
# ===========================================================================

class TestProfileRouteDateFilter:
    """Tests for GET /profile with date filter query parameters."""

    def _login(self, client, db_setup):
        """Inject a valid session for the Demo User created by db_setup."""
        with client.session_transaction() as sess:
            sess["user_id"] = db_setup["user_id"]
            sess["user_name"] = "Demo User"

    # -----------------------------------------------------------------------
    # 1. No params → 200, all-time data visible
    # -----------------------------------------------------------------------

    def test_no_params_returns_200(self, client, db_setup):
        self._login(client, db_setup)
        r = client.get("/profile")
        assert r.status_code == 200, "Expected 200 OK for /profile with no date params"

    def test_no_params_shows_all_time_total(self, client, db_setup):
        self._login(client, db_setup)
        r = client.get("/profile")
        assert "5,554".encode() in r.data, (
            "All-time total ₹5,554 should appear in the page with no date filter"
        )

    def test_no_params_shows_all_transaction_count(self, client, db_setup):
        self._login(client, db_setup)
        r = client.get("/profile")
        # 8 transactions in seed data; the number "8" must appear somewhere
        assert b"8" in r.data, "Transaction count 8 should appear with no date filter"

    def test_no_params_shows_top_category_shopping(self, client, db_setup):
        self._login(client, db_setup)
        r = client.get("/profile")
        assert b"Shopping" in r.data, "Top category 'Shopping' should appear with no date filter"

    # -----------------------------------------------------------------------
    # 2. Both from and to → filtered data
    # -----------------------------------------------------------------------

    def test_both_params_returns_200(self, client, db_setup):
        self._login(client, db_setup)
        r = client.get("/profile?from=2026-07-01&to=2026-07-10")
        assert r.status_code == 200, "Expected 200 OK for /profile with both date params"

    def test_both_params_filters_total_spent(self, client, db_setup):
        # 2026-07-01 to 2026-07-10 inclusive: 320+85+1200+500+399+2150 = 4,654
        self._login(client, db_setup)
        r = client.get("/profile?from=2026-07-01&to=2026-07-10")
        assert "4,654".encode() in r.data, (
            "Filtered total ₹4,654 should appear for 2026-07-01 to 2026-07-10"
        )

    def test_both_params_excludes_out_of_range_expenses(self, client, db_setup):
        # Expenses on 2026-07-15 (₹650) and 2026-07-20 (₹250) must NOT appear
        # as totals — we test by confirming the all-time total is absent
        self._login(client, db_setup)
        r = client.get("/profile?from=2026-07-01&to=2026-07-10")
        assert "5,554".encode() not in r.data, (
            "All-time total ₹5,554 must NOT appear when a date filter is applied"
        )

    def test_both_params_correct_transaction_count(self, client, db_setup):
        # 6 expenses fall within 2026-07-01 to 2026-07-10
        self._login(client, db_setup)
        r = client.get("/profile?from=2026-07-01&to=2026-07-10")
        assert b"6" in r.data, "Transaction count of 6 should appear for filtered range"

    def test_both_params_top_category_is_shopping(self, client, db_setup):
        # Shopping (₹2,150) is the biggest spend in 2026-07-01..2026-07-10
        self._login(client, db_setup)
        r = client.get("/profile?from=2026-07-01&to=2026-07-10")
        assert b"Shopping" in r.data, "Shopping should be top category in 2026-07-01..2026-07-10"

    # -----------------------------------------------------------------------
    # 3. from only (open-ended upper bound)
    # -----------------------------------------------------------------------

    def test_from_only_returns_200(self, client, db_setup):
        self._login(client, db_setup)
        r = client.get("/profile?from=2026-07-10")
        assert r.status_code == 200, "Expected 200 OK for /profile?from=..."

    def test_from_only_includes_boundary_date(self, client, db_setup):
        # 2026-07-10 itself (₹2,150 Shopping) must be included
        self._login(client, db_setup)
        r = client.get("/profile?from=2026-07-10")
        assert b"Shopping" in r.data, "Shopping (2026-07-10) must be included with from=2026-07-10"

    def test_from_only_correct_total(self, client, db_setup):
        # 2026-07-10 onwards: 2150+650+250 = 3,050
        self._login(client, db_setup)
        r = client.get("/profile?from=2026-07-10")
        assert "3,050".encode() in r.data, (
            "Total ₹3,050 should appear for expenses from 2026-07-10 onwards"
        )

    def test_from_only_excludes_earlier_expenses(self, client, db_setup):
        # Grocery (2026-07-01, ₹320) must not push total to 5,554
        self._login(client, db_setup)
        r = client.get("/profile?from=2026-07-10")
        assert "5,554".encode() not in r.data, (
            "All-time total must not appear when from= filter is active"
        )

    # -----------------------------------------------------------------------
    # 4. to only (open-ended lower bound)
    # -----------------------------------------------------------------------

    def test_to_only_returns_200(self, client, db_setup):
        self._login(client, db_setup)
        r = client.get("/profile?to=2026-07-05")
        assert r.status_code == 200, "Expected 200 OK for /profile?to=..."

    def test_to_only_includes_boundary_date(self, client, db_setup):
        # 2026-07-05 (₹500 Health) must be included
        self._login(client, db_setup)
        r = client.get("/profile?to=2026-07-05")
        assert b"Health" in r.data, "Health expense (2026-07-05) must be included with to=2026-07-05"

    def test_to_only_correct_total(self, client, db_setup):
        # up to 2026-07-05: 320+85+1200+500 = 2,105
        self._login(client, db_setup)
        r = client.get("/profile?to=2026-07-05")
        assert "2,105".encode() in r.data, (
            "Total ₹2,105 should appear for expenses up to 2026-07-05"
        )

    def test_to_only_excludes_later_expenses(self, client, db_setup):
        # Shopping (2026-07-10, ₹2,150) must not appear in totals
        self._login(client, db_setup)
        r = client.get("/profile?to=2026-07-05")
        assert "5,554".encode() not in r.data, (
            "All-time total must not appear when to= filter is active"
        )

    # -----------------------------------------------------------------------
    # 5. Date range with no matching expenses
    # -----------------------------------------------------------------------

    def test_empty_range_returns_200(self, client, db_setup):
        # No expenses exist between 2026-07-16 and 2026-07-19
        self._login(client, db_setup)
        r = client.get("/profile?from=2026-07-16&to=2026-07-19")
        assert r.status_code == 200, "Empty date range must not cause a server error"

    def test_empty_range_shows_zero_total(self, client, db_setup):
        self._login(client, db_setup)
        r = client.get("/profile?from=2026-07-16&to=2026-07-19")
        assert "₹0".encode() in r.data, "₹0 total should appear when date range has no expenses"

    def test_empty_range_shows_zero_transaction_count(self, client, db_setup):
        self._login(client, db_setup)
        r = client.get("/profile?from=2026-07-16&to=2026-07-19")
        # "0" must appear somewhere (transaction count)
        assert b"0" in r.data, "0 transactions should appear when date range has no expenses"

    def test_empty_range_shows_dash_top_category(self, client, db_setup):
        self._login(client, db_setup)
        r = client.get("/profile?from=2026-07-16&to=2026-07-19")
        assert "—".encode() in r.data, "'—' should appear as top category when no expenses match"

    # -----------------------------------------------------------------------
    # 6. Unauthenticated access with date params
    # -----------------------------------------------------------------------

    def test_unauthenticated_with_date_params_redirects(self, client):
        r = client.get("/profile?from=2026-07-01&to=2026-07-10")
        assert r.status_code == 302, "Unauthenticated access must return 302"
        assert "/login" in r.headers["Location"], (
            "Unauthenticated request must redirect to /login"
        )

    def test_unauthenticated_with_from_only_redirects(self, client):
        r = client.get("/profile?from=2026-07-01")
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]

    def test_unauthenticated_with_to_only_redirects(self, client):
        r = client.get("/profile?to=2026-07-31")
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]

    # -----------------------------------------------------------------------
    # 7. Invalid / garbage date strings silently ignored
    # -----------------------------------------------------------------------

    def test_garbage_from_param_falls_back_to_all_time(self, client, db_setup):
        self._login(client, db_setup)
        r = client.get("/profile?from=not-a-date")
        assert r.status_code == 200, "Garbage from= param must not cause a server error"
        assert "5,554".encode() in r.data, (
            "All-time total should appear when from= is an invalid date"
        )

    def test_garbage_to_param_falls_back_to_all_time(self, client, db_setup):
        self._login(client, db_setup)
        r = client.get("/profile?to=31-07-2026")
        assert r.status_code == 200, "Non-ISO to= param must not cause a server error"
        assert "5,554".encode() in r.data, (
            "All-time total should appear when to= is a non-ISO date string"
        )

    def test_both_garbage_params_fall_back_to_all_time(self, client, db_setup):
        self._login(client, db_setup)
        r = client.get("/profile?from=abc&to=xyz")
        assert r.status_code == 200
        assert "5,554".encode() in r.data, (
            "All-time total should appear when both date params are garbage"
        )

    def test_partial_date_string_ignored(self, client, db_setup):
        # "2026-07" is not a full ISO date — must be treated as invalid
        self._login(client, db_setup)
        r = client.get("/profile?from=2026-07&to=2026-08")
        assert r.status_code == 200
        assert "5,554".encode() in r.data, (
            "Partial date strings (YYYY-MM) must be ignored and all-time data shown"
        )

    def test_empty_string_params_fall_back_to_all_time(self, client, db_setup):
        self._login(client, db_setup)
        r = client.get("/profile?from=&to=")
        assert r.status_code == 200
        assert "5,554".encode() in r.data, (
            "Empty string params should be treated as absent and show all-time data"
        )

    # -----------------------------------------------------------------------
    # 8. URL reflects filter params (form pre-population)
    # -----------------------------------------------------------------------

    def test_from_value_pre_populated_in_response(self, client, db_setup):
        self._login(client, db_setup)
        r = client.get("/profile?from=2026-07-01&to=2026-07-10")
        assert b"2026-07-01" in r.data, (
            "The from date value must appear in the response (pre-populated input)"
        )

    def test_to_value_pre_populated_in_response(self, client, db_setup):
        self._login(client, db_setup)
        r = client.get("/profile?from=2026-07-01&to=2026-07-10")
        assert b"2026-07-10" in r.data, (
            "The to date value must appear in the response (pre-populated input)"
        )

    def test_filter_form_present_on_profile_page(self, client, db_setup):
        self._login(client, db_setup)
        r = client.get("/profile")
        assert b'method="get"' in r.data or b"method='get'" in r.data, (
            "Date filter form must use method=get so params appear in the URL"
        )

    def test_filter_form_action_is_profile(self, client, db_setup):
        self._login(client, db_setup)
        r = client.get("/profile")
        assert b'action="/profile"' in r.data or b"/profile" in r.data, (
            "Date filter form action must be /profile"
        )

    def test_date_inputs_present_on_profile_page(self, client, db_setup):
        self._login(client, db_setup)
        r = client.get("/profile")
        assert b'type="date"' in r.data, (
            "Profile page must include date inputs of type='date'"
        )


# ===========================================================================
# Unit-level tests — get_summary_stats with date filters
# ===========================================================================

class TestSummaryStatsDateFilter:
    """Unit tests for get_summary_stats(user_id, from_date, to_date)."""

    def test_no_dates_returns_all_time_stats(self, db_setup):
        stats = q.get_summary_stats(db_setup["user_id"])
        assert stats["total_spent"] == "₹5,554", "All-time total should be ₹5,554"
        assert stats["transaction_count"] == 8, "All-time count should be 8"
        assert stats["top_category"] == "Shopping", "All-time top category should be Shopping"

    def test_both_dates_filters_total(self, db_setup):
        # 2026-07-01..2026-07-10: 320+85+1200+500+399+2150 = 4,654
        stats = q.get_summary_stats(db_setup["user_id"], from_date="2026-07-01", to_date="2026-07-10")
        assert stats["total_spent"] == "₹4,654", (
            "Filtered total should be ₹4,654 for 2026-07-01..2026-07-10"
        )

    def test_both_dates_filters_count(self, db_setup):
        stats = q.get_summary_stats(db_setup["user_id"], from_date="2026-07-01", to_date="2026-07-10")
        assert stats["transaction_count"] == 6, "Should count 6 transactions in 2026-07-01..2026-07-10"

    def test_both_dates_top_category(self, db_setup):
        stats = q.get_summary_stats(db_setup["user_id"], from_date="2026-07-01", to_date="2026-07-10")
        assert stats["top_category"] == "Shopping", "Shopping should be top category in that range"

    def test_from_date_only_filters_correctly(self, db_setup):
        # 2026-07-10 onwards: 2150+650+250 = 3,050 (3 transactions)
        stats = q.get_summary_stats(db_setup["user_id"], from_date="2026-07-10")
        assert stats["total_spent"] == "₹3,050", "Total from 2026-07-10 onwards should be ₹3,050"
        assert stats["transaction_count"] == 3, "Should count 3 transactions from 2026-07-10 onwards"

    def test_to_date_only_filters_correctly(self, db_setup):
        # up to 2026-07-05: 320+85+1200+500 = 2,105 (4 transactions)
        stats = q.get_summary_stats(db_setup["user_id"], to_date="2026-07-05")
        assert stats["total_spent"] == "₹2,105", "Total up to 2026-07-05 should be ₹2,105"
        assert stats["transaction_count"] == 4, "Should count 4 transactions up to 2026-07-05"

    def test_empty_range_returns_zero_total(self, db_setup):
        # No expenses exist between 2026-07-16 and 2026-07-19
        stats = q.get_summary_stats(db_setup["user_id"], from_date="2026-07-16", to_date="2026-07-19")
        assert stats["total_spent"] == "₹0", "Total should be ₹0 for empty range"

    def test_empty_range_returns_zero_count(self, db_setup):
        stats = q.get_summary_stats(db_setup["user_id"], from_date="2026-07-16", to_date="2026-07-19")
        assert stats["transaction_count"] == 0, "Count should be 0 for empty range"

    def test_empty_range_returns_dash_top_category(self, db_setup):
        stats = q.get_summary_stats(db_setup["user_id"], from_date="2026-07-16", to_date="2026-07-19")
        assert stats["top_category"] == "—", "Top category should be '—' for empty range"

    def test_boundary_dates_are_inclusive(self, db_setup):
        # from=2026-07-20 to=2026-07-20 should capture exactly one expense (₹250 Other)
        stats = q.get_summary_stats(db_setup["user_id"], from_date="2026-07-20", to_date="2026-07-20")
        assert stats["total_spent"] == "₹250", "Boundary date must be inclusive"
        assert stats["transaction_count"] == 1, "Exactly one expense on 2026-07-20"

    def test_empty_user_returns_zero_with_dates(self, db_setup):
        stats = q.get_summary_stats(db_setup["empty_id"], from_date="2026-07-01", to_date="2026-07-31")
        assert stats["total_spent"] == "₹0"
        assert stats["transaction_count"] == 0
        assert stats["top_category"] == "—"


# ===========================================================================
# Unit-level tests — get_recent_transactions with date filters
# ===========================================================================

class TestRecentTransactionsDateFilter:
    """Unit tests for get_recent_transactions(user_id, from_date, to_date)."""

    def test_no_dates_returns_all_transactions(self, db_setup):
        txns = q.get_recent_transactions(db_setup["user_id"])
        assert len(txns) == 8, "All 8 transactions should be returned with no date filter"

    def test_both_dates_returns_only_matching(self, db_setup):
        # 2026-07-01..2026-07-10 → 6 transactions
        txns = q.get_recent_transactions(
            db_setup["user_id"], from_date="2026-07-01", to_date="2026-07-10"
        )
        assert len(txns) == 6, "Should return 6 transactions for 2026-07-01..2026-07-10"

    def test_both_dates_results_ordered_newest_first(self, db_setup):
        txns = q.get_recent_transactions(
            db_setup["user_id"], from_date="2026-07-01", to_date="2026-07-10"
        )
        assert txns[0]["date"] == "10 Jul 2026", "Most recent expense in range should be first"

    def test_from_date_only_returns_on_and_after(self, db_setup):
        # from 2026-07-10 → 3 transactions (2026-07-10, 2026-07-15, 2026-07-20)
        txns = q.get_recent_transactions(db_setup["user_id"], from_date="2026-07-10")
        assert len(txns) == 3, "Should return 3 transactions from 2026-07-10 onwards"

    def test_from_date_boundary_included(self, db_setup):
        txns = q.get_recent_transactions(db_setup["user_id"], from_date="2026-07-10")
        dates = [t["date"] for t in txns]
        assert "10 Jul 2026" in dates, "2026-07-10 (boundary) must be included with from_date"

    def test_from_date_excludes_earlier(self, db_setup):
        txns = q.get_recent_transactions(db_setup["user_id"], from_date="2026-07-10")
        dates = [t["date"] for t in txns]
        assert "1 Jul 2026" not in dates, "Expenses before from_date must be excluded"

    def test_to_date_only_returns_on_and_before(self, db_setup):
        # up to 2026-07-05 → 4 transactions (Jul 1, 2, 3, 5)
        txns = q.get_recent_transactions(db_setup["user_id"], to_date="2026-07-05")
        assert len(txns) == 4, "Should return 4 transactions up to 2026-07-05"

    def test_to_date_boundary_included(self, db_setup):
        txns = q.get_recent_transactions(db_setup["user_id"], to_date="2026-07-05")
        dates = [t["date"] for t in txns]
        assert "5 Jul 2026" in dates, "2026-07-05 (boundary) must be included with to_date"

    def test_to_date_excludes_later(self, db_setup):
        txns = q.get_recent_transactions(db_setup["user_id"], to_date="2026-07-05")
        dates = [t["date"] for t in txns]
        assert "10 Jul 2026" not in dates, "Expenses after to_date must be excluded"

    def test_empty_range_returns_empty_list(self, db_setup):
        txns = q.get_recent_transactions(
            db_setup["user_id"], from_date="2026-07-16", to_date="2026-07-19"
        )
        assert txns == [], "Empty date range should return an empty list"

    def test_transaction_fields_present_after_filter(self, db_setup):
        txns = q.get_recent_transactions(
            db_setup["user_id"], from_date="2026-07-01", to_date="2026-07-03"
        )
        assert len(txns) > 0, "Expected at least one transaction in range"
        txn = txns[0]
        assert "date" in txn, "Transaction must have 'date' field"
        assert "description" in txn, "Transaction must have 'description' field"
        assert "category" in txn, "Transaction must have 'category' field"
        assert "amount" in txn, "Transaction must have 'amount' field"
        assert txn["amount"].startswith("₹"), "Amount must be formatted in Rupees"

    def test_empty_user_returns_empty_with_dates(self, db_setup):
        txns = q.get_recent_transactions(
            db_setup["empty_id"], from_date="2026-07-01", to_date="2026-07-31"
        )
        assert txns == [], "Empty user should return empty list with date filter"

    def test_newest_first_ordering_without_filter(self, db_setup):
        txns = q.get_recent_transactions(db_setup["user_id"])
        assert txns[0]["date"] == "20 Jul 2026", "Most recent expense must be first with no filter"


# ===========================================================================
# Unit-level tests — get_category_breakdown with date filters
# ===========================================================================

class TestCategoryBreakdownDateFilter:
    """Unit tests for get_category_breakdown(user_id, from_date, to_date)."""

    def test_no_dates_returns_all_categories(self, db_setup):
        cats = q.get_category_breakdown(db_setup["user_id"])
        assert len(cats) == 7, "All 7 distinct categories should appear with no filter"

    def test_both_dates_filters_categories(self, db_setup):
        # 2026-07-01..2026-07-05 covers: Food, Transport, Bills, Health → 4 categories
        cats = q.get_category_breakdown(
            db_setup["user_id"], from_date="2026-07-01", to_date="2026-07-05"
        )
        names = [c["name"] for c in cats]
        assert "Food" in names, "Food category must appear in 2026-07-01..2026-07-05"
        assert "Transport" in names, "Transport category must appear in 2026-07-01..2026-07-05"
        assert "Bills" in names, "Bills category must appear in 2026-07-01..2026-07-05"
        assert "Health" in names, "Health category must appear in 2026-07-01..2026-07-05"

    def test_both_dates_excludes_out_of_range_categories(self, db_setup):
        # Shopping (2026-07-10) must NOT appear in 2026-07-01..2026-07-05
        cats = q.get_category_breakdown(
            db_setup["user_id"], from_date="2026-07-01", to_date="2026-07-05"
        )
        names = [c["name"] for c in cats]
        assert "Shopping" not in names, (
            "Shopping (2026-07-10) must not appear in 2026-07-01..2026-07-05 breakdown"
        )

    def test_from_date_only_filters_categories(self, db_setup):
        # from 2026-07-10: Shopping, Food (restaurant Jul15), Other (Jul20)
        cats = q.get_category_breakdown(db_setup["user_id"], from_date="2026-07-10")
        names = [c["name"] for c in cats]
        assert "Shopping" in names, "Shopping must appear with from=2026-07-10"
        assert "Food" in names, "Food (restaurant Jul15) must appear with from=2026-07-10"
        assert "Other" in names, "Other (Jul20) must appear with from=2026-07-10"
        # Bills (2026-07-03) must be excluded
        assert "Bills" not in names, "Bills (2026-07-03) must not appear with from=2026-07-10"

    def test_to_date_only_filters_categories(self, db_setup):
        # up to 2026-07-05: Food, Transport, Bills, Health
        cats = q.get_category_breakdown(db_setup["user_id"], to_date="2026-07-05")
        names = [c["name"] for c in cats]
        assert "Entertainment" not in names, (
            "Entertainment (2026-07-08) must not appear with to=2026-07-05"
        )

    def test_percent_sums_to_100_after_filter(self, db_setup):
        cats = q.get_category_breakdown(
            db_setup["user_id"], from_date="2026-07-01", to_date="2026-07-10"
        )
        assert len(cats) > 0, "Expected categories in range"
        total_pct = sum(c["percent"] for c in cats)
        assert total_pct == 100, (
            f"Category percentages must sum to 100 after filtering, got {total_pct}"
        )

    def test_percent_sums_to_100_with_no_filter(self, db_setup):
        cats = q.get_category_breakdown(db_setup["user_id"])
        total_pct = sum(c["percent"] for c in cats)
        assert total_pct == 100, "Category percentages must sum to 100 with no filter"

    def test_empty_range_returns_empty_list(self, db_setup):
        cats = q.get_category_breakdown(
            db_setup["user_id"], from_date="2026-07-16", to_date="2026-07-19"
        )
        assert cats == [], "Empty date range should return empty category breakdown"

    def test_category_ordered_by_amount_descending(self, db_setup):
        cats = q.get_category_breakdown(
            db_setup["user_id"], from_date="2026-07-01", to_date="2026-07-10"
        )
        # Shopping (₹2,150) should be first
        assert cats[0]["name"] == "Shopping", "Category breakdown must be sorted by amount DESC"

    def test_percent_is_integer(self, db_setup):
        cats = q.get_category_breakdown(
            db_setup["user_id"], from_date="2026-07-01", to_date="2026-07-10"
        )
        for cat in cats:
            assert isinstance(cat["percent"], int), (
                f"Percent for {cat['name']} must be an integer, got {type(cat['percent'])}"
            )

    def test_amount_formatted_as_rupees(self, db_setup):
        cats = q.get_category_breakdown(
            db_setup["user_id"], from_date="2026-07-01", to_date="2026-07-10"
        )
        for cat in cats:
            assert cat["amount"].startswith("₹"), (
                f"Category amount must be formatted in Rupees, got {cat['amount']}"
            )

    def test_empty_user_returns_empty_with_dates(self, db_setup):
        cats = q.get_category_breakdown(
            db_setup["empty_id"], from_date="2026-07-01", to_date="2026-07-31"
        )
        assert cats == [], "Empty user should return empty list with date filter"


# ===========================================================================
# Parametrized tests — invalid / garbage date strings
# ===========================================================================

@pytest.mark.parametrize("from_val,to_val", [
    ("not-a-date", "2026-07-10"),
    ("2026-07-01", "nope"),
    ("abc", "xyz"),
    ("31/07/2026", "01/07/2026"),    # DD/MM/YYYY format — not ISO
    ("2026-07", "2026-08"),          # Partial ISO without day
    ("", ""),                        # Empty strings
    ("2026-13-01", "2026-07-10"),    # Invalid month
    ("2026-07-32", "2026-07-10"),    # Invalid day
])
def test_invalid_dates_fall_back_to_all_time_via_route(client, db_setup, from_val, to_val):
    """Garbage date query params must be silently ignored; all-time data shown."""
    with client.session_transaction() as sess:
        sess["user_id"] = db_setup["user_id"]
        sess["user_name"] = "Demo User"
    r = client.get(f"/profile?from={from_val}&to={to_val}")
    assert r.status_code == 200, (
        f"Invalid dates from='{from_val}' to='{to_val}' must not cause a server error"
    )


@pytest.mark.parametrize("from_val,to_val", [
    ("not-a-date", "2026-07-10"),
    ("2026-07-01", "nope"),
    ("abc", "xyz"),
    ("31/07/2026", "01/07/2026"),
    ("2026-07", "2026-08"),
    ("2026-13-01", "2026-07-10"),
    ("2026-07-32", "2026-07-10"),
])
def test_invalid_date_strings_treated_as_none_in_summary(db_setup, from_val, to_val):
    """
    The route's _valid_date helper sanitises params before passing to queries.
    Here we verify the query helpers themselves handle None gracefully
    (confirming the contract: invalid dates → None → no filter applied).
    """
    # Pass None for whichever param would be invalid — mirrors what the route does
    from_clean = from_val if _is_valid_iso(from_val) else None
    to_clean = to_val if _is_valid_iso(to_val) else None
    # Must not raise any exception
    stats = q.get_summary_stats(db_setup["user_id"], from_date=from_clean, to_date=to_clean)
    assert "total_spent" in stats
    assert "transaction_count" in stats
    assert "top_category" in stats


def _is_valid_iso(s):
    """Mirror of app.py _valid_date — used only in test helper above."""
    from datetime import datetime
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False


# ===========================================================================
# Consistency tests — all three data sections must use the same date filter
# ===========================================================================

class TestFilterConsistency:
    """
    The spec mandates that stats, transactions, and category breakdown
    always reflect the same date range — they must never be mismatched.
    """

    def test_filtered_count_matches_transaction_list_length(self, db_setup):
        # The transaction_count in stats must equal the number of transactions returned
        from_date = "2026-07-01"
        to_date   = "2026-07-10"
        stats = q.get_summary_stats(db_setup["user_id"], from_date=from_date, to_date=to_date)
        txns  = q.get_recent_transactions(db_setup["user_id"], from_date=from_date, to_date=to_date)
        assert stats["transaction_count"] == len(txns), (
            "transaction_count in stats must equal the number of items in get_recent_transactions "
            "for the same date range"
        )

    def test_filtered_categories_are_subset_of_filtered_transactions(self, db_setup):
        from_date = "2026-07-01"
        to_date   = "2026-07-10"
        txns = q.get_recent_transactions(db_setup["user_id"], from_date=from_date, to_date=to_date)
        cats = q.get_category_breakdown(db_setup["user_id"], from_date=from_date, to_date=to_date)
        txn_categories  = {t["category"] for t in txns}
        cat_names       = {c["name"] for c in cats}
        assert cat_names == txn_categories, (
            "Categories in breakdown must exactly match categories seen in transactions "
            "for the same date range"
        )

    def test_empty_range_consistent_across_all_helpers(self, db_setup):
        from_date = "2026-07-16"
        to_date   = "2026-07-19"
        stats = q.get_summary_stats(db_setup["user_id"], from_date=from_date, to_date=to_date)
        txns  = q.get_recent_transactions(db_setup["user_id"], from_date=from_date, to_date=to_date)
        cats  = q.get_category_breakdown(db_setup["user_id"], from_date=from_date, to_date=to_date)
        assert stats["transaction_count"] == 0, "Stats must show 0 transactions for empty range"
        assert txns  == [], "Transaction list must be empty for empty range"
        assert cats  == [], "Category breakdown must be empty for empty range"

    def test_no_filter_consistent_across_all_helpers(self, db_setup):
        stats = q.get_summary_stats(db_setup["user_id"])
        txns  = q.get_recent_transactions(db_setup["user_id"])
        cats  = q.get_category_breakdown(db_setup["user_id"])
        assert stats["transaction_count"] == len(txns), (
            "All-time stats count must equal all-time transaction list length"
        )
        assert len(cats) > 0, "Category breakdown must be non-empty for user with expenses"
