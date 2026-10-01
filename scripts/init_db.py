"""Inisialisasi schema database dan (opsional) seed data awal aplikasi.

Pemakaian:
    python scripts/init_db.py           # buat tabel yang belum ada
    python scripts/init_db.py --seed    # buat tabel + akun seed + katalog produk contoh

Catatan: data seed adalah isi katalog aplikasi, BUKAN dataset penelitian.
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app import create_app, db  # noqa: E402
from app.models import Product, Role, User  # noqa: E402

SEED_ACCOUNTS = [
    ("admin", "admin@lab.local", Role.ADMIN, "SEED_ADMIN_PASSWORD"),
    ("user", "user@lab.local", Role.USER, "SEED_USER_PASSWORD"),
]

# (nama, kategori, deskripsi, harga, stok)
SEED_PRODUCTS = [
    ("Laptop Aspire 5", "Laptop", "Laptop 14 inci, Core i5, RAM 8GB, SSD 512GB.", 8499000, 12),
    ("Laptop ThinkBook 14", "Laptop", "Laptop bisnis 14 inci, Ryzen 5, RAM 16GB.", 10250000, 7),
    ("Laptop VivoBook Go", "Laptop", "Laptop ringan 15 inci untuk kuliah.", 5899000, 20),
    ("Mouse Wireless M185", "Aksesoris", "Mouse nirkabel 2.4GHz dengan receiver USB.", 149000, 85),
    ("Mouse Gaming G102", "Aksesoris", "Mouse gaming RGB 8000 DPI.", 279000, 40),
    ("Keyboard Mekanikal K87", "Aksesoris", "Keyboard tenkeyless, switch red.", 549000, 25),
    ("Keyboard Wireless K380", "Aksesoris", "Keyboard bluetooth multi-device.", 459000, 30),
    ("Monitor 24 inci IPS", "Monitor", "Monitor Full HD 75Hz panel IPS.", 1650000, 15),
    ("Monitor 27 inci QHD", "Monitor", "Monitor 2560x1440 165Hz.", 3899000, 6),
    ("SSD NVMe 512GB", "Penyimpanan", "SSD M.2 NVMe Gen3, baca hingga 3500MB/s.", 689000, 50),
    ("SSD SATA 1TB", "Penyimpanan", "SSD 2.5 inci SATA III.", 1049000, 18),
    ("Flashdisk 64GB", "Penyimpanan", "USB 3.2 flashdisk 64GB.", 89000, 120),
    ("Harddisk Eksternal 2TB", "Penyimpanan", "HDD portabel USB 3.0.", 1150000, 10),
    ("Headset USB H390", "Audio", "Headset USB dengan mikrofon noise-cancelling.", 399000, 22),
    ("Speaker Bluetooth Mini", "Audio", "Speaker portabel tahan air IPX5.", 329000, 35),
    ("Webcam HD 1080p", "Aksesoris", "Webcam Full HD dengan mikrofon stereo.", 525000, 14),
    ("Router WiFi AX1500", "Jaringan", "Router WiFi 6 dual band.", 899000, 9),
    ("Switch 8 Port Gigabit", "Jaringan", "Switch unmanaged 8 port 10/100/1000.", 299000, 16),
    ("Kabel LAN Cat6 10m", "Jaringan", "Kabel UTP Cat6 dengan konektor RJ45.", 65000, 0),
    ("Printer Ink Tank L3210", "Printer", "Printer multifungsi print/scan/copy.", 2299000, 5),
]


def seed_products():
    if db.session.execute(db.select(db.func.count()).select_from(Product)).scalar():
        print("  - produk: sudah ada, dilewati")
        return
    for name, category, description, price, stock in SEED_PRODUCTS:
        db.session.add(Product(name=name, category=category, description=description, price=price, stock=stock))
    db.session.commit()
    print(f"  - produk: {len(SEED_PRODUCTS)} dibuat")


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
        print("Schema siap:", ", ".join(sorted(db.metadata.tables)))

        if args.seed:
            print("Seed data:")
            seed()
            seed_products()


if __name__ == "__main__":
    main()
