"""Маршрути автентифікації, реєстрації та особистого кабінету користувача."""
from functools import wraps

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

import models

auth_bp = Blueprint("auth", __name__)


def login_required(view):
    """Перевіряє, чи користувач увійшов у систему."""
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.current_user is None:
            flash("Увійди, щоб продовжити.", "error")
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped_view


@auth_bp.route("/setup/admin", methods=["GET", "POST"])
def setup_admin():
    if models.has_admin():
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        name = request.form.get("name", "")
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        try:
            user_id = models.create_initial_admin(name, email, password)
            session.clear()
            session["user_id"] = user_id
            flash("Обліковий запис адміністратора створено.", "success")
            return redirect(url_for("admin.products"))
        except ValueError as error:
            flash(str(error), "error")
    return render_template("setup_admin.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if g.current_user:
        return redirect(url_for("shop.shop"))
    if request.method == "POST":
        try:
            user_id = models.create_account(
                request.form.get("name", ""),
                request.form.get("email", ""),
                request.form.get("password", ""),
            )
            session.clear()
            session["user_id"] = user_id
            flash("Обліковий запис створено. Можна оформлювати замовлення.", "success")
            return redirect(url_for("shop.shop"))
        except ValueError as error:
            flash(str(error), "error")
    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if g.current_user:
        return redirect(url_for("shop.shop"))
    next_path = request.args.get("next", "")
    if request.method == "POST":
        user = models.authenticate_user(request.form.get("email", ""), request.form.get("password", ""))
        if user is None:
            flash("Неправильна електронна пошта або пароль.", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            next_path = request.form.get("next", "")
            if next_path.startswith("/") and not next_path.startswith("//"):
                return redirect(next_path)
            return redirect(url_for("admin.products" if user["role"] == "admin" else "shop.shop"))
    return render_template("login.html", next_path=next_path)


@auth_bp.post("/logout")
def logout():
    session.clear()
    flash("Ти вийшов/вийшла з облікового запису.", "success")
    return redirect(url_for("home"))


@auth_bp.route("/account")
@login_required
def account():
    return render_template(
        "account.html",
        user=g.current_user,
        orders=models.get_user_orders(g.current_user["id"]),
        status_labels=models.STATUS_LABELS,
    )
