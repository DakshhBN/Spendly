import database.queries as q


class TestGetUserById:
    def test_returns_user_dict(self, db_setup):
        user = q.get_user_by_id(db_setup["user_id"])
        assert user is not None
        assert user["name"] == "Demo User"
        assert user["email"] == "demo@spendly.com"
        assert user["initials"] == "DU"
        assert user["member_since"] == "July 2026"

    def test_missing_user_returns_none(self, db_setup):
        assert q.get_user_by_id(9999) is None


class TestGetSummaryStats:
    def test_with_expenses(self, db_setup):
        stats = q.get_summary_stats(db_setup["user_id"])
        assert stats["total_spent"] == "₹5,554"
        assert stats["transaction_count"] == 8
        assert stats["top_category"] == "Shopping"

    def test_empty_user(self, db_setup):
        stats = q.get_summary_stats(db_setup["empty_id"])
        assert stats["total_spent"] == "₹0"
        assert stats["transaction_count"] == 0
        assert stats["top_category"] == "—"


class TestGetRecentTransactions:
    def test_with_expenses_newest_first(self, db_setup):
        txns = q.get_recent_transactions(db_setup["user_id"])
        assert len(txns) == 8
        assert txns[0]["date"] == "20 Jul 2026"
        assert "description" in txns[0]
        assert "category" in txns[0]
        assert txns[0]["amount"].startswith("₹")

    def test_empty_user(self, db_setup):
        assert q.get_recent_transactions(db_setup["empty_id"]) == []


class TestGetCategoryBreakdown:
    def test_with_expenses(self, db_setup):
        cats = q.get_category_breakdown(db_setup["user_id"])
        assert len(cats) == 7
        assert cats[0]["name"] == "Shopping"
        assert sum(c["percent"] for c in cats) == 100
        assert all(isinstance(c["percent"], int) for c in cats)

    def test_empty_user(self, db_setup):
        assert q.get_category_breakdown(db_setup["empty_id"]) == []


class TestProfileRoute:
    def test_unauthenticated_redirects_to_login(self, client):
        r = client.get("/profile")
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]

    def test_authenticated_shows_real_user_data(self, client):
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["user_name"] = "Demo User"
        r = client.get("/profile")
        assert r.status_code == 200
        assert b"Demo User" in r.data
        assert b"demo@spendly.com" in r.data
        assert "₹".encode() in r.data
