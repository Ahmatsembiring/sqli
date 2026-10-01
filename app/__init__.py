from flask import Flask, g, redirect, url_for
from flask_login import LoginManager, current_user
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_class=None):
    if config_class is None:
        from app.config import Config
        config_class = Config

    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Silakan login terlebih dahulu."
    login_manager.login_message_category = "warning"

    from app.models import User
    from app.services import activity_logger

    @login_manager.user_loader
    def load_user(user_id):
        # Query pemuatan session login adalah infrastruktur, bukan aktivitas user -> tidak direkam.
        with activity_logger.suspended():
            return db.session.get(User, int(user_id))

    activity_logger.init_activity_logger(app, db)

    @app.before_request
    def _forget_cached_user():
        # Di produksi g sudah baru tiap request; ini menyamakan perilaku saat app context dipakai ulang
        # (mis. test client), agar user selalu dimuat ulang lewat user_loader yang tidak direkam.
        g.pop("_login_user", None)

    from app.routes.auth import bp as auth_bp
    from app.routes.admin import bp as admin_bp
    from app.routes.user import bp as user_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(user_bp, url_prefix="/user")

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("auth.dashboard_for_role"))
        return redirect(url_for("auth.login"))

    return app
