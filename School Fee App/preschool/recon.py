# preschool/recon.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from .extensions import db
from .models import CashCount, Receipt, SettlementBatch, PhonePeFeeRule
from .security import role_required, audit
from .utils import D

recon_bp = Blueprint('recon', __name__)

# --- Legacy routes -> keep old bookmarks working -----------------------------

@recon_bp.route('/bank', methods=['GET'], endpoint='bank')
def bank_redirect():
    # Old URL /recon/bank now lands on the UPI tab
    return redirect(url_for('recon.home') + '#upi')

@recon_bp.route('/cash-legacy', methods=['GET'], endpoint='cash_legacy')
def cash_legacy_redirect():
    # If any template linked to /recon/cash-legacy, send them to Cash tab
    return redirect(url_for('recon.home') + '#cash')

@recon_bp.route('/settlements', methods=['GET'], endpoint='settlements')
def settlements_redirect():
    # Old URL /recon/settlements -> UPI tab
    return redirect(url_for('recon.home') + '#upi')

# --- New unified reconciliation UI -------------------------------------------

@recon_bp.route('/', methods=['GET'])
@login_required
def home():
    """Unified Reconciliation page with tabs: Cash and UPI Settlements."""
    cash_rows = CashCount.query.order_by(CashCount.date.desc(), CashCount.id.desc()).limit(50).all()
    batches = SettlementBatch.query.order_by(SettlementBatch.start_date.desc(), SettlementBatch.id.desc()).limit(50).all()
    try:
        rules = PhonePeFeeRule.query.order_by(PhonePeFeeRule.name.asc()).all()
    except Exception:
        rules = []
    return render_template('recon/index.html', cash_rows=cash_rows, batches=batches, rules=rules)

@recon_bp.route('/cash', methods=['POST'])
@role_required(['Owner', 'Manager', 'Cashier'])
def cash_submit():
    d = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
    counted = D(request.form.get('amount_counted') or 0)
    notes = request.form.get('notes') or ''

    cash_total = db.session.query(db.func.coalesce(db.func.sum(Receipt.amount), 0)).filter(
        db.func.date(Receipt.created_at) == d,
        Receipt.mode == 'Cash'
    ).scalar() or 0
    cash_total = D(cash_total)

    variance = counted - cash_total

    row = CashCount(date=d, amount_counted=counted, expected=cash_total, variance=variance, notes=notes)
    db.session.add(row)
    db.session.commit()

    audit(actor=current_user.username, action='CREATE', table='cash_count', record_id=str(row.id),
          before=None, after={'date': str(d), 'counted': float(counted), 'expected': float(cash_total), 'variance': float(variance)}, reason='cash reconciliation')

    flash('Cash reconciliation saved.', 'success')
    return redirect(url_for('recon.home') + '#cash')

@recon_bp.route('/settlements/new', methods=['POST'], endpoint='settlements_new')
@role_required(['Owner', 'Manager'])
def settlements_new():
    start = datetime.strptime(request.form['start'], '%Y-%m-%d').date()
    days = int(request.form.get('days', '2'))
    end = start + timedelta(days=days - 1)

    rid = request.form.get('rule_id')
    rule = PhonePeFeeRule.query.get(int(rid)) if (rid and rid.strip()) else None

    receipts_total = db.session.query(db.func.coalesce(db.func.sum(Receipt.amount), 0)).filter(
        db.func.date(Receipt.created_at) >= start,
        db.func.date(Receipt.created_at) <= end,
        Receipt.mode.in_(['UPI', 'UPI-PhonePe', 'UPI-GPay', 'UPI-Paytm', 'UPI-Other'])
    ).scalar() or 0
    receipts_total = D(receipts_total)

    override_pct = request.form.get('override_percent')
    override_flat = request.form.get('override_flat')
    charges = D(0)
    if override_pct:
        charges += (receipts_total * D(override_pct)) / D(100)
    if override_flat:
        charges += D(override_flat)
    if charges == 0 and rule is not None:
        if getattr(rule, 'percent', None):
            charges += (receipts_total * D(rule.percent)) / D(100)
        if getattr(rule, 'flat', None):
            charges += D(rule.flat)

    expected_net = receipts_total - charges
    bank_net = D(request.form.get('bank_amount') or 0)
    variance = bank_net - expected_net

    b = SettlementBatch(start_date=start, end_date=end, provider="UPI",
                        days_grouping=days, rule_id=getattr(rule, 'id', None),
                        gross=receipts_total, charges=charges, expected_net=expected_net,
                        bank_net=bank_net, variance=variance)
    db.session.add(b)
    db.session.commit()

    audit(actor=current_user.username, action='CREATE', table='settlement_batch', record_id=str(b.id),
          before=None, after={'start': str(start), 'end': str(end),
                              'gross': float(receipts_total), 'charges': float(charges),
                              'expected_net': float(expected_net), 'bank_net': float(bank_net),
                              'variance': float(variance)}, reason='upi settlement')

    flash('UPI settlement saved.', 'success')
    return redirect(url_for('recon.home') + '#upi')
