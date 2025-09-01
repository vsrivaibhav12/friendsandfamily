# preschool/reports.py
from flask import Blueprint, render_template, request, Response
from flask_login import login_required
from sqlalchemy import func, or_, and_, true
from datetime import datetime
from .extensions import db
from .models import Student, Receipt, ReceiptItem, FeeType
from .utils import D, receivable_for_student, received_for_student

reports_bp = Blueprint("reports", __name__)

# --------------------------- helpers -----------------------------------------

def has_col(model, name: str) -> bool:
    """Return True if ORM model has a DB column with this name."""
    try:
        return name in model.__table__.columns
    except Exception:
        return False

def _student_balance(student_id: int) -> D:
    """Receivable - Received for a student, Decimal (>= 0)."""
    rcv = receivable_for_student(student_id) or D(0)
    rec = received_for_student(student_id) or D(0)
    bal = rcv - rec
    return bal if bal > D(0) else D(0)

def _rows_with_balance(q):
    """Return [(student, balance>0)] sorted desc by balance."""
    rows = []
    for s in q:
        bal = _student_balance(s.id)
        if bal > D(0):
            rows.append((s, bal))
    rows.sort(key=lambda t: t[1], reverse=True)
    return rows

# --------------------------- pages -------------------------------------------

@reports_bp.route("/summary")
@login_required
def summary():
    students = Student.query.order_by(Student.name.asc()).all()

    total_students = len(students)
    receivable_sum = D(0)
    received_sum = D(0)
    overdue_rows = []

    has_discontinued = has_col(Student, "discontinued")
    # support either `collectible` or legacy `collectible_after_discontinue`
    collectible_col = "collectible" if has_col(Student, "collectible") else (
        "collectible_after_discontinue" if has_col(Student, "collectible_after_discontinue") else None
    )

    for s in students:
        rcv = receivable_for_student(s.id) or D(0)
        rec = received_for_student(s.id) or D(0)
        bal = rcv - rec
        receivable_sum += rcv
        received_sum += rec

        is_active = True
        if has_discontinued:
            is_active = not bool(getattr(s, "discontinued") or False)

        is_collectible = False
        if collectible_col:
            is_collectible = bool(getattr(s, collectible_col) or False)

        if bal > D(0) and (is_active or is_collectible):
            overdue_rows.append((s, bal))

    overdue_rows.sort(key=lambda t: t[1], reverse=True)
    top_overdue = overdue_rows[:10]
    overdue_count = len(overdue_rows)
    balance_sum = receivable_sum - received_sum

    return render_template(
        "reports/summary.html",
        total_students=total_students,
        receivable_sum=receivable_sum,
        received_sum=received_sum,
        balance_sum=balance_sum,
        overdue_count=overdue_count,
        top_overdue=top_overdue,
    )

@reports_bp.route("/overdue")
@login_required
def overdue():
    """Students with positive receivable:
       - Always include active students.
       - If the schema has (discontinued, collectible), also include discontinued & collectible.
    """
    has_discontinued = has_col(Student, "discontinued")
    collectible_attr = "collectible" if has_col(Student, "collectible") else (
        "collectible_after_discontinue" if has_col(Student, "collectible_after_discontinue") else None
    )

    cond_active = true()
    if has_discontinued:
        cond_active = or_(Student.discontinued == False, Student.discontinued.is_(None))

    if has_discontinued and collectible_attr:
        cond_collectible = and_(Student.discontinued == True, getattr(Student, collectible_attr) == True)
        base_q = Student.query.filter(or_(cond_active, cond_collectible))
    else:
        base_q = Student.query.filter(cond_active)

    q = base_q.order_by(Student.class_name.asc(), Student.section.asc(), Student.name.asc())
    rows = _rows_with_balance(q)
    return render_template("reports/overdue.html", rows=rows)

