# SQLi Research Lab

Lingkungan laboratorium **lokal** untuk penelitian Tugas Akhir:

> *Deteksi Serangan SQL Injection Real-Time Menggunakan Analisis N-Gram dan Algoritma Random Forest pada Log Aktivitas Database*

> ⚠️ Aplikasi ini akan memuat endpoint yang **sengaja dibuat rentan** (pada fase berikutnya).
> Jalankan hanya di `localhost` atau jaringan lab yang terisolasi. Jangan pernah di-deploy ke internet.
> `run.py` menolak bind ke alamat selain loopback.

## Status: Phase 3 — Activity Logger

Fitur yang sudah ada:

- **Phase 1:** login, logout, role `ADMIN`/`USER`, dashboard per role.
- **Phase 2 (USER):** profil (ubah email, ganti password), daftar & cari user (tanpa email user lain),
  daftar/cari/filter produk (kategori, rentang harga, stok, urutan, pagination), detail produk,
  beli produk, riwayat & pembatalan transaksi milik sendiri.
- **Phase 2 (ADMIN):** daftar & cari user, CRUD produk.

- **Phase 3:** activity logger untuk setiap query SQL selama HTTP request + halaman admin
  `/admin/activity-logs` (pagination, filter user/endpoint/operasi/tanggal, detail).

Tabel: `users`, `products`, `transactions`, `activity_logs`.

## Activity logging

Setiap query SQL yang dieksekusi aplikasi selama satu HTTP request menjadi satu baris `activity_logs`.

| Kolom | Isi |
|---|---|
| `timestamp` | waktu query selesai dieksekusi (presisi milidetik) |
| `user_id` | user yang login saat request (NULL jika anonim / login gagal) |
| `session_id` | ID acak per browser session (bukan cookie session, tidak memberi akses apa pun) |
| `endpoint` | pola route Flask, mis. `/user/products/<int:product_id>` |
| `http_method` | GET / POST |
| `input_data` | JSON berisi path params, query string, dan field form (field sensitif di-redact) |
| `query` | query SQL final yang dikirim ke MariaDB, dirender dengan `cursor.mogrify()` |
| `operation` | SELECT / INSERT / UPDATE / DELETE / OTHER (kata kunci pertama query) |
| `status` | SUCCESS / ERROR (+ `error_message`) |
| `label` | BENIGN / SQL_INJECTION / NULL — selalu NULL pada Phase 3; ground truth ditetapkan di tahap dataset |
| `response_time` | durasi eksekusi query di driver DB dalam ms (**bukan** durasi HTTP request) |

Cara kerja (`app/services/activity_logger.py`): event SQLAlchemy `before_cursor_execute`,
`after_cursor_execute`, dan `handle_error` menangkap query di level driver. Entri dikumpulkan
selama request lalu ditulis sekali di akhir request lewat koneksi terpisah.

Yang **tidak** direkam / disensor:

- field form yang namanya mengandung `password`, `secret`, `token` → `[REDACTED]`; `csrf_token` dibuang;
- nilai parameter SQL berbentuk hash password (`scrypt:` / `pbkdf2:`) → `[REDACTED]`;
- query pemuatan user dari session login (Flask-Login `user_loader`) — infrastruktur, bukan aktivitas user;
- request ke `/static/` dan ke halaman `/admin/activity-logs` (agar membaca log tidak menghasilkan log);
- query di luar HTTP request (`init_db.py`, CLI).

Keterbatasan yang perlu dicatat dalam penelitian:

- Logging dilakukan di **level aplikasi** (driver PyMySQL), bukan general query log MariaDB. Query yang
  dijalankan langsung ke database di luar aplikasi tidak terekam.
- Query yang dihasilkan ORM ikut terekam apa adanya, termasuk lazy-load (mis. halaman transaksi memuat
  produk per baris transaksi). Ini perilaku aplikasi sebenarnya, tetapi menghasilkan banyak query mirip.

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
  models/              User (+ enum Role), Product, Transaction, ActivityLog
  services/catalog.py  pencarian/filter produk & user
  services/shop.py     beli & batalkan transaksi (dengan penguncian stok)
  services/activity_logger.py  perekam query SQL per request
  services/activity_logs.py    filter & pagination log untuk admin
  routes/auth.py       /login, /logout, /dashboard (redirect sesuai role)
  routes/admin.py      /admin/* (ADMIN saja): dashboard, users, products CRUD, activity-logs
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
