from sqlalchemy import text

from app import create_app, db
from app.config import TestConfig
from app.models import User
from tests.conftest import ADMIN_PASSWORD, USER_PASSWORD, login


def test_database_connection(app):
    assert db.session.execute(text("SELECT 1")).scalar() == 1


def test_login_page_renders(client):
    resp = client.get("/login")
    assert resp.status_code == 200
    assert b"Login" in resp.data


def test_admin_login_redirects_to_admin_dashboard(client):
    resp = login(client, "admin", ADMIN_PASSWORD)
    assert resp.status_code == 302
    assert client.get(resp.headers["Location"], follow_redirects=True).request.path == "/admin/dashboard"

    resp = client.get("/admin/dashboard")
    assert resp.status_code == 200
    assert b"Admin Dashboard" in resp.data
    assert b"admin" in resp.data


def test_user_login_redirects_to_user_dashboard(client):
    resp = login(client, "user", USER_PASSWORD)
    assert resp.status_code == 302
    assert client.get(resp.headers["Location"], follow_redirects=True).request.path == "/user/dashboard"

    resp = client.get("/user/dashboard")
    assert resp.status_code == 200
    assert b"User Dashboard" in resp.data
    assert b"Normal Activity" in resp.data
    assert b"SQL Injection Lab" in resp.data


def test_wrong_password_rejected(client):
    resp = login(client, "admin", "salah")
    assert resp.status_code == 401
    assert client.get("/admin/dashboard").status_code == 302  # belum login -> ke /login


def test_user_cannot_open_admin_dashboard(client):
    login(client, "user", USER_PASSWORD)
    assert client.get("/admin/dashboard").status_code == 403


def test_admin_not_routed_to_user_dashboard(client):
    login(client, "admin", ADMIN_PASSWORD)
    assert client.get("/user/dashboard").status_code == 403


def test_anonymous_redirected_to_login(client):
    for path in ("/admin/dashboard", "/user/dashboard"):
        resp = client.get(path)
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]


def test_logout(client):
    login(client, "user", USER_PASSWORD)
    assert client.get("/user/dashboard").status_code == 200

    resp = client.post("/logout")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
    assert client.get("/user/dashboard").status_code == 302


def test_logout_requires_post(client):
    login(client, "user", USER_PASSWORD)
    assert client.get("/logout").status_code == 405


def test_password_not_stored_plaintext(app):
    for user, password in (("admin", ADMIN_PASSWORD), ("user", USER_PASSWORD)):
        stored = db.session.execute(
            text("SELECT password_hash FROM users WHERE username = :u"), {"u": user}
        ).scalar()
        assert stored != password
        assert password not in stored
        assert stored.startswith(("scrypt:", "pbkdf2:"))


def test_csrf_enforced_on_login():
    app = create_app(TestConfig)  # CSRF aktif (default)
    with app.app_context():
        db.create_all()
        resp = app.test_client().post("/login", data={"username": "admin", "password": "x"})
        assert resp.status_code == 400
        db.session.remove()
        db.drop_all()


def test_role_enum_values(app):
    roles = {u.role.value for u in db.session.execute(db.select(User)).scalars()}
    assert roles == {"ADMIN", "USER"}
