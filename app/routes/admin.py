from flask import Blueprint, render_template

from app.models import Role
from app.routes.decorators import role_required

bp = Blueprint("admin", __name__)


@bp.route("/dashboard")
@role_required(Role.ADMIN)
def dashboard():
    return render_template("admin/dashboard.html")
