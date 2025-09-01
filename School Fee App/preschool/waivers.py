# preschool/waivers.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from .extensions import db
from .models import Waiver, Student, FeeType
from .security import role_required, audit
from .utils import D

waivers_bp = Blueprint('waivers', __name__)

@waivers_bp.route('/', methods=['GET','POST'])
@role_required(['Owner','Manager'])
def list_create():
    students = Student.query.order_by(Student.name.asc()).all()
    types = FeeType.query.order_by(FeeType.name.asc()).all()
    if request.method == 'POST':
        try:
            # ADDED: Input validation
            student_id = int(request.form['student_id'])
            fee_type_id = int(request.form['fee_type_id'])
            amount = D(request.form.get('amount') or 0)
            percent = D(request.form.get('percent') or 0)
        except (ValueError, TypeError):
            flash('Invalid input. Please check the numbers you entered.', 'danger')
            return redirect(url_for('waivers.list_create'))

        reason = request.form.get('reason','')
        w = Waiver(student_id=student_id, fee_type_id=fee_type_id, amount=amount, percent=percent, reason=reason)
        db.session.add(w); db.session.commit()
        audit(current_user.username,'CREATE','waiver',w.id,{}, {'reason':reason})
        flash('Waiver created; pending approval','success')
        return redirect(url_for('waivers.list_create'))
    rows = Waiver.query.order_by(Waiver.created_at.desc()).limit(100).all()
    return render_template('waivers/list.html', rows=rows, students=students, types=types)

@waivers_bp.route('/<int:id>/approve', methods=['POST'])
@role_required(['Owner','Manager'])
def approve(id):
    w = Waiver.query.get_or_404(id)
    if w.approved:
        flash('Already approved','info')
        return redirect(url_for('waivers.list_create'))
    before = {'approved': w.approved}
    w.approved = True; w.approved_by = current_user.username
    s = Student.query.get(w.student_id)
    reduction = D(w.amount or 0)
    if reduction == D(0) and w.percent:
        total = sum([D(p.amount_total or 0) for p in s.fee_plans if p.fee_type_id == w.fee_type_id], D(0))
        reduction = (total * D(w.percent) / D(100))
    s.balance_amount = (s.balance_amount or D(0)) - reduction
    db.session.commit()
    audit(current_user.username,'APPROVE','waiver',w.id,before, {'approved':True}, reason=w.reason)
    flash(f'Waiver approved. Reduced balance by ₹{reduction}','success')
    return redirect(url_for('waivers.list_create'))