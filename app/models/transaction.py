from datetime import datetime

from app import db


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    user = db.relationship("User", back_populates="transactions")
    product = db.relationship("Product", back_populates="transactions")

    @property
    def total(self):
        return self.product.price * self.quantity

    def __repr__(self):
        return f"<Transaction {self.id} user={self.user_id} product={self.product_id} qty={self.quantity}>"
