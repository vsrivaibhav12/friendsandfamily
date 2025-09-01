# preschool/fees.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from .extensions import db
from .models import Student, FeeType
# Fee plan model name can vary; try the typical class
try:
    from .models import FeePlan
except Exception:
    FeePlan = None
# optional mapping table if your schema uses many-to-many
try:
    from .models import StudentPlan
except Exception:
    StudentPlan = None

fees_bp = Blueprint('fees', __name__)

@fees_bp.route('/fees/types')
@login_required
def types():
    rows = FeeType.query.order_by(FeeType.name.asc()).all()
    return render_template('fees/types.html', rows=rows)

@fees_bp.route('/fees/plans')
@login_required
def plans():
    plans = FeePlan.query.order_by(FeePlan.name.asc()).all() if FeePlan else []
    return render_template('fees/plans.html', plans=plans)

@fees_bp.route('/fees/bulk-assign', methods=['GET', 'POST'])
@login_required
def bulk_assign():
    if request.method == 'POST':
        plan_id = int(request.form['plan_id'])
        student_ids = request.form.getlist('student_ids')
        if not student_ids:
            flash('Please select at least one student.', 'warning')
            return redirect(url_for('fees.bulk_assign'))

        count = 0
        for sid in student_ids:
            s = Student.query.get(int(sid))
            if not s:
                continue
            # If Student has a plan_id field
            if hasattr(s, 'plan_id'):
                s.plan_id = plan_id
                count += 1
            elif StudentPlan is not None:
                db.session.add(StudentPlan(student_id=s.id, plan_id=plan_id))
                count += 1
            # else: no known place to store; skip

        db.session.commit()
        flash(f'Assigned plan to {count} student(s).', 'success')
        return redirect(url_for('fees.bulk_assign'))

    students = Student.query.order_by(Student.class_name.asc(), Student.section.asc(), Student.name.asc()).all()
    plans = FeePlan.query.order_by(FeePlan.name.asc()).all() if FeePlan else []
    return render_template('fees/bulk_assign.html', students=students, plans=plans)
