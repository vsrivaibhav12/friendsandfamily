# preschool/receipts.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
from .extensions import db
from .models import Student, FeeType, Receipt, ReceiptItem
# MODIFIED: Correctly importing the updated utility functions
from .utils import D, next_receipt_no, get_active_year_name

receipts_bp = Blueprint('receipts', __name__)

@receipts_bp.route('/', methods=['GET'])
@login_required
def list_receipts():
    rows = Receipt.query.order_by(Receipt.created_at.desc(), Receipt.id.desc()).limit(200).all()
    return render_template('receipts/list.html', rows=rows)

@receipts_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_receipt():
    if request.method == 'POST':
        try:
            student_id = int(request.form['student_id'])
            mode = request.form.get('mode') or 'Cash'
            notes = request.form.get('notes') or ''

            rec_no = next_receipt_no() # This will be None if mode is manual
            if rec_no is None:
                rec_no = (request.form.get('receipt_no') or '').strip()
                if not rec_no:
                    flash('Receipt number is required in manual numbering mode.', 'danger')
                    return redirect(url_for('receipts.new_receipt'))

            # Start transaction
            total = D(0)
            items_to_add = []
            for ft in FeeType.query.order_by(FeeType.name.asc()).all():
                key = f'amt_{ft.id}'
                if key in request.form:
                    amt_str = request.form.get(key) or '0'
                    if amt_str:
                        amt = D(amt_str)
                        if amt > 0:
                            items_to_add.append({'fee_type_id': ft.id, 'amount': amt})
                            total += amt

            if total == 0:
                flash('Please enter at least one amount.', 'warning')
                return redirect(url_for('receipts.new_receipt'))
            
            rec = Receipt(receipt_no=rec_no, student_id=student_id, mode=mode, amount=total,
                          notes=notes, created_by=current_user.username, created_at=datetime.utcnow())
            db.session.add(rec)
            db.session.flush()  # get id for receipt items

            for item_data in items_to_add:
                db.session.add(ReceiptItem(receipt_id=rec.id, **item_data))

            db.session.commit()
            flash('Receipt created.', 'success')
            return redirect(url_for('receipts.print_receipt', receipt_id=rec.id))

        except (ValueError, TypeError):
             flash('Invalid amount entered. Please use numbers only.', 'danger')
             db.session.rollback()
             return redirect(url_for('receipts.new_receipt'))
        except Exception as e:
            flash(f'An unexpected error occurred: {e}', 'danger')
            db.session.rollback()
            return redirect(url_for('receipts.new_receipt'))


    students = Student.query.order_by(Student.class_name.asc(), Student.section.asc(), Student.name.asc()).all()
    fee_types = FeeType.query.order_by(FeeType.name.asc()).all()
    return render_template('receipts/new.html', students=students, fee_types=fee_types, active_year=get_active_year_name())

@receipts_bp.route('/<int:receipt_id>/print', methods=['GET'])
@login_required
def print_receipt(receipt_id: int):
    rec = Receipt.query.get_or_404(receipt_id)
    return render_template('receipts/print.html', rec=rec)