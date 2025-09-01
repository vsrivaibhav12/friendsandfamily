# preschool/models.py
from datetime import datetime, date
from .extensions import db
from flask_login import UserMixin
from passlib.hash import bcrypt

# ---------------- Users ----------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    full_name = db.Column(db.String(120))
    role = db.Column(db.String(20), default="DataEntry")  # Owner, Manager, Cashier, DataEntry
    password_hash = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, default=True)
    last_login_at = db.Column(db.DateTime)

    def set_password(self, raw):
        self.password_hash = bcrypt.hash(raw)

    def check_password(self, raw) -> bool:
        try:
            return bcrypt.verify(raw, self.password_hash)
        except Exception:
            return False

# ---------------- Settings ----------------
class SystemSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False)
    value = db.Column(db.String(400))

# ADDED: The missing AcademicYear model
class AcademicYear(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), unique=True, nullable=False)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    is_active = db.Column(db.Boolean, default=False)

# ---------------- Catalog ----------------
class FeeType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)

# ---------------- Students ----------------
class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admission_no = db.Column(db.String(40), unique=True)
    name = db.Column(db.String(120), nullable=False)
    class_name = db.Column(db.String(50))
    section = db.Column(db.String(20))
    parent_name = db.Column(db.String(120)) # Added parent_name
    phone = db.Column(db.String(40))
    email = db.Column(db.String(120)) # Added email
    discontinued = db.Column(db.Date)      # null => active
    collectible = db.Column(db.Boolean)     # if discontinued and collectible = True => show in collectible report
    balance_amount = db.Column(db.Numeric(12, 2), default=0) # Added balance_amount
    credit_balance = db.Column(db.Numeric(12, 2), default=0) # Added credit_balance
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    fees = db.relationship("StudentFee", backref="student", cascade="all, delete-orphan")
    receipts = db.relationship("Receipt", backref="student")

    def is_active(self):
        return self.discontinued is None

    def total_receivable(self):
        from decimal import Decimal
        return sum((f.amount or 0) for f in self.fees) or Decimal(0)

    def total_received(self):
        from sqlalchemy import func
        from decimal import Decimal
        amt = db.session.query(func.coalesce(func.sum(Receipt.amount), 0)).filter(Receipt.student_id == self.id).scalar() or 0
        return Decimal(amt)

    def balance(self):
        from decimal import Decimal
        return Decimal(self.total_receivable()) - Decimal(self.total_received())

class StudentFee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    fee_type_id = db.Column(db.Integer, db.ForeignKey('fee_type.id'), nullable=False)
    amount = db.Column(db.Numeric(12, 2), default=0)

    fee_type = db.relationship("FeeType")

# ---------------- Receipts ----------------
class Receipt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    receipt_no = db.Column(db.String(40), unique=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    amount = db.Column(db.Numeric(12,2), default=0)
    mode = db.Column(db.String(20))  # Cash / UPI / Card / Bank
    notes = db.Column(db.String(255)) # Added notes
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(80))

    items = db.relationship("ReceiptItem", backref="receipt", cascade="all, delete-orphan")

class ReceiptItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    receipt_id = db.Column(db.Integer, db.ForeignKey('receipt.id'), nullable=False)
    fee_type_id = db.Column(db.Integer, db.ForeignKey('fee_type.id'), nullable=False)
    amount = db.Column(db.Numeric(12,2), default=0)
    fee_type = db.relationship("FeeType")

# ---------------- Waivers / Refunds ----------------
class Waiver(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    fee_type_id = db.Column(db.Integer, db.ForeignKey('fee_type.id'))
    amount = db.Column(db.Numeric(12,2), default=0)
    percent = db.Column(db.Numeric(5, 2)) # Added percent
    reason = db.Column(db.String(255))
    approved = db.Column(db.Boolean, default=False) # Added approved
    approved_by = db.Column(db.String(80)) # Added approved_by
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ADDED: The missing Refund model
class Refund(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    refund_no = db.Column(db.String(40), unique=True, nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    fee_type_id = db.Column(db.Integer, db.ForeignKey('fee_type.id'))
    mode = db.Column(db.String(20))
    amount = db.Column(db.Numeric(12, 2))
    reason = db.Column(db.String(255))
    created_by = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    student = db.relationship("Student")

# ---------------- Reconciliation ----------------
class CashCount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    amount_counted = db.Column(db.Numeric(12,2), default=0)
    expected = db.Column(db.Numeric(12,2), default=0)
    variance = db.Column(db.Numeric(12,2), default=0)
    notes = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PhonePeFeeRule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    percent = db.Column(db.Numeric(6,3))
    flat = db.Column(db.Numeric(12,2))
    active = db.Column(db.Boolean, default=True) # Added active

class SettlementBatch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(40))  # "UPI"
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    days_grouping = db.Column(db.Integer, default=2)
    rule_id = db.Column(db.Integer, db.ForeignKey('phone_pe_fee_rule.id'))
    gross = db.Column(db.Numeric(12,2), default=0)       # sum of receipts during period
    charges = db.Column(db.Numeric(12,2), default=0)
    expected_net = db.Column(db.Numeric(12,2), default=0)
    bank_net = db.Column(db.Numeric(12,2), default=0)
    variance = db.Column(db.Numeric(12,2), default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    rule = db.relationship("PhonePeFeeRule")

# ADDED: AuditLog model, which was used but not defined
class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    actor = db.Column(db.String(80))
    action = db.Column(db.String(40))
    table = db.Column(db.String(40))
    record_id = db.Column(db.String(80))
    before_json = db.Column(db.Text)
    after_json = db.Column(db.Text)
    reason = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)