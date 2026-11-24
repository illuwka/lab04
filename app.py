"""Точка входу застосунку LOQ Market: конфігурація Flask, ініціалізація БД та реєстрація Blueprint."""
import os
from pathlib import Path

from flask import Flask, abort, g, redirect, render_template, request, session, url_for

import models
import seed_data
from routes import admin_bp, auth_bp, feedback_bp, shop_bp

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("LOQ_MARKET_SECRET_KEY", "loq-market-development-key")
Path(app.instance_path).mkdir(parents=True, exist_ok=True)
app.config["DATABASE"] = os.environ.get("DATABASE", str(Path(app.instance_path) / "loq_market.sqlite3"))

models.init_app(app)

with app.app_context():
    models.init_db()
    seed_data.seed()

app.register_blueprint(auth_bp)
app.register_blueprint(feedback_bp)
app.register_blueprint(shop_bp)
app.register_blueprint(admin_bp)


@app.before_request
def load_current_user_and_protect_admin():
    user_id = session.get("user_id")
    g.current_user = models.get_user(user_id) if user_id else None
    if user_id and g.current_user is None:
        session.clear()

    endpoint = request.endpoint or ""
    if endpoint.startswith("admin."):
        if not models.has_admin():
            return redirect(url_for("auth.setup_admin"))
        if g.current_user is None:
            return redirect(url_for("auth.login", next=request.path))
        if g.current_user["role"] != "admin":
            abort(403)


@app.context_processor
def inject_user_navigation():
    return {
        "current_user": getattr(g, "current_user", None),
        "admin_setup_required": not models.has_admin(),
    }


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/about")
def about():
    return render_template("about.html")


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
