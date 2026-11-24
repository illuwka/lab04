"""Початкові дані та наповнення бази даних LOQ Market.

Може використовуватися як модуль під час запуску застосунку або як окремий скрипт:
python seed_data.py
"""
import models

SEED_PRODUCTS = (
    (
        "AWP",
        "Dragon Lore",
        "Factory New",
        1249.00,
        "https://community.akamai.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttyVfPaERSR0Wqmu7LAocGIGz3UqlXOLrxM-vMGmW8VNxu5Dx60noTyLwiYbf_jdk4veqYaF7IfysCnWRxuF4j-B-Xxa_nBovp3Pdwtj9cC_GaAd0DZdwQu9fuhS4kNy0NePntVTbjYpCyyT_3CgY5i9j_a9cBkcCWUKV",
        10,
    ),
    ("Karambit", "Doppler - Phase 2", "Factory New", 785.00, "https://cdn.cs2skins.gg/screenshots/skin-e7fd9a1907bb/fn/render.avif", 10),
    ("AK-47", "Fire Serpent", "Minimal Wear", 612.00, "https://cdn.cs2skins.gg/screenshots/skin-2599a8720f89/bs/render.avif", 10),
    ("M4A1-S", "Printstream", "Field-Tested", 98.50, "https://cdn.cs2skins.gg/screenshots/skin-8e45a15cf7f5/bs/render.avif", 8),
    ("USP-S", "Kill Confirmed", "Minimal Wear", 76.25, "https://cdn.cs2skins.gg/screenshots/skin-cf4c11689014/bs/render.avif", 6),
    (
        "Glock-18",
        "Fade",
        "Factory New",
        54.90,
        "https://community.akamai.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttyVfPaERSR0Wqmu7LAocGIGz3UqlXOLrxM-vMGmW8VNxu5Dx60noTyL2kpnj9h1a7s2oaaBoH_yaCW-Ej-8u5bZvHnq1w0Vz62TUzNj4eCiVblMmXMAkROJeskLpkdXjMrzksVTAy9US8PY25So",
        12,
    ),
    ("AWP", "Asiimov", "Field-Tested", 89.00, "https://cdn.cs2skins.gg/screenshots/skin-bb633c21fc25/bs/render.avif", 7),
    ("AK-47", "Neon Rider", "Minimal Wear", 73.40, "https://cdn.cs2skins.gg/screenshots/skin-74e670c4b279/bs/render.avif", 9),
    (
        "M4A4",
        "Howl",
        "Well-Worn",
        245.00,
        "https://community.akamai.steamstatic.com/economy/image/i0CoZ81Ui0m-9KwlBY1L_18myuGuq1wfhWSaZgMttyVfPaERSR0Wqmu7LAocGIGz3UqlXOLrxM-vMGmW8VNxu5Dx60noTyL8ypexwiFO0P_6afVSKP-EAm6extF6ueZhW2exwkl2tmTXwt39eCiUPQR2DMN4TOVetUK8xoLgM-K341eM2otDnC6okGoXufBz_TAB",
        3,
    ),
)


