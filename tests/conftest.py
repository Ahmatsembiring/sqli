import pytest

from app import create_app, db
from app.config import TestConfig
from app.models import Role, User

ADMIN_PASSWORD = "admin-test-pass"
USER_PASSWORD = "user-test-pass"


@pytest.fixture
def app():
    app = create_app(TestConfig)
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        db.drop_all()
        db.create_all()

        admin = User(username="admin", email="admin@test.local", role=Role.ADMIN)
        admin.set_password(ADMIN_PASSWORD)
        user = User(username="user", email="user@test.local", role=Role.USER)
        user.set_password(USER_PASSWORD)
        db.session.add_all([admin, user])
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, username, password):
    return client.post("/login", data={"username": username, "password": password})
