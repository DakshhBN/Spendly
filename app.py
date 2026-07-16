import os
import secrets
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from database.db import (
    get_db, init_db, seed_db, create_user, get_user_by_email,
    add_expense as db_add_expense,
    get_expense_by_id, update_expense,
)
from database.queries import (
    get_user_by_id, get_summary_stats,
    get_recent_transactions, get_category_breakdown,
    delete_expense as db_delete_expense,
)
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")

with app.app_context():
    init_db()
    seed_db()


CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]


@app.before_request
def _ensure_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _valid_date(s):
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return s
    except (ValueError, TypeError):
        return None


def _validate_expense_form(amount_str, category, date, description):
    errors = []
    amount = None
    try:
        amount = float(amount_str)
        if amount <= 0 or amount > 10_000_000:
            raise ValueError
    except ValueError:
        errors.append("Amount must be a positive number (max ₹1,00,00,000).")
    if category not in CATEGORIES:
        errors.append("Please select a valid category.")
    if not _valid_date(date):
        errors.append("Please enter a valid date.")
    if description and len(description) > 200:
        errors.append("Description must be 200 characters or fewer.")
    return amount, errors


def _check_csrf():
    if app.testing:
        return
    if request.form.get("csrf_token") != session.get("csrf_token"):
        abort(403)


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("register.html")

    name     = request.form.get("name", "").strip()
    email    = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    confirm  = request.form.get("confirm_password", "")

    if not name or not email or not password or not confirm:
        flash("All fields are required.")
        return render_template("register.html")

    if password != confirm:
        flash("Passwords do not match.")
        return render_template("register.html")

    if len(password) < 8:
        flash("Password must be at least 8 characters.")
        return render_template("register.html")

    try:
        user_id = create_user(name, email, password)
    except sqlite3.IntegrityError:
        flash("An account with this email already exists.")
        return render_template("register.html")

    session["user_id"]   = user_id
    session["user_name"] = name
    flash("Account created! Please sign in.")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("login.html")

    email    = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    user = get_user_by_email(email)
    if user and check_password_hash(user["password_hash"], password):
        session.clear()
        session["user_id"]   = user["id"]
        session["user_name"] = user["name"]
        return redirect(url_for("profile"))

    flash("Invalid email or password.")
    return render_template("login.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    uid  = session["user_id"]
    user = get_user_by_id(uid)
    if user is None:
        session.clear()
        flash("Session expired. Please log in again.")
        return redirect(url_for("login"))

    from_date = _valid_date(request.args.get("from"))
    to_date   = _valid_date(request.args.get("to"))

    stats      = get_summary_stats(uid, from_date=from_date, to_date=to_date)
    expenses   = get_recent_transactions(uid, from_date=from_date, to_date=to_date)
    categories = get_category_breakdown(uid, from_date=from_date, to_date=to_date)

    return render_template(
        "profile.html",
        user=user, stats=stats, expenses=expenses, categories=categories,
        from_date=from_date, to_date=to_date,
    )


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    today = datetime.today().strftime("%Y-%m-%d")

    if request.method == "GET":
        return render_template("add_expense.html", today=today, categories=CATEGORIES)

    _check_csrf()
    amount_str  = request.form.get("amount", "").strip()
    category    = request.form.get("category", "").strip()
    date        = request.form.get("date", "").strip()
    description = request.form.get("description", "").strip()

    amount, errors = _validate_expense_form(amount_str, category, date, description)
    for msg in errors:
        flash(msg)
    if errors:
        return render_template("add_expense.html", today=today, categories=CATEGORIES)

    db_add_expense(session["user_id"], amount, category, date, description)
    flash("Expense added successfully.")
    return redirect(url_for("profile"))


@app.route("/expenses/<int:expense_id>/edit", methods=["GET", "POST"])
def edit_expense(expense_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    uid     = session["user_id"]
    expense = get_expense_by_id(expense_id, uid)
    if expense is None:
        flash("Expense not found.")
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("edit_expense.html", expense=expense, categories=CATEGORIES)

    _check_csrf()
    amount_str  = request.form.get("amount", "").strip()
    category    = request.form.get("category", "").strip()
    date        = request.form.get("date", "").strip()
    description = request.form.get("description", "").strip()

    amount, errors = _validate_expense_form(amount_str, category, date, description)
    for msg in errors:
        flash(msg)
    if errors:
        return render_template("edit_expense.html", expense=expense, categories=CATEGORIES)

    update_expense(expense_id, uid, amount, category, date, description)
    flash("Expense updated successfully.")
    return redirect(url_for("profile"))


@app.route("/expenses/<int:expense_id>/delete", methods=["POST"])
def delete_expense(expense_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    _check_csrf()
    uid = session["user_id"]
    expense = get_expense_by_id(expense_id, uid)
    if expense is None:
        abort(404)

    db_delete_expense(expense_id, uid)
    flash("Expense deleted.")
    return redirect(url_for("profile"))


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", port=5001)
