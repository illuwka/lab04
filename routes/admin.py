"""Маршрути адміністративної панелі: товари, категорії, користувачі, замовлення, промокоди, відгуки."""
from flask import Blueprint, flash, redirect, render_template, request, url_for

import models

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _order_redirect():
    redirect_to = request.form.get("redirect_to", "admin_orders")
    if redirect_to in ("admin_users", "admin.users"):
        return redirect(url_for("admin.users"))
    return redirect(url_for("admin.orders"))


@admin_bp.route("")
@admin_bp.route("/")
def index():
    return redirect(url_for("admin.products"))


@admin_bp.route("/feedback")
def feedback():
    return render_template("admin_feedback.html", feedback_entries=models.get_all_feedback())


@admin_bp.post("/feedback/<int:feedback_id>/delete")
def delete_feedback(feedback_id):
    flash("Відгук видалено." if models.delete_feedback(feedback_id) else "Відгук уже не існує.", "success")
    return redirect(url_for("admin.feedback"))


@admin_bp.route("/products")
def products():
    return render_template("admin_products.html", products=models.get_products(), categories=models.get_categories())


@admin_bp.post("/categories/save")
def save_category():
    category_id = request.form.get("category_id", "").strip()
    parent_id = request.form.get("parent_id", "").strip()
    try:
        models.save_category(
            int(category_id) if category_id else None,
            request.form.get("name", ""),
            int(parent_id) if parent_id else None,
        )
        flash("Категорію збережено.", "success")
    except ValueError as error:
        flash(str(error), "error")
    return redirect(url_for("admin.products"))


@admin_bp.post("/categories/<int:category_id>/delete")
def delete_category(category_id):
    flash(
        "Категорію видалено. Товари та підкатегорії перенесено на батьківський рівень."
        if models.delete_category(category_id)
        else "Категорію не знайдено.",
        "success",
    )
    return redirect(url_for("admin.products"))


def _product_form_values():
    weapon = request.form.get("weapon", "").strip()
    skin = request.form.get("skin", "").strip()
    quality = request.form.get("quality", "").strip()
    image_url = request.form.get("image_url", "").strip()
    category_value = request.form.get("category_id", "").strip()
    try:
        price = float(request.form.get("price", ""))
        stock = int(request.form.get("stock", ""))
    except ValueError:
        raise ValueError("Ціна має бути числом, а залишок — цілим числом.")
    if not weapon or not skin or not quality or price < 0 or stock < 0:
        raise ValueError("Заповни назву, стан, ціну та залишок коректно.")
    try:
        category_id = int(category_value) if category_value else None
    except ValueError:
        raise ValueError("Обери коректну категорію товару.")
    return weapon, skin, quality, price, image_url, stock, category_id


@admin_bp.post("/products/save")
def save_product():
    product_id = request.form.get("product_id", "").strip()
    try:
        product_id = int(product_id) if product_id else None
        models.save_product(product_id, *_product_form_values())
        flash("Товар збережено.", "success")
    except ValueError as error:
        flash(str(error), "error")
    return redirect(url_for("admin.products"))


@admin_bp.post("/products/<int:product_id>/delete")
def delete_product(product_id):
    if models.delete_product(product_id):
        flash("Товар видалено.", "success")
    else:
        flash("Товар не знайдено або він уже входить до замовлення.", "error")
    return redirect(url_for("admin.products"))


@admin_bp.route("/users")
def users():
    return render_template(
        "admin_users.html",
        users=models.get_users(),
        products=models.get_products(),
        statuses=models.ORDER_STATUSES,
        status_labels=models.STATUS_LABELS,
    )


@admin_bp.post("/users/save")
def save_user():
    user_id = request.form.get("user_id", "").strip()
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    try:
        if user_id:
            models.save_user(int(user_id), name, email, request.form.get("role", "customer"))
            flash("Дані користувача збережено.", "success")
        else:
            models.create_account(name, email, request.form.get("password", ""))
            flash("Обліковий запис клієнта створено.", "success")
    except ValueError as error:
        flash(str(error), "error")
    return redirect(url_for("admin.users"))


@admin_bp.post("/users/<int:user_id>/delete")
def delete_user(user_id):
    try:
        if models.delete_user(user_id):
            flash("Користувача та його замовлення видалено.", "success")
        else:
            flash("Користувача не знайдено.", "error")
    except ValueError as error:
        flash(str(error), "error")
    return redirect(url_for("admin.users"))


@admin_bp.post("/users/<int:user_id>/orders/create")
def create_user_order(user_id):
    product_id = request.form.get("product_id", "").strip()
    quantity = request.form.get("quantity", "").strip()
    status = request.form.get("status", "pending").strip()
    try:
        p_id = int(product_id)
        qty = int(quantity)
        order_id = models.create_order(p_id, "", "", qty, user_id=user_id, status=status)
        flash(f"Замовлення №{order_id} для користувача створено.", "success")
    except (ValueError, TypeError) as error:
        flash(str(error), "error")
    return redirect(url_for("admin.users"))


@admin_bp.route("/orders")
def orders():
    return render_template(
        "admin_orders.html",
        orders=models.get_orders(),
        products=models.get_products(),
        statuses=models.ORDER_STATUSES,
        status_labels=models.STATUS_LABELS,
    )


@admin_bp.route("/promocodes")
def promocodes():
    return render_template("admin_promocodes.html", promocodes=models.get_promocodes())


@admin_bp.post("/promocodes/save")
def save_promocode():
    promo_id = request.form.get("promo_id", "").strip()
    try:
        promo_id = int(promo_id) if promo_id else None
        models.save_promocode(
            promo_id,
            request.form.get("code", ""),
            request.form.get("discount_percent", ""),
            request.form.get("expires_on"),
            request.form.get("usage_limit"),
            request.form.get("active") == "on",
        )
        flash("Промокод збережено.", "success")
    except ValueError as error:
        flash(str(error), "error")
    return redirect(url_for("admin.promocodes"))


@admin_bp.post("/promocodes/<int:promo_id>/delete")
def delete_promocode(promo_id):
    flash("Промокод видалено." if models.delete_promocode(promo_id) else "Промокод не знайдено.", "success")
    return redirect(url_for("admin.promocodes"))


@admin_bp.post("/orders/<int:order_id>/status")
def order_status(order_id):
    try:
        updated = models.update_order_status(order_id, request.form.get("status", ""))
        flash(
            "Статус замовлення оновлено." if updated else "Замовлення не знайдено.",
            "success" if updated else "error",
        )
    except ValueError as error:
        flash(str(error), "error")
    return _order_redirect()


@admin_bp.post("/orders/<int:order_id>/edit")
def edit_order(order_id):
    product_id = request.form.get("product_id", "").strip()
    quantity = request.form.get("quantity", "").strip()
    total_price = request.form.get("total_price", "").strip()
    status = request.form.get("status", "").strip()
    try:
        p_id = int(product_id) if product_id else None
        qty = int(quantity) if quantity else None
        price = float(total_price) if total_price else None
        models.update_order(order_id, product_id=p_id, quantity=qty, total_price=price, status=status)
        flash(f"Замовлення №{order_id} оновлено.", "success")
    except (ValueError, TypeError) as error:
        flash(str(error), "error")
    return _order_redirect()


@admin_bp.post("/orders/<int:order_id>/delete")
def delete_order(order_id):
    if models.delete_order(order_id):
        flash("Замовлення видалено.", "success")
    else:
        flash("Замовлення не знайдено.", "error")
    return _order_redirect()
