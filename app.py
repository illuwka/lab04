from pathlib import Path
from functools import wraps
import os

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for

from models import (
    ORDER_STATUSES, STATUS_LABELS, authenticate_user, create_account,
    create_feedback, create_initial_admin, create_order, delete_feedback,
    delete_order, delete_product, delete_promocode, delete_user, get_all_feedback,
    get_available_promocodes,
    get_db, get_orders, get_product, get_products, get_promocodes, get_user,
    get_user_orders, get_users, has_admin, init_app, init_db, save_product,
    save_promocode, save_user, update_order, update_order_status,
)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("LOQ_MARKET_SECRET_KEY", "loq-market-development-key")
Path(app.instance_path).mkdir(parents=True, exist_ok=True)
app.config["DATABASE"] = str(Path(app.instance_path) / "loq_market.sqlite3")
init_app(app)


@app.before_request
def load_current_user_and_protect_admin():
    user_id = session.get("user_id")
    g.current_user = get_user(user_id) if user_id else None
    if user_id and g.current_user is None:
        session.clear()

    endpoint = request.endpoint or ""
    if endpoint == "admin" or endpoint.startswith("admin_"):
        if not has_admin():
            return redirect(url_for("setup_admin"))
        if g.current_user is None:
            return redirect(url_for("login", next=request.path))
        if g.current_user["role"] != "admin":
            abort(403)


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.current_user is None:
            flash("Увійди, щоб продовжити.", "error")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped_view


