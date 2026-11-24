"""Маршрути сторінки контактів та зворотного зв’язку."""
from flask import Blueprint, flash, redirect, render_template, request, url_for

import models

feedback_bp = Blueprint("feedback", __name__)


@feedback_bp.route("/contacts", methods=["GET", "POST"])
def contacts():
    if request.method == "POST":
        name, email, message = (request.form.get(key, "").strip() for key in ("name", "email", "message"))
        if not name or not email or "@" not in email or not message:
            flash("Заповни всі поля та вкажи коректну електронну адресу.", "error")
        else:
            models.create_feedback(name, email, message)
            flash("Дякуємо! Твій відгук збережено.", "success")
        return redirect(url_for("feedback.contacts"))
    return render_template("contacts.html")
