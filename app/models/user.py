import enum
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db


class Role(str, enum.Enum):
    ADMIN = "ADMIN"
    USER = "USER"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    email = db.Column(db.String(120), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(
        db.Enum(Role, name="user_role", values_callable=lambda e: [r.value for r in e]),
        nullable=False,
        default=Role.USER,
    )
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    def set_password(self, password):
        # werkzeug default: scrypt dengan salt acak
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == Role.ADMIN

    def __repr__(self):
        return f"<User {self.username} ({self.role.value})>"
