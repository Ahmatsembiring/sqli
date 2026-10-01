from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app import db
from app.models import Role, User

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("auth.dashboard_for_role"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = db.session.execute(
            db.select(User).filter_by(username=username)
        ).scalar_one_or_none()

        if user is None or not user.check_password(password):
            flash("Username atau password salah.", "danger")
            return render_template("auth/login.html", username=username), 401

        login_user(user)
        return redirect(url_for("auth.dashboard_for_role"))

    return render_template("auth/login.html")


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Anda telah logout.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/dashboard")
@login_required
def dashboard_for_role():
    if current_user.role == Role.ADMIN:
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("user.dashboard"))
