"""Inisialisasi schema database dan (opsional) seed akun awal.

Pemakaian:
    python scripts/init_db.py           # buat tabel yang belum ada
    python scripts/init_db.py --seed    # buat tabel + akun seed admin & user
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app import create_app, db  # noqa: E402
from app.models import Role, User  # noqa: E402

SEED_ACCOUNTS = [
    ("admin", "admin@lab.local", Role.ADMIN, "SEED_ADMIN_PASSWORD"),
    ("user", "user@lab.local", Role.USER, "SEED_USER_PASSWORD"),
]


def seed():
    for username, email, role, password_env in SEED_ACCOUNTS:
        if db.session.execute(db.select(User).filter_by(username=username)).scalar_one_or_none():
            print(f"  - {username}: sudah ada, dilewati")
            continue
        password = os.getenv(password_env)
        if not password:
            sys.exit(f"{password_env} belum diset di .env")
        user = User(username=username, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        print(f"  - {username}: dibuat ({role.value})")
    db.session.commit()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", action="store_true", help="buat akun seed admin & user")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        version = db.session.execute(text("SELECT VERSION()")).scalar()
        print(f"Terhubung ke database: {version}")

        db.create_all()
        print("Schema siap: users")

        if args.seed:
            print("Seed akun:")
            seed()


if __name__ == "__main__":
    main()
