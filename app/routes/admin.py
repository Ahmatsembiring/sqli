from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app import db
from app.models import Product, Role, Transaction
from app.routes.decorators import role_required
from app.services import catalog

bp = Blueprint("admin", __name__)


@bp.route("/dashboard")
@role_required(Role.ADMIN)
def dashboard():
    return render_template("admin/dashboard.html")


# ---------- Users ----------

@bp.route("/users")
@role_required(Role.ADMIN)
def users():
    q = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    return render_template("admin/users.html", q=q, pagination=catalog.search_users(q, page))


# ---------- Products ----------

def _product_form_data(form):
    """Validasi form produk. Mengembalikan (data, errors)."""
    errors = []
    data = {
        "name": form.get("name", "").strip(),
        "category": form.get("category", "").strip(),
        "description": form.get("description", "").strip(),
    }
    if not data["name"] or len(data["name"]) > 120:
        errors.append("Nama wajib diisi (maks. 120 karakter).")
    if not data["category"] or len(data["category"]) > 50:
        errors.append("Kategori wajib diisi (maks. 50 karakter).")

    try:
        data["price"] = Decimal(form.get("price", ""))
        if data["price"] < 0:
            raise InvalidOperation
    except InvalidOperation:
        errors.append("Harga harus angka >= 0.")

    try:
        data["stock"] = int(form.get("stock", ""))
        if data["stock"] < 0:
            raise ValueError
    except ValueError:
        errors.append("Stok harus bilangan bulat >= 0.")

    return data, errors


@bp.route("/products")
@role_required(Role.ADMIN)
def products():
    filters = catalog.parse_product_filters(request.args)
    page = request.args.get("page", 1, type=int)
    return render_template(
        "admin/products.html",
        filters=filters,
        categories=catalog.product_categories(),
        pagination=catalog.search_products(filters, page),
    )


@bp.route("/products/new", methods=["GET", "POST"])
@role_required(Role.ADMIN)
def product_create():
    if request.method == "POST":
        data, errors = _product_form_data(request.form)
        if not errors:
            product = Product(**data)
            db.session.add(product)
            db.session.commit()
            flash(f"Produk '{product.name}' ditambahkan.", "info")
            return redirect(url_for("admin.products"))
        for err in errors:
            flash(err, "danger")
        return render_template("admin/product_form.html", product=None, form=request.form), 400
    return render_template("admin/product_form.html", product=None, form={})


@bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@role_required(Role.ADMIN)
def product_edit(product_id):
    product = db.get_or_404(Product, product_id)
    if request.method == "POST":
        data, errors = _product_form_data(request.form)
        if not errors:
            for key, value in data.items():
                setattr(product, key, value)
            db.session.commit()
            flash(f"Produk '{product.name}' diperbarui.", "info")
            return redirect(url_for("admin.products"))
        for err in errors:
            flash(err, "danger")
        return render_template("admin/product_form.html", product=product, form=request.form), 400

    form = {
        "name": product.name,
        "category": product.category,
        "description": product.description or "",
        "price": product.price,
        "stock": product.stock,
    }
    return render_template("admin/product_form.html", product=product, form=form)


@bp.route("/products/<int:product_id>/delete", methods=["POST"])
@role_required(Role.ADMIN)
def product_delete(product_id):
    product = db.get_or_404(Product, product_id)
    used = db.session.execute(
        db.select(db.func.count()).select_from(Transaction).where(Transaction.product_id == product.id)
    ).scalar()
    if used:
        flash(f"Produk '{product.name}' tidak bisa dihapus: dipakai di {used} transaksi.", "danger")
        return redirect(url_for("admin.products"))

    db.session.delete(product)
    db.session.commit()
    flash(f"Produk '{product.name}' dihapus.", "info")
    return redirect(url_for("admin.products"))
