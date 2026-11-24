"""Маршрути каталогу магазину, обраного та оформлення замовлень."""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

import models
from .auth import login_required

shop_bp = Blueprint("shop", __name__)


@shop_bp.route("/shop")
def shop():
    all_products = models.get_products()
    categories = models.get_categories()
    category_value = request.args.get("category_id", "").strip()
    try:
        selected_category = int(category_value) if category_value else None
    except ValueError:
        selected_category = None

    category_ids = set()
    if selected_category is not None:
        category_ids.add(selected_category)
        while True:
            children = {category["id"] for category in categories if category["parent_id"] in category_ids}
            updated = category_ids | children
            if updated == category_ids:
                break
            category_ids = updated

    query = request.args.get("q", "").strip()
    weapon = request.args.get("weapon", "").strip()
    quality = request.args.get("quality", "").strip()
    availability = request.args.get("availability", "").strip()
    sort = request.args.get("sort", "default").strip()

    def read_price_filter(name):
        try:
            value = float(request.args.get(name, ""))
            return value if value >= 0 else None
        except (TypeError, ValueError):
            return None

    price_min = read_price_filter("price_min")
    price_max = read_price_filter("price_max")
    products = [
        product
        for product in all_products
        if (not query or query.casefold() in f"{product['weapon']} {product['skin']} {product['quality']}".casefold())
        and (not weapon or product["weapon"] == weapon)
        and (not quality or product["quality"] == quality)
        and (selected_category is None or product["category_id"] in category_ids)
        and (availability != "in_stock" or product["stock"] > 0)
        and (price_min is None or product["price"] >= price_min)
        and (price_max is None or product["price"] <= price_max)
    ]

    if sort == "price_asc":
        products.sort(key=lambda product: (product["price"], product["weapon"], product["skin"]))
    elif sort == "price_desc":
        products.sort(key=lambda product: (-product["price"], product["weapon"], product["skin"]))
    elif sort == "name":
        products.sort(key=lambda product: (product["weapon"].casefold(), product["skin"].casefold()))

    return render_template(
        "shop.html",
        products=products,
        promocodes=models.get_available_promocodes(),
        filters={
            "q": query,
            "weapon": weapon,
            "quality": quality,
            "category_id": selected_category,
            "availability": availability,
            "price_min": request.args.get("price_min", ""),
            "price_max": request.args.get("price_max", ""),
            "sort": sort,
        },
        weapons=sorted({product["weapon"] for product in all_products}),
        qualities=sorted({product["quality"] for product in all_products}),
        categories=categories,
        category_paths={category["id"]: category["path"] for category in categories},
        favorite_ids=models.get_favorite_product_ids(g.current_user["id"]) if g.current_user else set(),
        total_products=len(all_products),
    )


@shop_bp.route("/favorites")
@login_required
def favorites():
    categories = models.get_categories()
    return render_template(
        "favorites.html",
        products=models.get_favorite_products(g.current_user["id"]),
        categories=categories,
        category_paths={category["id"]: category["path"] for category in categories},
        favorite_ids=models.get_favorite_product_ids(g.current_user["id"]),
    )


@shop_bp.post("/favorites/<int:product_id>/toggle")
@login_required
def toggle_product_favorite(product_id):
    if models.get_product(product_id) is None:
        abort(404)
    saved = models.toggle_favorite(g.current_user["id"], product_id)
    flash("Товар додано до обраного." if saved else "Товар видалено з обраного.", "success")
    target = request.form.get("next", "")
    if target.startswith("/") and not target.startswith("//"):
        return redirect(target)
    return redirect(url_for("shop.favorites"))


@shop_bp.route("/shop/<int:product_id>/order", methods=["GET", "POST"])
@login_required
def order_product(product_id):
    product = models.get_product(product_id)
    if product is None:
        abort(404)
    if request.method == "POST":
        try:
            quantity = int(request.form.get("quantity", ""))
        except ValueError:
            quantity = 0
        try:
            order_id = models.create_order(
                product_id,
                g.current_user["name"],
                g.current_user["email"],
                quantity,
                user_id=g.current_user["id"],
                promo_code=request.form.get("promo_code", ""),
            )
        except ValueError as error:
            flash(str(error), "error")
            return redirect(url_for("shop.order_product", product_id=product_id))
        flash(f"Замовлення №{order_id} оформлено.", "success")
        return redirect(url_for("auth.account"))
    return render_template("order.html", product=product, user=g.current_user)
