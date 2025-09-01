from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response
from flask_login import login_required, current_user
from datetime import datetime, date
from .extensions import db
from .models import Student
from .security import role_required, audit
from .utils import D, receivable_for_student, received_for_student, balance_for_student
import csv, io

students_bp = Blueprint('students', __name__)

# ---------- helpers ----------
def parse_iso_date(val):
    """Return a date object from 'YYYY-MM-DD' or None if empty/invalid."""
    if not val:
        return None
    try:
        return date.fromisoformat(val)
    except Exception:
        try:
            return datetime.strptime(val, "%Y-%m-%d").date()
        except Exception:
            return None

# ---------- routes ----------
@students_bp.route('/')
@login_required
def list_students():
    q = request.args.get('q', '').strip()
    cls = request.args.get('class')
    sec = request.args.get('section')

    query = Student.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Student.name.ilike(like)) |
            (Student.admission_no.ilike(like)) |
            (Student.parent_name.ilike(like))
        )
    if cls:
        query = query.filter(Student.class_name == cls)
    if sec:
        query = query.filter(Student.section == sec)

    rows = query.order_by(Student.created_at.desc()).all()
    return render_template('students/list.html', rows=rows, q=q, cls=cls, sec=sec)

@students_bp.route('/new', methods=['GET', 'POST'])
@role_required(['Owner', 'Manager'])
def new_student():
    if request.method == 'POST':
        s = Student(
            admission_no=request.form['admission_no'],
            name=request.form['name'],
            class_name=request.form.get('class_name'),
            section=request.form.get('section'),
            parent_name=request.form.get('parent_name'),
            phone=request.form.get('phone'),
            email=request.form.get('email'),
            discontinued=('discontinued' in request.form),
            collectible_after_discontinue=('collectible_after_discontinue' in request.form),
            discontinued_date=parse_iso_date(request.form.get('discontinued_date')),
        )
        db.session.add(s)
        db.session.commit()
        audit(current_user.username, 'CREATE', 'student', s.id, {}, {'name': s.name})
        flash('Student added', 'success')
        return redirect(url_for('students.list_students'))
    return render_template('students/form.html', s=None)

@students_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@role_required(['Owner', 'Manager'])
def edit_student(id):
    s = Student.query.get_or_404(id)
    if request.method == 'POST':
        before = {
            'name': s.name,
            'admission_no': s.admission_no,
            'discontinued': s.discontinued,
            'collectible_after_discontinue': s.collectible_after_discontinue,
            'discontinued_date': str(s.discontinued_date) if s.discontinued_date else None,
        }
        s.admission_no = request.form['admission_no']
        s.name = request.form['name']
        s.class_name = request.form.get('class_name')
        s.section = request.form.get('section')
        s.parent_name = request.form.get('parent_name')
        s.phone = request.form.get('phone')
        s.email = request.form.get('email')
        s.discontinued = ('discontinued' in request.form)
        s.collectible_after_discontinue = ('collectible_after_discontinue' in request.form)
        s.discontinued_date = parse_iso_date(request.form.get('discontinued_date'))
        db.session.commit()
        audit(current_user.username, 'UPDATE', 'student', s.id, before, {
            'name': s.name,
            'admission_no': s.admission_no,
            'discontinued': s.discontinued,
            'collectible_after_discontinue': s.collectible_after_discontinue,
            'discontinued_date': str(s.discontinued_date) if s.discontinued_date else None,
        })
        flash('Updated', 'success')
        return redirect(url_for('students.list_students'))
    return render_template('students/form.html', s=s)

@students_bp.route('/import', methods=['POST'])
@role_required(['Owner', 'Manager'])
def import_students():
    f = request.files.get('csv')
    if not f:
        flash('Upload a CSV file', 'warning')
        return redirect(url_for('students.list_students'))
    try:
        stream = io.StringIO(f.stream.read().decode('utf-8'))
        reader = csv.DictReader(stream)
        count = 0
        for row in reader:
            if not row.get('admission_no') or not row.get('name'):
                continue
            if Student.query.filter_by(admission_no=row['admission_no']).first():
                continue
            s = Student(
                admission_no=row['admission_no'],
                name=row['name'],
                class_name=row.get('class_name'),
                section=row.get('section'),
                parent_name=row.get('parent_name'),
                phone=row.get('phone'),
                email=row.get('email'),
            )
            db.session.add(s)
            count += 1
        db.session.commit()
        audit(current_user.username, 'IMPORT', 'student', '-', {}, {'count': count})
        flash(f'Imported {count} students', 'success')
    except Exception as e:
        flash(f'Import failed: {e}', 'danger')
    return redirect(url_for('students.list_students'))

@students_bp.route('/import_opening', methods=['POST'])
@role_required(['Owner', 'Manager'])
def import_opening():
    f = request.files.get('csv')
    if not f:
        flash('Upload a CSV file', 'warning')
        return redirect(url_for('students.list_students'))
    stream = io.StringIO(f.stream.read().decode('utf-8'))
    reader = csv.DictReader(stream)
    count = 0
    for row in reader:
        adm = row.get('admission_no')
        if not adm:
            continue
        s = Student.query.filter_by(admission_no=adm).first()
        if not s:
            continue
        if row.get('opening_balance'):
            s.balance_amount = D(row.get('opening_balance'))
        if row.get('credit_balance'):
            s.credit_balance = D(row.get('credit_balance'))
        count += 1
    db.session.commit()
    flash(f'Updated opening balances for {count} students', 'success')
    return redirect(url_for('students.list_students'))

@students_bp.route('/template/students.csv')
def template_students():
    out = (
        'admission_no,name,class_name,section,parent_name,phone,email\n'
        'A001,Jane Doe,Nursery,A,Parent Doe,9876543210,guardian@example.com\n'
    )
    resp = make_response(out)
    resp.headers['Content-Type'] = 'text/csv'
    resp.headers['Content-Disposition'] = 'attachment; filename=students_template.csv'
    return resp

@students_bp.route('/template/opening_balances.csv')
def template_opening():
    out = 'admission_no,opening_balance,credit_balance\nA001,30000,0\n'
    resp = make_response(out)
    resp.headers['Content-Type'] = 'text/csv'
    resp.headers['Content-Disposition'] = 'attachment; filename=opening_balances_template.csv'
    return resp

@students_bp.route('/<int:id>/card')
@login_required
def student_card(id):
    s = Student.query.get_or_404(id)
    receivable = receivable_for_student(id)
    received = received_for_student(id)
    balance = receivable - received
    # history is accessible via relationship: s.receipts
    return render_template(
        'students/card.html',
        s=s,
        receivable=receivable,
        received=received,
        balance=balance
    )
