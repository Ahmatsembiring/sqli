"""Phase 2 — fitur aplikasi normal: profil, user, produk, transaksi."""
import pytest

from app import db
from app.models import Product, Role, Transaction, User
from tests.conftest import ADMIN_PASSWORD, USER_PASSWORD, login

USER2_PASSWORD = "user2-test-pass"

TEST_PRODUCTS = [
    # (name, category, description, price, stock)
    ("Laptop Alpha", "Laptop", "Laptop 14 inci ringan", 8000000, 5),
    ("Laptop Beta", "Laptop", "Laptop gaming", 15000000, 0),
    ("Mouse Wireless", "Aksesoris", "Mouse nirkabel", 150000, 50),
    ("Keyboard Mekanikal", "Aksesoris", "Keyboard switch red", 550000, 10),
]


@pytest.fixture
def data(app):
    user2 = User(username="user2", email="user2@test.local", role=Role.USER)
    user2.set_password(USER2_PASSWORD)
    db.session.add(user2)
    products = {}
    for name, category, description, price, stock in TEST_PRODUCTS:
        p = Product(name=name, category=category, description=description, price=price, stock=stock)
        db.session.add(p)
        products[name] = p
    db.session.commit()
    return {"user2": user2, "products": products}


def as_user(client):
    login(client, "user", USER_PASSWORD)
    return client


def as_admin(client):
    login(client, "admin", ADMIN_PASSWORD)
    return client


def get_user(username):
    return db.session.execute(db.select(User).filter_by(username=username)).scalar_one()


# ---------- Authorization ----------

USER_PAGES = ["/user/profile", "/user/users", "/user/products", "/user/transactions"]
ADMIN_PAGES = ["/admin/users", "/admin/products", "/admin/products/new"]


def test_anonymous_redirected_from_all_pages(client, data):
    for path in USER_PAGES + ADMIN_PAGES:
        resp = client.get(path)
        assert resp.status_code == 302, path
        assert "/login" in resp.headers["Location"]


def test_user_pages_ok_admin_pages_forbidden(client, data):
    as_user(client)
    for path in USER_PAGES:
        assert client.get(path).status_code == 200, path
    for path in ADMIN_PAGES:
        assert client.get(path).status_code == 403, path


def test_admin_pages_ok_user_pages_forbidden(client, data):
    as_admin(client)
    for path in ADMIN_PAGES:
        assert client.get(path).status_code == 200, path
    for path in USER_PAGES:
        assert client.get(path).status_code == 403, path


def test_user_cannot_modify_products(client, data):
    as_user(client)
    pid = data["products"]["Mouse Wireless"].id
    form = {"name": "x", "category": "x", "price": "1", "stock": "1"}
    assert client.post("/admin/products/new", data=form).status_code == 403
    assert client.post(f"/admin/products/{pid}/edit", data=form).status_code == 403
    assert client.post(f"/admin/products/{pid}/delete").status_code == 403
    assert db.session.get(Product, pid) is not None


# ---------- Search & filter ----------

def test_product_search_by_name(client, data):
    resp = as_user(client).get("/user/products?q=laptop")
    assert b"Laptop Alpha" in resp.data and b"Laptop Beta" in resp.data
    assert b"Mouse Wireless" not in resp.data


def test_product_search_matches_description(client, data):
    resp = as_user(client).get("/user/products?q=nirkabel")
    assert b"Mouse Wireless" in resp.data
    assert b"Laptop Alpha" not in resp.data


def test_product_filter_category_price_stock(client, data):
    as_user(client)
    resp = client.get("/user/products?category=Aksesoris&max_price=200000")
    assert b"Mouse Wireless" in resp.data and b"Keyboard Mekanikal" not in resp.data

    resp = client.get("/user/products?category=Laptop&in_stock=1")
    assert b"Laptop Alpha" in resp.data and b"Laptop Beta" not in resp.data


def test_product_filter_ignores_invalid_values(client, data):
    resp = as_user(client).get("/user/products?min_price=abc&max_price=-5&sort=evil&page=999")
    assert resp.status_code == 200


def test_product_sort_by_price(client, data):
    body = as_user(client).get("/user/products?sort=price_desc").data.decode()
    assert body.index("Laptop Beta") < body.index("Laptop Alpha") < body.index("Mouse Wireless")


def test_product_detail_and_404(client, data):
    as_user(client)
    pid = data["products"]["Laptop Alpha"].id
    resp = client.get(f"/user/products/{pid}")
    assert resp.status_code == 200 and b"Laptop 14 inci ringan" in resp.data
    assert client.get("/user/products/999999").status_code == 404


def test_user_search(client, data):
    resp = as_user(client).get("/user/users?q=user2")
    assert b"user2" in resp.data
    assert b"admin" not in resp.data.split(b"<main")[1]  # di luar header


def test_user_directory_hides_other_users_email(client, data):
    as_user(client)
    assert b"user2@test.local" not in client.get("/user/users").data
    assert b"user2@test.local" not in client.get(f"/user/users/{data['user2'].id}").data


def test_admin_user_list_shows_email(client, data):
    resp = as_admin(client).get("/admin/users?q=user2")
    assert b"user2@test.local" in resp.data


# ---------- Transactions (CRUD) ----------

