from datetime import datetime

from app import db


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(50), nullable=False, index=True)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(12, 2), nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    transactions = db.relationship("Transaction", back_populates="product", lazy="dynamic")

    def __repr__(self):
        return f"<Product {self.id} {self.name}>"
