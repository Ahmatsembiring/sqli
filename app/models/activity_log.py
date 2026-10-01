import enum

from sqlalchemy.dialects.mysql import DATETIME

from app import db


class Operation(str, enum.Enum):
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    OTHER = "OTHER"


class QueryStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


class Label(str, enum.Enum):
    BENIGN = "BENIGN"
    SQL_INJECTION = "SQL_INJECTION"


def _enum(enum_cls, name):
    return db.Enum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e])


class ActivityLog(db.Model):
    """Satu baris = satu query SQL yang dieksekusi aplikasi selama satu HTTP request."""

    __tablename__ = "activity_logs"

    id = db.Column(db.BigInteger, primary_key=True)
    timestamp = db.Column(DATETIME(fsp=3), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    session_id = db.Column(db.String(64), nullable=True)
    endpoint = db.Column(db.String(200), nullable=False, index=True)
    http_method = db.Column(db.String(8), nullable=False)
    input_data = db.Column(db.Text, nullable=True)
    query = db.Column(db.Text, nullable=False)
    operation = db.Column(_enum(Operation, "log_operation"), nullable=False, index=True)
    status = db.Column(_enum(QueryStatus, "log_status"), nullable=False)
    error_message = db.Column(db.String(255), nullable=True)
    # Ground truth diisi pada tahap dataset (Phase 5); NULL = belum dilabeli.
    label = db.Column(_enum(Label, "log_label"), nullable=True, index=True)
    # Durasi eksekusi query di driver DB (ms), bukan durasi HTTP request.
    response_time = db.Column(db.Float, nullable=False)

    user = db.relationship("User")

    def __repr__(self):
        return f"<ActivityLog {self.id} {self.operation.value} {self.endpoint}>"
