"""Робота з підключенням до бази даних SQLite, ініціалізацією схеми та міграціями."""
import sqlite3

from flask import current_app, g


def get_db():
    """Повертає з'єднання SQLite для поточного запиту (створює за потреби)."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    """Закриває з'єднання з БД наприкінці запиту."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_app(app):
    """Реєструє функцію автоматичного закриття з'єднання в застосунку Flask."""
    app.teardown_appcontext(close_db)


def _create_order_tables(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            customer_name TEXT NOT NULL,
            customer_email TEXT NOT NULL,
            total_price REAL NOT NULL CHECK (total_price >= 0),
            promo_code TEXT,
            discount_amount REAL NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending','processing','shipped','completed','cancelled')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            unit_price REAL NOT NULL CHECK (unit_price >= 0),
            quantity INTEGER NOT NULL CHECK (quantity > 0),
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
        );
        CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
        CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
    """)


def init_db():
    """Створює таблиці, індекси та виконує необхідні міграції схеми."""
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            parent_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            weapon TEXT NOT NULL,
            skin TEXT NOT NULL,
            quality TEXT NOT NULL,
            price REAL NOT NULL CHECK (price >= 0),
            image_url TEXT NOT NULL DEFAULT '',
            stock INTEGER NOT NULL DEFAULT 10 CHECK (stock >= 0),
            category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL DEFAULT 'customer' CHECK (role IN ('admin', 'customer')),
            password TEXT,
            password_hash TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS promocodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE COLLATE NOCASE,
            discount_percent INTEGER NOT NULL CHECK (discount_percent BETWEEN 1 AND 100),
            active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
            expires_on TEXT,
            usage_limit INTEGER CHECK (usage_limit IS NULL OR usage_limit > 0),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS favorites (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, product_id)
        );
    """)

    product_columns = {row["name"] for row in db.execute("PRAGMA table_info(products)")}
    if "category_id" not in product_columns:
        db.execute("ALTER TABLE products ADD COLUMN category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL")
    db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_categories_parent_name "
        "ON categories(COALESCE(parent_id, 0), name COLLATE NOCASE)"
    )

    user_columns = {row["name"] for row in db.execute("PRAGMA table_info(users)")}
    if "role" not in user_columns:
        db.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'customer'")
    if "password" not in user_columns:
        db.execute("ALTER TABLE users ADD COLUMN password TEXT")
    if "password_hash" not in user_columns:
        db.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")

    orders_exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='orders'").fetchone()
    if not orders_exists:
        _create_order_tables(db)
    else:
        columns = {row["name"] for row in db.execute("PRAGMA table_info(orders)")}
        if "product_id" in columns:
            db.execute("PRAGMA foreign_keys = OFF")
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute("ALTER TABLE orders RENAME TO orders_legacy")
                _create_order_tables(db)
                db.execute("""INSERT INTO orders
                    (id, customer_name, customer_email, total_price, status, created_at)
                    SELECT id, customer_name, customer_email, total_price, 'pending', created_at
                    FROM orders_legacy""")
                db.execute("""INSERT INTO order_items (order_id, product_id, product_name, unit_price, quantity)
                    SELECT id, product_id, product_name, unit_price, quantity FROM orders_legacy""")
                db.execute("DROP TABLE orders_legacy")
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.execute("PRAGMA foreign_keys = ON")
        else:
            if "user_id" not in columns:
                db.execute("ALTER TABLE orders ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE")
            db.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)")

    order_columns = {row["name"] for row in db.execute("PRAGMA table_info(orders)")}
    if "promo_code" not in order_columns:
        db.execute("ALTER TABLE orders ADD COLUMN promo_code TEXT")
    if "discount_amount" not in order_columns:
        db.execute("ALTER TABLE orders ADD COLUMN discount_amount REAL NOT NULL DEFAULT 0")

    db.commit()