def seed():
    """Ідемпотентно наповнює базу початковими товарами, категоріями, промокодом та замовленнями."""
    db = models.get_db()

    for weapon, skin, quality, price, image_url, stock in SEED_PRODUCTS:
        db.execute(
            """INSERT INTO products (weapon, skin, quality, price, image_url, stock)
               SELECT ?, ?, ?, ?, ?, ?
               WHERE NOT EXISTS (SELECT 1 FROM products WHERE weapon = ? AND skin = ?)""",
            (weapon, skin, quality, price, image_url, stock, weapon, skin),
        )

    for weapon, skin, _quality, _price, image_url, _stock in SEED_PRODUCTS:
        if image_url:
            db.execute(
                "UPDATE products SET image_url = ? WHERE weapon = ? AND skin = ? AND image_url = ''",
                (image_url, weapon, skin),
            )

    root_id = models.get_or_create_category(db, "Скіни CS2", None)
    weapons_id = models.get_or_create_category(db, "Зброя", root_id)
    models.get_or_create_category(db, "Ножі", root_id)
    models.get_or_create_category(db, "Рукавички", root_id)
    rifles_id = models.get_or_create_category(db, "Гвинтівки", weapons_id)
    pistols_id = models.get_or_create_category(db, "Пістолети", weapons_id)

    for weapon in ("AWP", "AK-47", "M4A1-S", "M4A4"):
        db.execute("UPDATE products SET category_id = ? WHERE weapon = ? AND category_id IS NULL", (rifles_id, weapon))
    for weapon in ("USP-S", "Glock-18", "Desert Eagle"):
        db.execute("UPDATE products SET category_id = ? WHERE weapon = ? AND category_id IS NULL", (pistols_id, weapon))
    db.execute(
        "UPDATE products SET category_id = (SELECT id FROM categories WHERE name = 'Ножі' AND parent_id = ? LIMIT 1) "
        "WHERE (weapon LIKE '%Knife%' OR weapon IN ('Karambit', 'Butterfly')) AND category_id IS NULL",
        (root_id,),
    )
    db.execute(
        "UPDATE products SET category_id = (SELECT id FROM categories WHERE name = 'Рукавички' AND parent_id = ? LIMIT 1) "
        "WHERE weapon LIKE '%Gloves%' AND category_id IS NULL",
        (root_id,),
    )

    db.execute("INSERT OR IGNORE INTO promocodes (code, discount_percent) VALUES ('LOQ10', 10)")

    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        seed_users = (
            ("Влад Завиднюк", "skebob@gmail.com"),
            ("Давид Біскій", "bis.david11@gmail.com"),
            ("Ілля Прадійчук", "pradiychuk@example.com"),
        )
        user_ids = []
        for uname, uemail in seed_users:
            c = db.execute("INSERT INTO users (name, email) VALUES (?, ?)", (uname, uemail))
            user_ids.append(c.lastrowid)

        if db.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0:
            db_products = db.execute("SELECT id, weapon, skin, price, stock FROM products ORDER BY id").fetchall()
            if len(db_products) >= 3:
                sample_orders_data = [
                    (user_ids[0], seed_users[0][0], seed_users[0][1], db_products[0], "completed"),
                    (user_ids[1], seed_users[1][0], seed_users[1][1], db_products[1], "processing"),
                    (user_ids[2], seed_users[2][0], seed_users[2][1], db_products[2], "pending"),
                ]
                for uid, cname, cemail, prod, st in sample_orders_data:
                    c_ord = db.execute(
                        "INSERT INTO orders (user_id, customer_name, customer_email, total_price, status) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (uid, cname, cemail, prod["price"], st),
                    )
                    oid = c_ord.lastrowid
                    db.execute(
                        "INSERT INTO order_items (order_id, product_id, product_name, unit_price, quantity) "
                        "VALUES (?, ?, ?, ?, 1)",
                        (oid, prod["id"], f"{prod['weapon']} | {prod['skin']}", prod["price"]),
                    )

    unlinked = db.execute("SELECT id, customer_name, customer_email FROM orders WHERE user_id IS NULL").fetchall()
    for row in unlinked:
        u = db.execute("SELECT id FROM users WHERE email = ?", (row["customer_email"],)).fetchone()
        if not u:
            c = db.execute(
                "INSERT INTO users (name, email) VALUES (?, ?)",
                (row["customer_name"], row["customer_email"]),
            )
            uid = c.lastrowid
        else:
            uid = u["id"]
        db.execute("UPDATE orders SET user_id = ? WHERE id = ?", (uid, row["id"]))

    db.commit()


if __name__ == "__main__":
    from app import app

    with app.app_context():
        models.init_db()
        seed()
    print("Початкові дані успішно перевірено/додано до бази даних.")
