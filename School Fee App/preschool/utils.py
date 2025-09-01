# preschool/utils.py
from flask import current_app
from datetime import datetime, date
from decimal import Decimal
from .extensions import db
from .models import SystemSetting, Student, Receipt, StudentFee, AcademicYear
import os
import shutil
import zipfile

D = Decimal

def now():
    return datetime.now()

def school_name():
    s = SystemSetting.query.filter_by(key="school_name").first()
    return s.value if s else "Your School"

def set_setting(key, value):
    s = SystemSetting.query.filter_by(key=key).first()
    if not s:
        s = SystemSetting(key=key, value=str(value))
        db.session.add(s)
    else:
        s.value = str(value)
    db.session.commit()

def get_setting(key, default=None):
    s = SystemSetting.query.filter_by(key=key).first()
    return s.value if s else default

def get_active_year_name():
    ay = AcademicYear.query.filter_by(is_active=True).first()
    return ay.name if ay else "Unset"

def next_receipt_no():
    mode = get_setting("receipt_number_mode", "auto")
    if mode == 'manual':
        return None

    prefix = get_setting("receipt_prefix", "AY")
    active_year = get_active_year_name()
    year_str = active_year.replace('-', '') if active_year != "Unset" else str(datetime.now().year)
    prefix = prefix.replace("AY", year_str)
    
    seq_key = f"receipt_seq_{active_year}"
    setting = SystemSetting.query.filter_by(key=seq_key).first()
    
    if not setting:
        global_seq = get_setting("receipt_seq", "1")
        n = int(global_seq)
        setting = SystemSetting(key=seq_key, value=str(n + 1))
        db.session.add(setting)
    else:
        n = int(setting.value)
        setting.value = str(n + 1)

    db.session.commit()
    return f"{prefix}-R-{n:04d}"

def ensure_default_dirs(app):
    for p in (app.config.get("UPLOAD_FOLDER"), app.config.get("BACKUP_FOLDER"), app.instance_path):
        if p and not os.path.exists(p):
            os.makedirs(p, exist_ok=True)

# ADDED: The missing backup_sqlite function
def backup_sqlite():
    """Creates a timestamped zip backup of the SQLite database."""
    db_path_str = current_app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")
    db_path = os.path.normpath(db_path_str)
    
    if not os.path.exists(db_path):
        return "Error: Database file not found."

    backup_folder = current_app.config["BACKUP_FOLDER"]
    ensure_default_dirs(current_app)

    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    zip_filename = f"backup-{stamp}.zip"
    zip_path = os.path.join(backup_folder, zip_filename)

    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(db_path, os.path.basename(db_path))
        return zip_path
    except Exception as e:
        return f"Error creating backup: {e}"

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