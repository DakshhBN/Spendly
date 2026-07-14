from datetime import datetime
from database.db import get_db


def _fmt_rupee(value: float) -> str:
    return f"₹{value:,.0f}"


def _fmt_date(iso: str) -> str:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(iso, fmt)
            return dt.strftime("%d %b %Y").lstrip("0")
        except ValueError:
            continue
    return iso


def get_user_by_id(user_id):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    parts = row["name"].split()
    initials = "".join(p[0].upper() for p in parts[:2])
    try:
        dt = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        dt = datetime.strptime(row["created_at"], "%Y-%m-%d")
    return {
        "name": row["name"],
        "email": row["email"],
        "initials": initials,
        "member_since": dt.strftime("%B %Y"),
    }


def _date_where(user_id, from_date=None, to_date=None):
    conditions = ["user_id = ?"]
    params = [user_id]
    if from_date:
        conditions.append("date >= ?")
        params.append(from_date)
    if to_date:
        conditions.append("date <= ?")
        params.append(to_date)
    return "WHERE " + " AND ".join(conditions), params


def get_summary_stats(user_id, from_date=None, to_date=None):
    conn = get_db()
    try:
        where, params = _date_where(user_id, from_date, to_date)
        agg = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt "
            "FROM expenses " + where,
            params,
        ).fetchone()
        top = conn.execute(
            "SELECT category FROM expenses " + where +
            " GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
            params,
        ).fetchone()
    finally:
        conn.close()
    return {
        "total_spent": _fmt_rupee(agg["total"]),
        "transaction_count": agg["cnt"],
        "top_category": top["category"] if top else "—",
    }


def get_recent_transactions(user_id, limit=10, from_date=None, to_date=None):
    conn = get_db()
    try:
        where, params = _date_where(user_id, from_date, to_date)
        rows = conn.execute(
            "SELECT date, description, category, amount FROM expenses "
            + where + " ORDER BY date DESC LIMIT ?",
            params + [limit],
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "date": _fmt_date(r["date"]),
            "description": r["description"],
            "category": r["category"],
            "amount": _fmt_rupee(r["amount"]),
        }
        for r in rows
    ]


def get_category_breakdown(user_id, from_date=None, to_date=None):
    conn = get_db()
    try:
        where, params = _date_where(user_id, from_date, to_date)
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            + where + " GROUP BY category ORDER BY total DESC",
            params,
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        return []
    grand_total = sum(r["total"] for r in rows)
    result = [
        {
            "name": r["category"],
            "amount": _fmt_rupee(r["total"]),
            "percent": round(r["total"] / grand_total * 100),
            "_raw": r["total"],
        }
        for r in rows
    ]
    diff = 100 - sum(c["percent"] for c in result)
    if diff != 0:
        result[0]["percent"] += diff
    for c in result:
        del c["_raw"]
    return result
