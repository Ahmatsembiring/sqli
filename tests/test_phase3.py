"""Phase 3 — Activity Logger & halaman admin activity logs."""
import json
from datetime import datetime, timedelta

from app import db
from app.models import ActivityLog, Product, User
from app.services.activity_logger import classify_operation, redact_parameters
from tests.conftest import ADMIN_PASSWORD, USER_PASSWORD, login
from tests.test_phase2 import data  # noqa: F401  (fixture)


def all_logs():
    db.session.expire_all()
    return db.session.execute(db.select(ActivityLog).order_by(ActivityLog.id)).scalars().all()


def logs_for(endpoint):
    return [log for log in all_logs() if log.endpoint == endpoint]


def user_id(username):
    return db.session.execute(db.select(User.id).filter_by(username=username)).scalar_one()


# ---------- Perekaman dasar ----------

def test_activity_logs_table_exists(app):
    columns = {c["name"] for c in db.inspect(db.engine).get_columns("activity_logs")}
    required = {"id", "timestamp", "user_id", "session_id", "endpoint", "http_method", "input_data",
                "query", "operation", "status", "label", "response_time"}
    assert required <= columns


def test_queries_outside_request_not_logged(app, data):
    db.session.execute(db.select(Product)).all()
    assert all_logs() == []


def test_product_search_logged(client, data):
    login(client, "user", USER_PASSWORD)
    client.get("/user/products?q=laptop&category=Laptop")

    logs = logs_for("/user/products")
    assert logs, "pencarian produk harus menghasilkan log"
    search = [log for log in logs if "LIKE" in log.query]
    assert search, [log.query for log in logs]
    log = search[0]

    # Query final berisi nilai input yang sudah di-escape (bukan placeholder %s)
    assert "'%laptop%'" in log.query and "'Laptop'" in log.query
    assert "%s" not in log.query
    assert log.operation.value == "SELECT"
    assert log.status.value == "SUCCESS"
    assert log.http_method == "GET"
    assert log.user_id == user_id("user")
    assert log.session_id and len(log.session_id) == 32
    assert log.label is None
    assert log.response_time >= 0
    assert abs(log.timestamp - datetime.now()) < timedelta(minutes=1)
    assert json.loads(log.input_data) == {"q": "laptop", "category": "Laptop"}


def test_endpoint_uses_route_rule_and_path_params(client, data):
    login(client, "user", USER_PASSWORD)
    pid = data["products"]["Laptop Alpha"].id
    # Session test dipakai bersama request; kosongkan cache identity map seperti session baru di produksi.
    db.session.expire_all()
    client.get(f"/user/products/{pid}")

    logs = logs_for("/user/products/<int:product_id>")
    assert logs
    assert json.loads(logs[0].input_data) == {"product_id": pid}
    assert f"products.id = {pid}" in logs[0].query


def test_purchase_logs_insert_and_update(client, data):
    login(client, "user", USER_PASSWORD)
    pid = data["products"]["Mouse Wireless"].id
    client.post(f"/user/products/{pid}/buy", data={"quantity": "2"})

    ops = {log.operation.value for log in logs_for("/user/products/<int:product_id>/buy")}
    assert {"SELECT", "UPDATE", "INSERT"} <= ops
    for log in logs_for("/user/products/<int:product_id>/buy"):
        assert log.http_method == "POST"


def test_cancel_logs_delete(client, data):
    login(client, "user", USER_PASSWORD)
    pid = data["products"]["Mouse Wireless"].id
    client.post(f"/user/products/{pid}/buy", data={"quantity": "1"})
    trx_id = db.session.execute(db.text("SELECT id FROM transactions")).scalar_one()
    client.post(f"/user/transactions/{trx_id}/cancel")

    ops = {log.operation.value for log in logs_for("/user/transactions/<int:transaction_id>/cancel")}
    assert "DELETE" in ops


def test_failed_query_logged_as_error(client, data):
    login(client, "user", USER_PASSWORD)
    client.post("/user/profile", data={"email": "user2@test.local"})  # duplikat -> IntegrityError

    errors = [log for log in logs_for("/user/profile") if log.status.value == "ERROR"]
    assert len(errors) == 1
    assert errors[0].operation.value == "UPDATE"
    assert "Duplicate" in errors[0].error_message


def test_login_query_logged_with_user(client, data):
    login(client, "user", USER_PASSWORD)
    logs = logs_for("/login")
    assert len(logs) == 1
    assert "'user'" in logs[0].query
    assert logs[0].user_id == user_id("user")


def test_failed_login_logged_without_user(client, data):
    login(client, "user", "password-salah")
    logs = logs_for("/login")
    assert len(logs) == 1 and logs[0].user_id is None


def test_session_id_stable_within_session(client, data):
    login(client, "user", USER_PASSWORD)
    client.get("/user/products")
    client.get("/user/users")
    session_ids = {log.session_id for log in all_logs()}
    assert len(session_ids) == 1


def test_user_loader_queries_not_logged(client, data):
    login(client, "user", USER_PASSWORD)
    client.get("/user/products")
    for log in logs_for("/user/products"):
        assert "FROM users" not in log.query


def test_pages_without_queries_not_logged(client, data):
    client.get("/login")
    client.get("/static/css/style.css")
    assert all_logs() == []


# ---------- Data sensitif ----------

def _all_log_text():
    return " ".join(f"{log.query} {log.input_data or ''} {log.session_id or ''}" for log in all_logs())