def test_purchase_creates_transaction_and_reduces_stock(client, data):
    as_user(client)
    pid = data["products"]["Laptop Alpha"].id
    resp = client.post(f"/user/products/{pid}/buy", data={"quantity": "2"})
    assert resp.status_code == 302

    trx = db.session.execute(db.select(Transaction)).scalar_one()
    assert trx.user_id == get_user("user").id and trx.quantity == 2
    db.session.refresh(data["products"]["Laptop Alpha"])
    assert data["products"]["Laptop Alpha"].stock == 3
    assert b"Laptop Alpha" in client.get("/user/transactions").data


@pytest.mark.parametrize("qty", ["0", "-1", "101", "abc", ""])
def test_purchase_rejects_invalid_quantity(client, data, qty):
    as_user(client)
    pid = data["products"]["Mouse Wireless"].id
    client.post(f"/user/products/{pid}/buy", data={"quantity": qty})
    assert db.session.execute(db.select(db.func.count()).select_from(Transaction)).scalar() == 0


def test_purchase_rejects_insufficient_stock(client, data):
    as_user(client)
    pid = data["products"]["Laptop Beta"].id  # stok 0
    client.post(f"/user/products/{pid}/buy", data={"quantity": "1"})
    assert db.session.execute(db.select(db.func.count()).select_from(Transaction)).scalar() == 0
    db.session.refresh(data["products"]["Laptop Beta"])
    assert data["products"]["Laptop Beta"].stock == 0


def test_cancel_transaction_restores_stock(client, data):
    as_user(client)
    pid = data["products"]["Keyboard Mekanikal"].id
    client.post(f"/user/products/{pid}/buy", data={"quantity": "4"})
    trx_id = db.session.execute(db.select(Transaction.id)).scalar_one()

    assert client.post(f"/user/transactions/{trx_id}/cancel").status_code == 302
    assert db.session.get(Transaction, trx_id) is None
    db.session.refresh(data["products"]["Keyboard Mekanikal"])
    assert data["products"]["Keyboard Mekanikal"].stock == 10


def test_admin_product_create_edit_delete(client, data):
    as_admin(client)
    form = {"name": "Webcam Test", "category": "Aksesoris", "description": "HD", "price": "250000", "stock": "7"}
    assert client.post("/admin/products/new", data=form).status_code == 302
    product = db.session.execute(db.select(Product).filter_by(name="Webcam Test")).scalar_one()
    assert product.stock == 7

    form.update(price="275000", stock="3")
    assert client.post(f"/admin/products/{product.id}/edit", data=form).status_code == 302
    db.session.refresh(product)
    assert product.price == 275000 and product.stock == 3

    assert client.post(f"/admin/products/{product.id}/delete").status_code == 302
    db.session.expire_all()
    assert db.session.get(Product, product.id) is None


def test_admin_product_validation(client, data):
    as_admin(client)
    bad = {"name": "", "category": "X", "price": "-1", "stock": "abc"}
    assert client.post("/admin/products/new", data=bad).status_code == 400
    assert db.session.execute(db.select(Product).filter_by(category="X")).first() is None


def test_admin_cannot_delete_product_with_transactions(client, data):
    pid = data["products"]["Mouse Wireless"].id
    as_user(client).post(f"/user/products/{pid}/buy", data={"quantity": "1"})
    client.post("/logout")

    as_admin(client).post(f"/admin/products/{pid}/delete")
    db.session.expire_all()
    assert db.session.get(Product, pid) is not None


# ---------- Profile ----------

def test_profile_update_email(client, data):
    as_user(client).post("/user/profile", data={"email": "baru@test.local"})
    assert get_user("user").email == "baru@test.local"


def test_profile_rejects_duplicate_email(client, data):
    as_user(client).post("/user/profile", data={"email": "user2@test.local"})
    assert get_user("user").email == "user@test.local"


def test_change_password(client, data):
    as_user(client)
    client.post("/user/profile/password", data={
        "current_password": USER_PASSWORD, "new_password": "password-baru-1", "confirm_password": "password-baru-1",
    })
    client.post("/logout")
    assert login(client, "user", USER_PASSWORD).status_code == 401
    assert login(client, "user", "password-baru-1").status_code == 302


def test_change_password_requires_current_password(client, data):
    as_user(client).post("/user/profile/password", data={
        "current_password": "salah", "new_password": "password-baru-1", "confirm_password": "password-baru-1",
    })
    db.session.expire_all()
    assert get_user("user").check_password(USER_PASSWORD)


# ---------- User isolation ----------

def test_user_only_sees_own_transactions(client, data):
    pid = data["products"]["Mouse Wireless"].id
    trx = Transaction(user_id=data["user2"].id, product_id=pid, quantity=3)
    db.session.add(trx)
    db.session.commit()

    resp = as_user(client).get("/user/transactions")
    assert b"Belum ada transaksi" in resp.data


def test_user_cannot_cancel_other_users_transaction(client, data):
    pid = data["products"]["Mouse Wireless"].id
    trx = Transaction(user_id=data["user2"].id, product_id=pid, quantity=3)
    db.session.add(trx)
    db.session.commit()

    assert as_user(client).post(f"/user/transactions/{trx.id}/cancel").status_code == 404
    db.session.expire_all()
    assert db.session.get(Transaction, trx.id) is not None


def test_profile_edit_only_affects_current_user(client, data):
    as_user(client).post("/user/profile", data={"email": "lain@test.local", "user_id": data["user2"].id})
    assert get_user("user2").email == "user2@test.local"


def test_schema_has_phase2_tables(app):
    tables = set(db.inspect(db.engine).get_table_names())
    assert {"users", "products", "transactions"} <= tables
