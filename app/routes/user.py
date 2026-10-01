from flask import Blueprint, render_template

from app.models import Role
from app.routes.decorators import role_required

bp = Blueprint("user", __name__)


@bp.route("/dashboard")
@role_required(Role.USER)
def dashboard():
    return render_template("user/dashboard.html")
