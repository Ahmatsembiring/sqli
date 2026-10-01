# SQLi Research Lab

Lingkungan laboratorium **lokal** untuk penelitian Tugas Akhir:

> *Deteksi Serangan SQL Injection Real-Time Menggunakan Analisis N-Gram dan Algoritma Random Forest pada Log Aktivitas Database*

> ⚠️ Aplikasi ini akan memuat endpoint yang **sengaja dibuat rentan** (pada fase berikutnya).
> Jalankan hanya di `localhost` atau jaringan lab yang terisolasi. Jangan pernah di-deploy ke internet.
> `run.py` menolak bind ke alamat selain loopback.

## Status: Phase 2 — Normal Application

Fitur yang sudah ada:

- **Phase 1:** login, logout, role `ADMIN`/`USER`, dashboard per role.
- **Phase 2 (USER):** profil (ubah email, ganti password), daftar & cari user (tanpa email user lain),
  daftar/cari/filter produk (kategori, rentang harga, stok, urutan, pagination), detail produk,
  beli produk, riwayat & pembatalan transaksi milik sendiri.
- **Phase 2 (ADMIN):** daftar & cari user, CRUD produk.

Tabel: `users`, `products`, `transactions`. Semua akses database lewat SQLAlchemy (parameterized),
sehingga dapat diamati oleh Activity Logger pada fase berikutnya.

## Teknologi

| Lapisan | Pilihan |
|---|---|
| Backend | Python 3.14, Flask 3.1 |
| ORM | Flask-SQLAlchemy 3.1 / SQLAlchemy 2.1 |
| Driver DB | PyMySQL |
| Database | MariaDB 10.4+ (XAMPP) / MySQL 8 |
| Auth | Flask-Login, password hashing `werkzeug` (scrypt), CSRF Flask-WTF |
| Frontend | Jinja2 + HTML/CSS/JS sederhana |
| Test | pytest |

## Struktur

```
app/
  __init__.py          app factory, registrasi extension & blueprint
  config.py            konfigurasi dari environment variable (.env)
  models/              User (+ enum Role), Product, Transaction
  services/catalog.py  pencarian/filter produk & user
  services/shop.py     beli & batalkan transaksi (dengan penguncian stok)
  routes/auth.py       /login, /logout, /dashboard (redirect sesuai role)
  routes/admin.py      /admin/* (ADMIN saja): dashboard, users, products CRUD
  routes/user.py       /user/*  (USER saja): dashboard, profile, users, products, transactions
  routes/decorators.py role_required()
  templates/           base, _macros, auth/, admin/, user/
  static/              css/style.css, js/app.js
scripts/init_db.py     buat tabel + seed akun & katalog produk contoh
tests/                 pytest per phase
run.py                 entry point (hanya localhost)
```

## Setup

1. Jalankan MariaDB (XAMPP Control Panel → MySQL → Start).
2. Buat database dan akun DB khusus aplikasi (jangan pakai root di aplikasi):

   ```sql
   CREATE DATABASE sqli_lab      CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE DATABASE sqli_lab_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'sqli_lab_app'@'localhost' IDENTIFIED BY '<password>';
   CREATE USER 'sqli_lab_app'@'127.0.0.1' IDENTIFIED BY '<password>';
   GRANT ALL PRIVILEGES ON sqli_lab.*      TO 'sqli_lab_app'@'localhost', 'sqli_lab_app'@'127.0.0.1';
   GRANT ALL PRIVILEGES ON sqli_lab_test.* TO 'sqli_lab_app'@'localhost', 'sqli_lab_app'@'127.0.0.1';
   ```

3. Salin `.env.example` menjadi `.env`, lalu isi password DB, `FLASK_SECRET_KEY`, dan password seed.
4. Install dependency dan inisialisasi database:

   ```powershell
   python -m venv venv
   .\venv\Scripts\pip install -r requirements.txt
   .\venv\Scripts\python scripts\init_db.py --seed
   ```

5. Jalankan aplikasi:

   ```powershell
   .\venv\Scripts\python run.py
   ```

   Buka http://127.0.0.1:5000

## Akun seed

| Username | Role | Password |
|---|---|---|
| `admin` | ADMIN | nilai `SEED_ADMIN_PASSWORD` di `.env` |
| `user` | USER | nilai `SEED_USER_PASSWORD` di `.env` |

## Test

```powershell
.\venv\Scripts\python -m pytest -v
```

Test memakai database terpisah (`DB_TEST_NAME`), yang dikosongkan setiap kali test berjalan.
