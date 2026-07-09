import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from database.db import get_db, init_db, seed_db, create_user, get_user_by_email
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = "dev-secret-change-in-prod"

with app.app_context():
    init_db()
    seed_db()


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

    user = {
        "name": "Demo User",
        "email": "demo@spendly.com",
        "initials": "DU",
        "member_since": "1 Jul 2026",
    }
    stats = {
        "total_spent": "₹5,554",
        "transaction_count": 8,
        "top_category": "Food",
    }
    expenses = [
        {"date": "20 Jul 2026", "description": "Miscellaneous",       "category": "Other",         "amount": "₹250"},
        {"date": "15 Jul 2026", "description": "Restaurant dinner",   "category": "Food",          "amount": "₹650"},
        {"date": "10 Jul 2026", "description": "Clothes",             "category": "Shopping",      "amount": "₹2,150"},
        {"date": "8 Jul 2026",  "description": "OTT subscription",    "category": "Entertainment", "amount": "₹399"},
        {"date": "5 Jul 2026",  "description": "Pharmacy — vitamins", "category": "Health",        "amount": "₹500"},
    ]
    categories = [
        {"name": "Shopping",      "amount": "₹2,150", "percent": 100},
        {"name": "Food",          "amount": "₹970",   "percent": 45},
        {"name": "Bills",         "amount": "₹1,200", "percent": 56},
        {"name": "Health",        "amount": "₹500",   "percent": 23},
        {"name": "Entertainment", "amount": "₹399",   "percent": 19},
        {"name": "Other",         "amount": "₹250",   "percent": 12},
        {"name": "Transport",     "amount": "₹85",    "percent": 4},
    ]
    return render_template("profile.html", user=user, stats=stats, expenses=expenses, categories=categories)


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
