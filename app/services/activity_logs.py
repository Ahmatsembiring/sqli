"""Query activity log untuk halaman admin (filter + pagination)."""
from datetime import datetime, timedelta

from sqlalchemy.orm import joinedload

from app import db
from app.models import ActivityLog, Operation, User

PER_PAGE = 25


def _parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def parse_log_filters(args):
    operation = args.get("operation", "")
    return {
        "user_id": args.get("user_id", type=int),
        "endpoint": args.get("endpoint", "").strip(),
        "operation": operation if operation in {op.value for op in Operation} else "",
        "date_from": _parse_date(args.get("date_from")),
        "date_to": _parse_date(args.get("date_to")),
    }


def log_query(filters):
    stmt = db.select(ActivityLog).options(joinedload(ActivityLog.user))
    if filters["user_id"]:
        stmt = stmt.where(ActivityLog.user_id == filters["user_id"])
    if filters["endpoint"]:
        stmt = stmt.where(ActivityLog.endpoint == filters["endpoint"])
    if filters["operation"]:
        stmt = stmt.where(ActivityLog.operation == filters["operation"])
    if filters["date_from"]:
        stmt = stmt.where(ActivityLog.timestamp >= filters["date_from"])
    if filters["date_to"]:
        # date_to inklusif: sampai akhir hari tersebut
        stmt = stmt.where(ActivityLog.timestamp < filters["date_to"] + timedelta(days=1))
    return stmt.order_by(ActivityLog.timestamp.desc(), ActivityLog.id.desc())


def search_logs(filters, page):
    return db.paginate(log_query(filters), page=page, per_page=PER_PAGE, error_out=False)


def filter_options():
    endpoints = db.session.execute(
        db.select(ActivityLog.endpoint).distinct().order_by(ActivityLog.endpoint)
    ).scalars().all()
    users = db.session.execute(db.select(User.id, User.username).order_by(User.username)).all()
    return {"endpoints": endpoints, "users": users, "operations": [op.value for op in Operation]}
