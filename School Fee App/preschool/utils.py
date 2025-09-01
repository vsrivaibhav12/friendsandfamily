from datetime import datetime, date
from decimal import Decimal
from .extensions import db
from .models import SystemSetting, Student, Receipt, ReceiptItem, StudentFee

D = Decimal

def now():
    return datetime.now()

def school_name():
    s = SystemSetting.query.filter_by(key="school_name").first()
    return s.value if s else "Your School"

def set_setting(key, value):
    s = SystemSetting.query.filter_by(key=key).first()
    if not s:
        s = SystemSetting(key=key, value=value)
        db.session.add(s)
    else:
        s.value = value
    db.session.commit()

def receipt_next_number():
    """CY<year>-R-xxxx"""
    year = datetime.now().year
    key = f"rcpt_counter_{year}"
    row = SystemSetting.query.filter_by(key=key).first()
    n = int(row.value) if row else 0
    n += 1
    if row:
        row.value = str(n)
    else:
        db.session.add(SystemSetting(key=key, value=str(n)))
    db.session.commit()
    return f"CY{year}-R-{n:04d}"

def ensure_default_dirs(app):
    import os
    for p in (app.config["UPLOAD_FOLDER"], app.config["BACKUP_FOLDER"], app.instance_path):
        os.makedirs(p, exist_ok=True)

# -------------- business helpers -----------------

def receivable_for_student(student_id):
    rows = StudentFee.query.filter_by(student_id=student_id).all()
    return sum((r.amount or 0) for r in rows) or D(0)

def received_for_student(student_id):
    from sqlalchemy import func
    amt = db.session.query(func.coalesce(func.sum(Receipt.amount), 0)).filter(
        Receipt.student_id == student_id
    ).scalar() or 0
    return D(amt)
