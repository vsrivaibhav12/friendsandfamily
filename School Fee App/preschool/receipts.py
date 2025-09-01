# preschool/receipts.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
from .extensions import db
from .models import Student, FeeType, Receipt, ReceiptItem
from .utils import D, next_receipt_no, get_active_year_name

receipts_bp = Blueprint('receipts', __name__)

@receipts_bp.route('/receipts', methods=['GET'])
@login_required
def list_receipts():
    rows = Receipt.query.order_by(Receipt.created_at.desc(), Receipt.id.desc()).limit(200).all()
    return render_template('receipts/list.html', rows=rows)

@receipts_bp.route('/receipts/new', methods=['GET', 'POST'])
@login_required
def new_receipt():
    if request.method == 'POST':
        student_id = int(request.form['student_id'])
        mode = request.form.get('mode') or 'Cash'
        notes = request.form.get('notes') or ''

        # Auto or manual numbering
        rec_no = next_receipt_no()
        if rec_no is None:
            rec_no = (request.form.get('receipt_no') or '').strip()
            if not rec_no:
                flash('Receipt number is required in manual mode.', 'danger')
                return redirect(url_for('receipts.new_receipt'))

        rec = Receipt(receipt_no=rec_no, student_id=student_id, mode=mode, amount=D(0),
                      notes=notes, created_by=current_user.username, created_at=datetime.utcnow())
        db.session.add(rec)
        db.session.flush()  # get id

        total = D(0)
        for ft in FeeType.query.order_by(FeeType.name.asc()).all():
            key = f'amt_{ft.id}'
            if key in request.form:
                try:
                    amt = D(request.form.get(key) or 0)
                except Exception:
                    amt = D(0)
                if amt > 0:
                    db.session.add(ReceiptItem(receipt_id=rec.id, fee_type_id=ft.id, amount=amt))
                    total += amt

        if total == 0:
            db.session.rollback()
            flash('Please enter at least one amount.', 'warning')
            return redirect(url_for('receipts.new_receipt'))

        rec.amount = total
        db.session.commit()

        flash('Receipt created.', 'success')
        return redirect(url_for('receipts.print_receipt', receipt_id=rec.id))

    students = Student.query.order_by(Student.class_name.asc(), Student.section.asc(), Student.name.asc()).all()
    fee_types = FeeType.query.order_by(FeeType.name.asc()).all()
    current_year = datetime.utcnow().year  # Calendar year display, as requested
    return render_template('receipts/new.html', students=students, fee_types=fee_types, current_year=current_year, active_year=get_active_year_name())

@receipts_bp.route('/receipts/<int:receipt_id>/print', methods=['GET'])
@login_required
def print_receipt(receipt_id: int):
    rec = Receipt.query.get_or_404(receipt_id)
    items = ReceiptItem.query.filter_by(receipt_id=receipt_id).join(FeeType, FeeType.id == ReceiptItem.fee_type_id)\
            .add_columns(FeeType.name.label('fee_name'), ReceiptItem.amount).all()
    return render_template('receipts/print.html', rec=rec, items=items)
