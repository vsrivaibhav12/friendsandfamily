from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
from .extensions import db, login_manager
from .models import User

auth_bp = Blueprint("auth", __name__)

@login_manager.user_loader
def load_user(uid):
    return User.query.get(int(uid))

@auth_bp.route("/login", methods=["GET","POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        u = User.query.filter_by(username=request.form["username"].strip()).first()
        if u and u.check_password(request.form["password"]):
            login_user(u, remember=True)
            return redirect(request.args.get("next") or url_for("index"))
        error = "Invalid username or password"
    return render_template("login.html", error=error)

@auth_bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
