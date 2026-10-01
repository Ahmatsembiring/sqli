from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import Product, Role, User
from app.routes.decorators import role_required
from app.services import catalog, shop

bp = Blueprint("user", __name__)

MIN_PASSWORD_LENGTH = 8


@bp.route("/dashboard")
@role_required(Role.USER)
def dashboard():
    recent = shop.user_transactions(current_user)[:5]
    return render_template("user/dashboard.html", recent_transactions=recent)


# ---------- Profile ----------

@bp.route("/profile", methods=["GET", "POST"])
@role_required(Role.USER)
def profile():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        if "@" not in email or len(email) > 120:
            flash("Email tidak valid.", "danger")
        else:
            current_user.email = email
            try:
                db.session.commit()
                flash("Profil diperbarui.", "info")
            except IntegrityError:
                db.session.rollback()
                flash("Email sudah dipakai akun lain.", "danger")
        return redirect(url_for("user.profile"))

    return render_template("user/profile.html")


@bp.route("/profile/password", methods=["POST"])
@role_required(Role.USER)
def change_password():
    current = request.form.get("current_password", "")
    new = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")

    if not current_user.check_password(current):
        flash("Password saat ini salah.", "danger")
    elif len(new) < MIN_PASSWORD_LENGTH:
        flash(f"Password baru minimal {MIN_PASSWORD_LENGTH} karakter.", "danger")
    elif new != confirm:
        flash("Konfirmasi password tidak cocok.", "danger")
    else:
        current_user.set_password(new)
        db.session.commit()
        flash("Password berhasil diganti.", "info")
    return redirect(url_for("user.profile"))


# ---------- User directory ----------

@bp.route("/users")
@role_required(Role.USER)
def users():
    q = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    return render_template("user/users.html", q=q, pagination=catalog.search_users(q, page))


@bp.route("/users/<int:user_id>")
@role_required(Role.USER)
def user_detail(user_id):
    user = db.get_or_404(User, user_id)
    return render_template("user/user_detail.html", user=user)


# ---------- Products ----------

@bp.route("/products")
@role_required(Role.USER)
def products():
    filters = catalog.parse_product_filters(request.args)
    page = request.args.get("page", 1, type=int)
    return render_template(
        "user/products.html",
        filters=filters,
        categories=catalog.product_categories(),
        pagination=catalog.search_products(filters, page),
    )


@bp.route("/products/<int:product_id>")
@role_required(Role.USER)
def product_detail(product_id):
    product = db.get_or_404(Product, product_id)
    return render_template("user/product_detail.html", product=product, max_qty=shop.MAX_QUANTITY)


@bp.route("/products/<int:product_id>/buy", methods=["POST"])
@role_required(Role.USER)
def buy(product_id):
    quantity = request.form.get("quantity", type=int) or 0
    try:
        trx = shop.purchase(current_user, product_id, quantity)
    except shop.ShopError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("user.product_detail", product_id=product_id))
    flash(f"Transaksi #{trx.id} berhasil.", "info")
    return redirect(url_for("user.transactions"))


# ---------- Transactions ----------

@bp.route("/transactions")
@role_required(Role.USER)
def transactions():
    return render_template("user/transactions.html", transactions=shop.user_transactions(current_user))


@bp.route("/transactions/<int:transaction_id>/cancel", methods=["POST"])
@role_required(Role.USER)
def cancel_transaction(transaction_id):
    try:
        shop.cancel(current_user, transaction_id)
    except shop.ShopError:
        abort(404)
    flash(f"Transaksi #{transaction_id} dibatalkan.", "info")
    return redirect(url_for("user.transactions"))
