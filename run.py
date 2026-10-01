import os
import sys

from app import create_app

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}

app = create_app()

if __name__ == "__main__":
    host = os.getenv("APP_HOST", "127.0.0.1")
    port = int(os.getenv("APP_PORT", "5000"))

    # Aplikasi lab ini hanya boleh berjalan di localhost.
    if host not in LOOPBACK_HOSTS:
        sys.exit(f"Menolak bind ke {host!r}: aplikasi lab hanya boleh berjalan di localhost.")

    app.run(host=host, port=port, debug=os.getenv("FLASK_DEBUG") == "1")
