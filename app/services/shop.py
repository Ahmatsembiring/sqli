"""Transaksi sederhana: beli dan batalkan, dengan penyesuaian stok."""
from app import db
from app.models import Product, Transaction

MAX_QUANTITY = 100


class ShopError(Exception):
    pass


def purchase(user, product_id, quantity):
    if not 1 <= quantity <= MAX_QUANTITY:
        raise ShopError(f"Jumlah harus antara 1 dan {MAX_QUANTITY}.")

    # Kunci baris produk agar stok tidak minus saat ada pembelian bersamaan.
    product = db.session.execute(
        db.select(Product).where(Product.id == product_id).with_for_update()
    ).scalar_one_or_none()
    if product is None:
        raise ShopError("Produk tidak ditemukan.")
    if product.stock < quantity:
        db.session.rollback()
        raise ShopError(f"Stok tidak cukup (tersisa {product.stock}).")

    product.stock -= quantity
    trx = Transaction(user_id=user.id, product_id=product.id, quantity=quantity)
    db.session.add(trx)
    db.session.commit()
    return trx


def get_own_transaction(user, transaction_id):
    """Transaksi milik user lain diperlakukan sama dengan tidak ada."""
    return db.session.execute(
        db.select(Transaction).where(
            Transaction.id == transaction_id, Transaction.user_id == user.id
        )
    ).scalar_one_or_none()


def cancel(user, transaction_id):
    trx = get_own_transaction(user, transaction_id)
    if trx is None:
        raise ShopError("Transaksi tidak ditemukan.")

    product = db.session.execute(
        db.select(Product).where(Product.id == trx.product_id).with_for_update()
    ).scalar_one()
    product.stock += trx.quantity
    db.session.delete(trx)
    db.session.commit()


def user_transactions(user):
    return db.session.execute(
        db.select(Transaction)
        .where(Transaction.user_id == user.id)
        .order_by(Transaction.created_at.desc(), Transaction.id.desc())
    ).scalars().all()