@reports_bp.route("/overdue.csv")
@login_required
def overdue_csv():
    has_discontinued = has_col(Student, "discontinued")
    collectible_attr = "collectible" if has_col(Student, "collectible") else (
        "collectible_after_discontinue" if has_col(Student, "collectible_after_discontinue") else None
    )
    cond_active = true()
    if has_discontinued:
        cond_active = or_(Student.discontinued == False, Student.discontinued.is_(None))
    if has_discontinued and collectible_attr:
        cond_collectible = and_(Student.discontinued == True, getattr(Student, collectible_attr) == True)
        base_q = Student.query.filter(or_(cond_active, cond_collectible))
    else:
        base_q = Student.query.filter(cond_active)

    q = base_q.order_by(Student.class_name.asc(), Student.section.asc(), Student.name.asc())
    rows = [(s, _student_balance(s.id)) for s in q if _student_balance(s.id) > D(0)]

    def gen():
        yield "Admission No,Name,Class,Section,Phone,Receivable\n"
        for s, bal in rows:
            yield f"{s.admission_no or ''},{s.name or ''},{s.class_name or ''},{s.section or ''},{s.phone or ''},{float(bal):.2f}\n"

    return Response(gen(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=overdue.csv"})

@reports_bp.route("/income")
@login_required
def income():
    """Income by Fee Type (sum of receipt items)."""
    date_from = request.args.get("from")
    date_to = request.args.get("to")

    ri = db.session.query(
        FeeType.name.label("fee_name"),
        func.sum(ReceiptItem.amount).label("amount"),
    ).join(FeeType, FeeType.id == ReceiptItem.fee_type_id)

    if date_from:
        try:
            ri = ri.filter(ReceiptItem.created_at >= datetime.strptime(date_from, "%Y-%m-%d"))
        except Exception:
            pass
    if date_to:
        try:
            ri = ri.filter(ReceiptItem.created_at < datetime.strptime(date_to, "%Y-%m-%d"))
        except Exception:
            pass

    rows = ri.group_by(FeeType.name).order_by(FeeType.name.asc()).all()
    total = D(sum((r.amount or 0) for r in rows))
    return render_template("reports/income.html", rows=rows, total=total,
                           date_from=date_from, date_to=date_to)

@reports_bp.route("/income.csv")
@login_required
def income_csv():
    ri = db.session.query(
        FeeType.name.label("fee_name"),
        func.sum(ReceiptItem.amount).label("amount"),
    ).join(FeeType, FeeType.id == ReceiptItem.fee_type_id) \
     .group_by(FeeType.name).order_by(FeeType.name.asc()).all()

    def gen():
        yield "Fee Type,Amount\n"
        for r in ri:
            amt = f"{float(r.amount or 0):.2f}"
            yield f"{r.fee_name},{amt}\n"

    return Response(gen(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=income_by_fee_type.csv"})

@reports_bp.route("/discontinued/collectible")
@login_required
def discontinued_collectible():
    has_discontinued = has_col(Student, "discontinued")
    collectible_attr = "collectible" if has_col(Student, "collectible") else (
        "collectible_after_discontinue" if has_col(Student, "collectible_after_discontinue") else None
    )
    if not (has_discontinued and collectible_attr):
        return render_template("reports/discontinued.html", rows=[], title="Discontinued & Collectible", kind="collectible")

    q = Student.query.filter(
        (Student.discontinued == True) &
        (getattr(Student, collectible_attr) == True)
    ).order_by(Student.class_name.asc(), Student.section.asc(), Student.name.asc())
    rows = _rows_with_balance(q)
    return render_template("reports/discontinued.html",
                           rows=rows, title="Discontinued & Collectible", kind="collectible")

@reports_bp.route("/discontinued/noncollectible")
@login_required
def discontinued_noncollectible():
    has_discontinued = has_col(Student, "discontinued")
    collectible_attr = "collectible" if has_col(Student, "collectible") else (
        "collectible_after_discontinue" if has_col(Student, "collectible_after_discontinue") else None
    )
    if not (has_discontinued and collectible_attr):
        return render_template("reports/discontinued.html", rows=[], title="Discontinued (Non-collectible)", kind="noncollectible")

    q = Student.query.filter(
        (Student.discontinued == True) &
        (getattr(Student, collectible_attr) == False)
    ).order_by(Student.class_name.asc(), Student.section.asc(), Student.name.asc())
    rows = _rows_with_balance(q)
    return render_template("reports/discontinued.html",
                           rows=rows, title="Discontinued (Non-collectible)", kind="noncollectible")

# -------- CSV export for discontinued variants -------------------------------

@reports_bp.route("/discontinued.csv")
@login_required
def discontinued_csv():
    """Export Discontinued lists to CSV. Use ?kind=collectible|noncollectible."""
    kind = (request.args.get("kind") or "collectible").lower()
    has_discontinued = has_col(Student, "discontinued")
    collectible_attr = "collectible" if has_col(Student, "collectible") else (
        "collectible_after_discontinue" if has_col(Student, "collectible_after_discontinue") else None
    )

    rows = []
    if has_discontinued and collectible_attr:
        if kind == "noncollectible":
            q = Student.query.filter(
                (Student.discontinued == True) & (getattr(Student, collectible_attr) == False)
            ).order_by(Student.class_name.asc(), Student.section.asc(), Student.name.asc())
        else:
            q = Student.query.filter(
                (Student.discontinued == True) & (getattr(Student, collectible_attr) == True)
            ).order_by(Student.class_name.asc(), Student.section.asc(), Student.name.asc())
        rows = [(s, _student_balance(s.id)) for s in q]

    def gen():
        yield "Admission No,Name,Class,Section,Phone,Receivable\n"
        for s, bal in rows:
            yield f"{s.admission_no or ''},{s.name or ''},{s.class_name or ''},{s.section or ''},{s.phone or ''},{float(bal):.2f}\n"

    filename = f"discontinued_{kind}.csv"
    return Response(gen(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})
