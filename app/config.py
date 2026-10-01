import os
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()


def _required(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} belum diset (lihat .env.example)")
    return value


def build_db_uri(db_name):
    user = quote_plus(_required("DB_USER"))
    password = quote_plus(_required("DB_PASSWORD"))
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = os.getenv("DB_PORT", "3306")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{db_name}?charset=utf8mb4"


class Config:
    SECRET_KEY = _required("FLASK_SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = build_db_uri(_required("DB_NAME"))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = build_db_uri(_required("DB_TEST_NAME"))