@app.context_processor
def inject_user_navigation():
    return {
        "current_user": getattr(g, "current_user", None),
        "admin_setup_required": not has_admin(),
    }


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/setup/admin", methods=["GET", "POST"])
def setup_admin():
    if has_admin():
        return redirect(url_for("login"))
    if request.method == "POST":
        name = request.form.get("name", "")
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        try:
            user_id = create_initial_admin(name, email, password)
            session.clear()
            session["user_id"] = user_id
            flash("Обліковий запис адміністратора створено.", "success")
            return redirect(url_for("admin_products"))
        except ValueError as error:
            flash(str(error), "error")
    return render_template("setup_admin.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if g.current_user:
        return redirect(url_for("shop"))
    if request.method == "POST":
        try:
            user_id = create_account(
                request.form.get("name", ""),
                request.form.get("email", ""),
                request.form.get("password", ""),
            )
            session.clear()
            session["user_id"] = user_id
            flash("Обліковий запис створено. Можна оформлювати замовлення.", "success")
            return redirect(url_for("shop"))
        except ValueError as error:
            flash(str(error), "error")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.current_user:
        return redirect(url_for("shop"))
    next_path = request.args.get("next", "")
    if request.method == "POST":
        user = authenticate_user(request.form.get("email", ""), request.form.get("password", ""))
        if user is None:
            flash("Неправильна електронна пошта або пароль.", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            next_path = request.form.get("next", "")
            if next_path.startswith("/") and not next_path.startswith("//"):
                return redirect(next_path)
            return redirect(url_for("admin_products" if user["role"] == "admin" else "shop"))
    return render_template("login.html", next_path=next_path)


@app.post("/logout")
def logout():
    session.clear()
    flash("Ти вийшов/вийшла з облікового запису.", "success")
    return redirect(url_for("home"))


@app.route("/account")
@login_required
def account():
    return render_template(
        "account.html",
        user=g.current_user,
        orders=get_user_orders(g.current_user["id"]),
        status_labels=STATUS_LABELS,
    )


@app.route("/contacts", methods=["GET", "POST"])
def contacts():
    if request.method == "POST":
        name, email, message = (request.form.get(key, "").strip() for key in ("name", "email", "message"))
        if not name or not email or "@" not in email or not message:
            flash("Заповни всі поля та вкажи коректну електронну адресу.", "error")
        else:
            create_feedback(name, email, message)
            flash("Дякуємо! Твій відгук збережено.", "success")
        return redirect(url_for("contacts"))
    return render_template("contacts.html")


@app.route("/admin")
def admin():
    return redirect(url_for("admin_products"))


@app.route("/admin/feedback")
def admin_feedback():
    return render_template("admin_feedback.html", feedback_entries=get_all_feedback())


@app.post("/admin/feedback/<int:feedback_id>/delete")
def admin_delete_feedback(feedback_id):
    flash("Відгук видалено." if delete_feedback(feedback_id) else "Відгук уже не існує.", "success")
    return redirect(url_for("admin_feedback"))


@app.route("/admin/products")
def admin_products():
    return render_template("admin_products.html", products=get_products())


def product_form_values():
    weapon = request.form.get("weapon", "").strip()
    skin = request.form.get("skin", "").strip()
    quality = request.form.get("quality", "").strip()
    image_url = request.form.get("image_url", "").strip()
    try:
        price = float(request.form.get("price", ""))
        stock = int(request.form.get("stock", ""))
    except ValueError:
        raise ValueError("Ціна має бути числом, а залишок — цілим числом.")
    if not weapon or not skin or not quality or price < 0 or stock < 0:
        raise ValueError("Заповни назву, стан, ціну та залишок коректно.")
    return weapon, skin, quality, price, image_url, stock


@app.post("/admin/products/save")
def admin_save_product():
    product_id = request.form.get("product_id", "").strip()
    try:
        product_id = int(product_id) if product_id else None
        save_product(product_id, *product_form_values())
        flash("Товар збережено.", "success")
    except ValueError as error:
        flash(str(error), "error")
    return redirect(url_for("admin_products"))


@app.post("/admin/products/<int:product_id>/delete")
def admin_delete_product(product_id):
    if delete_product(product_id):
        flash("Товар видалено.", "success")
    else:
        flash("Товар не знайдено або він уже входить до замовлення.", "error")
    return redirect(url_for("admin_products"))


@app.route("/admin/users")
def admin_users():
    return render_template(
        "admin_users.html",
        users=get_users(),
        products=get_products(),
        statuses=ORDER_STATUSES,
        status_labels=STATUS_LABELS,
    )


@app.post("/admin/users/save")
def admin_save_user():
    user_id = request.form.get("user_id", "").strip()
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    try:
        if user_id:
            save_user(int(user_id), name, email, request.form.get("role", "customer"))
            flash("Дані користувача збережено.", "success")
        else:
            create_account(name, email, request.form.get("password", ""))
            flash("Обліковий запис клієнта створено.", "success")
    except ValueError as error:
        flash(str(error), "error")
    return redirect(url_for("admin_users"))


@app.post("/admin/users/<int:user_id>/delete")
def admin_delete_user(user_id):
    try:
        if delete_user(user_id):
            flash("Користувача та його замовлення видалено.", "success")
        else:
            flash("Користувача не знайдено.", "error")
    except ValueError as error:
        flash(str(error), "error")
    return redirect(url_for("admin_users"))


@app.post("/admin/users/<int:user_id>/orders/create")
def admin_create_user_order(user_id):
    product_id = request.form.get("product_id", "").strip()
    quantity = request.form.get("quantity", "").strip()
    status = request.form.get("status", "pending").strip()
    try:
        p_id = int(product_id)
        qty = int(quantity)
        order_id = create_order(p_id, "", "", qty, user_id=user_id, status=status)
        flash(f"Замовлення №{order_id} для користувача створено.", "success")
    except (ValueError, TypeError) as error:
        flash(str(error), "error")
    return redirect(url_for("admin_users"))


@app.route("/admin/orders")
def admin_orders():
    return render_template(
        "admin_orders.html",
        orders=get_orders(),
        products=get_products(),
        statuses=ORDER_STATUSES,
        status_labels=STATUS_LABELS,
    )


@app.route("/admin/promocodes")
def admin_promocodes():
    return render_template("admin_promocodes.html", promocodes=get_promocodes())


@app.post("/admin/promocodes/save")
def admin_save_promocode():
    promo_id = request.form.get("promo_id", "").strip()
    try:
        promo_id = int(promo_id) if promo_id else None
        save_promocode(
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
    return redirect(url_for("admin_promocodes"))


@app.post("/admin/promocodes/<int:promo_id>/delete")
def admin_delete_promocode(promo_id):
    flash("Промокод видалено." if delete_promocode(promo_id) else "Промокод не знайдено.", "success")
    return redirect(url_for("admin_promocodes"))


@app.post("/admin/orders/<int:order_id>/status")
def admin_order_status(order_id):
    redirect_to = request.form.get("redirect_to", "admin_orders")
    try:
        updated = update_order_status(order_id, request.form.get("status", ""))
        flash("Статус замовлення оновлено." if updated else "Замовлення не знайдено.", "success" if updated else "error")
    except ValueError as error:
        flash(str(error), "error")
    if redirect_to == "admin_users":
        return redirect(url_for("admin_users"))
    return redirect(url_for("admin_orders"))


@app.post("/admin/orders/<int:order_id>/edit")
def admin_edit_order(order_id):
    product_id = request.form.get("product_id", "").strip()
    quantity = request.form.get("quantity", "").strip()
    total_price = request.form.get("total_price", "").strip()
    status = request.form.get("status", "").strip()
    redirect_to = request.form.get("redirect_to", "admin_orders")
    try:
        p_id = int(product_id) if product_id else None
        qty = int(quantity) if quantity else None
        price = float(total_price) if total_price else None
        update_order(order_id, product_id=p_id, quantity=qty, total_price=price, status=status)
        flash(f"Замовлення №{order_id} оновлено.", "success")
    except (ValueError, TypeError) as error:
        flash(str(error), "error")

    if redirect_to == "admin_users":
        return redirect(url_for("admin_users"))
    return redirect(url_for("admin_orders"))


@app.post("/admin/orders/<int:order_id>/delete")
def admin_delete_order(order_id):
    redirect_to = request.form.get("redirect_to", "admin_orders")
    if delete_order(order_id):
        flash("Замовлення видалено.", "success")
    else:
        flash("Замовлення не знайдено.", "error")
    if redirect_to == "admin_users":
        return redirect(url_for("admin_users"))
    return redirect(url_for("admin_orders"))


@app.route("/shop")
def shop():
    return render_template("shop.html", products=get_products(), promocodes=get_available_promocodes())


@app.route("/shop/<int:product_id>/order", methods=["GET", "POST"])
@login_required
def order_product(product_id):
    product = get_product(product_id)
    if product is None:
        abort(404)
    if request.method == "POST":
        try:
            quantity = int(request.form.get("quantity", ""))
        except ValueError:
            quantity = 0
        try:
            order_id = create_order(
                product_id,
                g.current_user["name"],
                g.current_user["email"],
                quantity,
                user_id=g.current_user["id"],
                promo_code=request.form.get("promo_code", ""),
            )
        except ValueError as error:
            flash(str(error), "error")
            return redirect(url_for("order_product", product_id=product_id))
        flash(f"Замовлення №{order_id} оформлено.", "success")
        return redirect(url_for("account"))
    return render_template("order.html", product=product, user=g.current_user)


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
