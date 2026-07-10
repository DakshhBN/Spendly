import pytest
from werkzeug.security import generate_password_hash
from database.db import get_db, init_db


@pytest.fixture
def app():
    import app as flask_app_module
    flask_app_module.app.config["TESTING"] = True
    flask_app_module.app.config["SECRET_KEY"] = "test-secret"
    return flask_app_module.app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db_setup(monkeypatch, tmp_path):
    db_file = str(tmp_path / "test.db")
    monkeypatch.setattr("database.db.DB_PATH", db_file)
    init_db()
    conn = get_db()

    cur = conn.execute(
        "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
        ("Demo User", "demo@spendly.com", generate_password_hash("demo123"), "2026-07-01 00:00:00"),
    )
    user_id = cur.lastrowid

    cur2 = conn.execute(
        "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
        ("Empty User", "empty@test.com", generate_password_hash("pass123"), "2026-07-01 00:00:00"),
    )
    empty_id = cur2.lastrowid

    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        [
            (user_id, 320.0,  "Food",          "2026-07-01", "Groceries"),
            (user_id, 85.0,   "Transport",     "2026-07-02", "Auto"),
            (user_id, 1200.0, "Bills",         "2026-07-03", "Electricity"),
            (user_id, 500.0,  "Health",        "2026-07-05", "Pharmacy"),
            (user_id, 399.0,  "Entertainment", "2026-07-08", "OTT"),
            (user_id, 2150.0, "Shopping",      "2026-07-10", "Clothes"),
            (user_id, 650.0,  "Food",          "2026-07-15", "Restaurant"),
            (user_id, 250.0,  "Other",         "2026-07-20", "Misc"),
        ],
    )
    conn.commit()
    conn.close()
    return {"user_id": user_id, "empty_id": empty_id}
