"""CRUD-операції та автентифікація користувачів."""
import sqlite3

from werkzeug.security import check_password_hash

from .db import get_db
from .orders import get_user_orders


def has_admin():
    return get_db().execute("SELECT 1 FROM users WHERE role = 'admin' LIMIT 1").fetchone() is not None


def _account_fields(name, email, password):
    name = name.strip()
    email = email.strip().lower()
    if not name or len(name) > 100:
        raise ValueError("Вкажіть ім’я довжиною до 100 символів.")
    if not email or len(email) > 254 or "@" not in email:
        raise ValueError("Вкажіть коректну адресу електронної пошти.")
    if len(password) < 8:
        raise ValueError("Пароль має містити щонайменше 8 символів.")
    return name, email, password


def create_account(name, email, password):
    name, email, plain_password = _account_fields(name, email, password)
    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO users (name, email, role, password, password_hash) VALUES (?, ?, 'customer', ?, NULL)",
            (name, email, plain_password),
        )
        db.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError as error:
        db.rollback()
        raise ValueError("Користувач із такою електронною поштою вже існує.") from error


def create_initial_admin(name, email, password):
    name, email, plain_password = _account_fields(name, email, password)
    db = get_db()
    db.execute("BEGIN IMMEDIATE")
    try:
        if db.execute("SELECT 1 FROM users WHERE role = 'admin' LIMIT 1").fetchone():
            raise ValueError("Обліковий запис адміністратора вже налаштовано.")
        existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            db.execute(
                "UPDATE users SET name = ?, role = 'admin', password = ?, password_hash = NULL WHERE id = ?",
                (name, plain_password, existing["id"]),
            )
            user_id = existing["id"]
        else:
            cursor = db.execute(
                "INSERT INTO users (name, email, role, password, password_hash) VALUES (?, ?, 'admin', ?, NULL)",
                (name, email, plain_password),
            )
            user_id = cursor.lastrowid
        db.commit()
        return user_id
    except Exception:
        db.rollback()
        raise


def authenticate_user(email, password):
    email = email.strip().lower()
    db = get_db()
    user = db.execute(
        "SELECT id, password, password_hash FROM users WHERE email = ?",
        (email,),
    ).fetchone()
    if user is None:
        return None
    if user["password"] is not None:
        if user["password"] != password:
            return None
    elif user["password_hash"] and check_password_hash(user["password_hash"], password):
        db.execute("UPDATE users SET password = ?, password_hash = NULL WHERE id = ?", (password, user["id"]))
        db.commit()
    else:
        return None
    return get_user(user["id"])


def get_users():
    db = get_db()
    users = db.execute("SELECT id, name, email, role, created_at FROM users ORDER BY id").fetchall()
    result = []
    for u in users:
        orders = get_user_orders(u["id"])
        result.append({
            "id": u["id"],
            "name": u["name"],
            "email": u["email"],
            "role": u["role"],
            "created_at": u["created_at"],
            "orders": orders,
            "orders_count": len(orders),
            "total_spent": sum(o["total_price"] for o in orders if o["status"] != "cancelled"),
        })
    return result


def get_user(user_id):
    db = get_db()
    u = db.execute("SELECT id, name, email, role, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    if u is None:
        return None
    user = dict(u)
    user["orders"] = get_user_orders(user_id)
    return user


def save_user(user_id, name, email, role="customer"):
    db = get_db()
    name = name.strip()
    email = email.strip().lower()
    if role not in ("admin", "customer"):
        raise ValueError("Недопустима роль користувача.")
    if not name or len(name) > 100 or not email or len(email) > 254 or "@" not in email:
        raise ValueError("Вкажіть коректне ім’я та адресу електронної пошти.")

    if user_id is None:
        existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            raise ValueError(f"Користувач із поштою {email} вже існує.")
        cursor = db.execute("INSERT INTO users (name, email, role) VALUES (?, ?, ?)", (name, email, role))
        db.commit()
        return cursor.lastrowid
    else:
        existing = db.execute("SELECT id FROM users WHERE email = ? AND id != ?", (email, user_id)).fetchone()
        if existing:
            raise ValueError(f"Електронна пошта {email} вже використовується іншим користувачем.")
        db.execute("BEGIN IMMEDIATE")
        try:
            current = db.execute("SELECT role, password, password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
            if current is None:
                raise ValueError("Користувача не знайдено.")
            if role == "admin" and current["password"] is None and not current["password_hash"]:
                raise ValueError("Цей користувач ще не має пароля й не може увійти як адміністратор.")
            if current["role"] == "admin" and role != "admin":
                admin_count = db.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]
                if admin_count <= 1:
                    raise ValueError("Неможливо змінити роль останнього адміністратора.")
            db.execute("UPDATE users SET name = ?, email = ?, role = ? WHERE id = ?", (name, email, role, user_id))
            db.execute("UPDATE orders SET customer_name = ?, customer_email = ? WHERE user_id = ?", (name, email, user_id))
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise


def delete_user(user_id):
    db = get_db()
    db.execute("BEGIN IMMEDIATE")
    try:
        user = db.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            db.rollback()
            return False
        role = db.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()["role"]
        if role == "admin" and db.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0] <= 1:
            raise ValueError("Неможливо видалити останнього адміністратора.")
        orders = db.execute("SELECT id, status FROM orders WHERE user_id = ?", (user_id,)).fetchall()
        for o in orders:
            if o["status"] != "cancelled":
                items = db.execute("SELECT product_id, quantity FROM order_items WHERE order_id = ?", (o["id"],)).fetchall()
                for it in items:
                    db.execute("UPDATE products SET stock = stock + ? WHERE id = ?", (it["quantity"], it["product_id"]))
            db.execute("DELETE FROM order_items WHERE order_id = ?", (o["id"],))
        db.execute("DELETE FROM orders WHERE user_id = ?", (user_id,))
        db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
