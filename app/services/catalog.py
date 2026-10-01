"""Query produk & user untuk fitur normal (semua parameterized lewat SQLAlchemy)."""
from decimal import Decimal, InvalidOperation

from app import db
from app.models import Product, User

PRODUCT_SORTS = {
    "newest": Product.created_at.desc(),
    "name": Product.name.asc(),
    "price_asc": Product.price.asc(),
    "price_desc": Product.price.desc(),
}

PER_PAGE = 10


def _decimal_or_none(value):
    if value in (None, ""):
        return None
    try:
        number = Decimal(value)
    except InvalidOperation:
        return None
    return number if number >= 0 else None


def parse_product_filters(args):
    """Ambil filter dari query string; nilai tidak valid diabaikan (bukan error)."""
    sort = args.get("sort", "newest")
    return {
        "q": args.get("q", "").strip(),
        "category": args.get("category", "").strip(),
        "min_price": _decimal_or_none(args.get("min_price")),
        "max_price": _decimal_or_none(args.get("max_price")),
        "in_stock": args.get("in_stock") == "1",
        "sort": sort if sort in PRODUCT_SORTS else "newest",
    }


def product_query(filters):
    stmt = db.select(Product)
    if filters["q"]:
        pattern = f"%{filters['q']}%"
        stmt = stmt.where(Product.name.like(pattern) | Product.description.like(pattern))
    if filters["category"]:
        stmt = stmt.where(Product.category == filters["category"])
    if filters["min_price"] is not None:
        stmt = stmt.where(Product.price >= filters["min_price"])
    if filters["max_price"] is not None:
        stmt = stmt.where(Product.price <= filters["max_price"])
    if filters["in_stock"]:
        stmt = stmt.where(Product.stock > 0)
    return stmt.order_by(PRODUCT_SORTS[filters["sort"]], Product.id)


def search_products(filters, page):
    return db.paginate(product_query(filters), page=page, per_page=PER_PAGE, error_out=False)


def product_categories():
    return db.session.execute(
        db.select(Product.category).distinct().order_by(Product.category)
    ).scalars().all()


def search_users(q, page):
    stmt = db.select(User)
    if q:
        stmt = stmt.where(User.username.like(f"%{q}%"))
    return db.paginate(stmt.order_by(User.username), page=page, per_page=PER_PAGE, error_out=False)
