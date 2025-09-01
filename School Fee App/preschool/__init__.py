# preschool/__init__.py
from flask import Flask, render_template
from flask_login import login_required
from datetime import datetime, date as _date
from .extensions import db, login_manager
from .auth import auth_bp
from .students import students_bp
from .fees import fees_bp
from .receipts import receipts_bp
from .recon import recon_bp
from .reports import reports_bp
from .admin import admin_bp
from .refunds import refunds_bp
from .settings import settings_bp
from .dbfix import ensure_schema
from .utils import ensure_default_dirs, school_name, next_receipt_no

def create_app():
    # MODIFIED: Changed how the Flask app is created to be more explicit.
    # We now use the package name 'preschool' directly.
    app = Flask(
        "preschool",
        template_folder="templates",
        static_folder="static"
    )
    app.config.from_object('config.Config')

    ensure_default_dirs(app)
    db.init_app(app)
    login_manager.init_app(app)

    with app.app_context():
        from .models import User
        db.create_all()
        ensure_schema(db)
        # seed default owner
        if not User.query.filter_by(username="owner").first():
            u = User(username="owner", full_name="Owner", role="Owner")
            u.set_password("owner123")
            db.session.add(u)
            db.session.commit()

    # Inject handy template helpers
    @app.context_processor
    def inject_helpers():
        from .utils import now
        return dict(now=now, school_name=school_name, receipt_next_number=next_receipt_no)

    # Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(students_bp, url_prefix="/students")
    app.register_blueprint(fees_bp, url_prefix="/fees")
    app.register_blueprint(receipts_bp, url_prefix="/receipts")
    app.register_blueprint(recon_bp, url_prefix="/recon")
    app.register_blueprint(reports_bp, url_prefix="/reports")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(refunds_bp, url_prefix="/refunds")
    app.register_blueprint(settings_bp, url_prefix="/settings")

    @app.route("/")
    @login_required
    def index():
        from .models import Student, StudentFee, Receipt
        from .utils import D
        from sqlalchemy import func
        
        receivable = db.session.query(func.sum(StudentFee.amount)).scalar() or D(0)
        received = db.session.query(func.coalesce(func.sum(Receipt.amount), 0)).scalar() or D(0)
        balance = receivable - received
        
        top = [(s, s.balance()) for s in Student.query.all() if s.balance() > 0]
        top.sort(key=lambda x: x[1], reverse=True)
        top = top[:10]
        
        return render_template("dashboard.html",
                               receivable=receivable,
                               received=received,
                               balance=balance,
                               top_overdue=top)

    @app.route("/healthz")
    def healthz():
        return "ok", 200

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500

    return app