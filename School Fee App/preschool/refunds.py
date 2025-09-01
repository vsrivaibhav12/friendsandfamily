from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
from .extensions import db
from .models import Student, Refund, FeeType
from .security import role_required, audit
from .utils import D

refunds_bp = Blueprint('refunds', __name__)

def next_refund_no():
    ts = datetime.now().strftime('%y%m%d%H%M%S')
    return f"RFND-{ts}"

@refunds_bp.route('/new', methods=['GET','POST'])
@role_required(['Owner','Manager'])
def new_refund():
    students = Student.query.order_by(Student.name.asc()).all()
    fee_types = FeeType.query.order_by(FeeType.name.asc()).all()
    if request.method == 'POST':
        student_id = int(request.form['student_id'])
        amount = D(request.form.get('amount') or 0)
        mode = request.form.get('mode','Cash')
        fee_type_id = request.form.get('fee_type_id') or None
        reason = request.form.get('reason','')
        date_str = request.form.get('date'); custom_dt = None
        if date_str:
            try: custom_dt = datetime.strptime(date_str, '%Y-%m-%d')
            except: custom_dt = None
        s = Student.query.get_or_404(student_id)
        if (s.credit_balance or D(0)) < amount:
            flash('Refund exceeds credit balance.','warning')
            return redirect(url_for('refunds.new_refund'))
        r = Refund(refund_no=next_refund_no(), student_id=student_id, fee_type_id=fee_type_id, mode=mode, amount=amount, reason=reason, created_by=current_user.username)
        if custom_dt: r.created_at = custom_dt
        db.session.add(r); s.credit_balance = (s.credit_balance or D(0)) - amount; db.session.commit()
        audit(current_user.username,'CREATE','refund',r.id,{}, {'amount':str(amount),'reason':reason})
        flash(f'Refund {r.refund_no} saved','success')
        return redirect(url_for('refunds.new_refund'))
    rows = Refund.query.order_by(Refund.created_at.desc()).limit(200).all()
    return render_template('receipts/refunds.html', rows=rows, students=students, fee_types=fee_types)