def test_login_password_not_logged(client, data):
    login(client, "user", USER_PASSWORD)
    text = _all_log_text()
    assert USER_PASSWORD not in text
    assert '"password": "[REDACTED]"' in logs_for("/login")[0].input_data


def test_password_change_hash_and_plaintext_not_logged(client, data):
    login(client, "user", USER_PASSWORD)
    new_password = "rahasia-baru-123"
    client.post("/user/profile/password", data={
        "current_password": USER_PASSWORD, "new_password": new_password, "confirm_password": new_password,
    })

    stored_hash = db.session.execute(
        db.text("SELECT password_hash FROM users WHERE username = 'user'")
    ).scalar()
    text = _all_log_text()
    assert new_password not in text and USER_PASSWORD not in text
    assert stored_hash not in text
    assert "scrypt:" not in text and "pbkdf2:" not in text

    updates = [log for log in logs_for("/user/profile/password") if log.operation.value == "UPDATE"]
    assert updates and "[REDACTED]" in updates[0].query


def test_csrf_token_and_secrets_not_logged(client, data):
    login(client, "user", USER_PASSWORD)
    client.get("/user/products?csrf_token=abc123&api_secret=xyz&q=mouse")
    log_input = json.loads(logs_for("/user/products")[0].input_data)
    assert "csrf_token" not in log_input
    assert log_input["api_secret"] == "[REDACTED]"
    assert log_input["q"] == "mouse"


def test_redact_parameters_helper():
    assert redact_parameters(("budi", "scrypt:32768:8:1$abc$def")) == ("budi", "[REDACTED]")
    assert redact_parameters({"a": "pbkdf2:sha256:1$x$y", "b": 5}) == {"a": "[REDACTED]", "b": 5}
    assert redact_parameters(None) is None


def test_classify_operation():
    assert classify_operation("SELECT * FROM t") == "SELECT"
    assert classify_operation("  insert into t values (1)") == "INSERT"
    assert classify_operation("(SELECT 1) UNION (SELECT 2)") == "SELECT"
    assert classify_operation("UPDATE t SET a=1") == "UPDATE"
    assert classify_operation("DELETE FROM t") == "DELETE"
    assert classify_operation("SHOW TABLES") == "OTHER"


# ---------- Halaman admin ----------

def test_activity_logs_page_admin_only(client, data):
    assert client.get("/admin/activity-logs").status_code == 302  # anonim -> login
    login(client, "user", USER_PASSWORD)
    assert client.get("/admin/activity-logs").status_code == 403
    client.post("/logout")
    login(client, "admin", ADMIN_PASSWORD)
    assert client.get("/admin/activity-logs").status_code == 200


def test_viewing_activity_logs_does_not_create_logs(client, data):
    login(client, "admin", ADMIN_PASSWORD)
    before = len(all_logs())
    client.get("/admin/activity-logs")
    client.get("/admin/activity-logs?operation=SELECT")
    assert len(all_logs()) == before


def _generate_activity(client, data):
    login(client, "user", USER_PASSWORD)
    client.get("/user/products?q=laptop")
    pid = data["products"]["Mouse Wireless"].id
    client.post(f"/user/products/{pid}/buy", data={"quantity": "1"})
    client.post("/logout")
    login(client, "admin", ADMIN_PASSWORD)
    client.get("/admin/products")


def test_activity_logs_filters(client, data):
    _generate_activity(client, data)
    uid = user_id("user")

    body = client.get(f"/admin/activity-logs?user_id={uid}").data.decode()
    assert "/user/products" in body and "/admin/products" not in body.split("<tbody>")[1]

    body = client.get("/admin/activity-logs?operation=INSERT").data.decode()
    rows = body.split("<tbody>")[1]
    assert "INSERT" in rows and "<td>SELECT</td>" not in rows

    body = client.get("/admin/activity-logs?endpoint=/admin/products").data.decode()
    rows = body.split("<tbody>")[1]
    assert "/admin/products" in rows and "/user/products" not in rows

    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    assert "Belum ada log" not in client.get(f"/admin/activity-logs?date_from={today}&date_to={today}").data.decode()
    assert "Belum ada log" in client.get(f"/admin/activity-logs?date_from={tomorrow}").data.decode()


def test_activity_logs_invalid_filters_ignored(client, data):
    login(client, "admin", ADMIN_PASSWORD)
    resp = client.get("/admin/activity-logs?user_id=abc&operation=DROP&date_from=kemarin&page=-3")
    assert resp.status_code == 200


def test_activity_logs_pagination(client, data):
    login(client, "user", USER_PASSWORD)
    for _ in range(30):
        client.get("/user/products")
    client.post("/logout")
    login(client, "admin", ADMIN_PASSWORD)
    body = client.get("/admin/activity-logs").data.decode()
    assert "Halaman 1 /" in body
    assert client.get("/admin/activity-logs?page=2").status_code == 200


def test_activity_log_detail(client, data):
    login(client, "user", USER_PASSWORD)
    client.get("/user/products?q=mouse")
    log = logs_for("/user/products")[0]
    client.post("/logout")

    login(client, "admin", ADMIN_PASSWORD)
    resp = client.get(f"/admin/activity-logs/{log.id}")
    assert resp.status_code == 200
    assert b"Belum dilabeli" in resp.data and b"mouse" in resp.data
    assert client.get("/admin/activity-logs/999999").status_code == 404


def test_activity_log_detail_forbidden_for_user(client, data):
    login(client, "user", USER_PASSWORD)
    client.get("/user/products")
    log_id = logs_for("/user/products")[0].id
    assert client.get(f"/admin/activity-logs/{log_id}").status_code == 403
