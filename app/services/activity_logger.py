"""Activity Logger: merekam setiap query SQL yang dieksekusi aplikasi selama HTTP request.

Mekanisme:
- Event SQLAlchemy `before_cursor_execute` / `after_cursor_execute` / `handle_error` menangkap
  statement + parameter di level driver (PyMySQL). Query final dirender dengan `cursor.mogrify()`,
  yaitu string SQL yang benar-benar dikirim ke MariaDB (nilai parameter sudah di-escape).
- Entri dikumpulkan di `flask.g` lalu ditulis sekali di akhir request lewat koneksi terpisah,
  sehingga INSERT ke activity_logs sendiri tidak ikut terekam dan tidak terpengaruh rollback
  transaksi aplikasi.
- Query di luar HTTP request (CLI, init_db, test setup) tidak direkam.

Data sensitif yang TIDAK disimpan:
- field form yang namanya mengandung "password", "secret", "token" (termasuk csrf_token);
- nilai parameter SQL berbentuk hash password werkzeug (scrypt:/pbkdf2:) -> '[REDACTED]';
- cookie session tidak pernah dicatat; session_id adalah ID acak terpisah tanpa hak akses.
"""
import json
import logging
import re
import secrets
import time
from contextlib import contextmanager
from datetime import datetime

from flask import g, has_request_context, request, session
from flask_login import current_user
from sqlalchemy import event, insert

from app.models import ActivityLog, Operation, QueryStatus

logger = logging.getLogger(__name__)

REDACTED = "[REDACTED]"
SENSITIVE_FIELD = re.compile(r"password|passwd|secret|token", re.IGNORECASE)
PASSWORD_HASH = re.compile(r"^(scrypt|pbkdf2):")
OPERATIONS = {op.value for op in Operation}
MAX_QUERY_LENGTH = 60000
MAX_INPUT_LENGTH = 10000

# Request ke path ini tidak direkam: aset statis, dan halaman admin yang membaca log itu sendiri
# (agar membuka halaman log tidak menghasilkan log baru tanpa henti).
EXCLUDED_PATH_PREFIXES = ("/static/", "/admin/activity-logs")


# ---------- Helper ----------

def classify_operation(statement):
    first = statement.lstrip(" (\n\t").split(None, 1)
    keyword = first[0].upper() if first else ""
    return keyword if keyword in OPERATIONS else Operation.OTHER.value


def _redact_value(value):
    if isinstance(value, str) and PASSWORD_HASH.match(value):
        return REDACTED
    return value


def redact_parameters(parameters):
    if isinstance(parameters, dict):
        return {k: _redact_value(v) for k, v in parameters.items()}
    if isinstance(parameters, (list, tuple)):
        return type(parameters)(_redact_value(v) for v in parameters)
    return parameters


def render_query(cursor, statement, parameters):
    safe_params = redact_parameters(parameters)
    try:
        rendered = cursor.mogrify(statement, safe_params) if safe_params else statement
    except Exception:  # render gagal: simpan statement mentah tanpa nilai parameter
        rendered = statement
    return rendered[:MAX_QUERY_LENGTH]


def collect_input_data():
    """Input request (path params, query string, form) tanpa field sensitif, dalam JSON."""
    data = {}
    for source in (request.view_args or {}, request.args, request.form):
        for key in source:
            if SENSITIVE_FIELD.search(key):
                if key != "csrf_token":
                    data[key] = REDACTED
                continue
            values = source.getlist(key) if hasattr(source, "getlist") else [source[key]]
            data[key] = values[0] if len(values) == 1 else values
    if not data:
        return None
    return json.dumps(data, ensure_ascii=False, default=str)[:MAX_INPUT_LENGTH]


def _session_id():
    if "sid" not in session:
        session["sid"] = secrets.token_hex(16)
    return session["sid"]


def _should_log():
    return (
        has_request_context()
        and not g.get("_activity_log_suspended", 0)
        and not request.path.startswith(EXCLUDED_PATH_PREFIXES)
    )


@contextmanager
def suspended():
    """Matikan perekaman sementara (untuk query infrastruktur, mis. user_loader Flask-Login)."""
    if not has_request_context():
        yield
        return
    g._activity_log_suspended = g.get("_activity_log_suspended", 0) + 1
    try:
        yield
    finally:
        g._activity_log_suspended -= 1


# ---------- Event SQLAlchemy ----------

def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault("_query_start", []).append(time.perf_counter())


def _pop_elapsed_ms(conn):
    stack = conn.info.get("_query_start")
    if not stack:
        return 0.0
    return (time.perf_counter() - stack.pop()) * 1000


def _record(cursor, statement, parameters, executemany, elapsed_ms, status, error=None):
    param_sets = parameters if executemany else [parameters]
    for params in param_sets:
        g.setdefault("_activity_log_entries", []).append({
            "timestamp": datetime.now(),
            "query": render_query(cursor, statement, params),
            "operation": classify_operation(statement),
            "status": status,
            "error_message": (str(error)[:255] if error else None),
            "response_time": round(elapsed_ms, 3),
        })


def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    elapsed = _pop_elapsed_ms(conn)
    if _should_log():
        _record(cursor, statement, parameters, executemany, elapsed, QueryStatus.SUCCESS.value)


def _handle_error(exc_context):
    conn = exc_context.connection
    elapsed = _pop_elapsed_ms(conn) if conn is not None else 0.0
    if not _should_log() or conn is None or exc_context.statement is None:
        return
    # ExceptionContext tidak menyediakan cursor; render query dengan cursor baru dari koneksi DBAPI yang sama.
    try:
        cursor = conn.connection.cursor()
    except Exception:
        return
    _record(
        cursor,
        exc_context.statement,
        exc_context.parameters,
        bool(exc_context.execution_context and exc_context.execution_context.executemany),
        elapsed,
        QueryStatus.ERROR.value,
        error=exc_context.original_exception,
    )


# ---------- Flush per request ----------

def _flush(engine, db):
    entries = g.pop("_activity_log_entries", None)
    if not entries:
        return

    with suspended():
        # Ambil metadata request SEBELUM rollback: rollback meng-expire current_user, dan membacanya
        # sesudahnya akan memicu query baru yang membuka transaksi dengan snapshot lama.
        user_id = current_user.get_id() if current_user.is_authenticated else None
        common = {
            "user_id": int(user_id) if user_id else None,
            "session_id": _session_id(),
            "endpoint": request.url_rule.rule if request.url_rule else request.path,
            "http_method": request.method,
            "input_data": collect_input_data(),
            "label": None,
        }
        rows = [{**common, **entry} for entry in entries]

        # Lepas lock transaksi aplikasi yang belum di-commit (mis. request gagal di tengah),
        # supaya INSERT lewat koneksi terpisah tidak menunggu lock milik request ini sendiri.
        db.session.rollback()

        try:
            with engine.begin() as conn:
                conn.execute(insert(ActivityLog.__table__), rows)
        except Exception:
            logger.exception("Gagal menulis activity log (%d entri)", len(rows))


def init_activity_logger(app, db):
    with app.app_context():
        engine = db.engine

    event.listen(engine, "before_cursor_execute", _before_cursor_execute)
    event.listen(engine, "after_cursor_execute", _after_cursor_execute)
    event.listen(engine, "handle_error", _handle_error)

    @app.after_request
    def _ensure_session_id(response):
        # Session cookie harus di-set sebelum response dikirim, jadi sid dibuat di sini.
        if g.get("_activity_log_entries"):
            _session_id()
        return response

    @app.teardown_request
    def _flush_activity_log(exc):
        _flush(engine, db)
