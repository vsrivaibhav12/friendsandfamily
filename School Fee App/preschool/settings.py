from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from datetime import date
from .extensions import db
from .models import AcademicYear, FeeType, PhonePeFeeRule
from .utils import set_setting, get_setting, backup_sqlite

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/')
@login_required
def index():
    ay = AcademicYear.query.filter_by(is_active=True).first()
    fee_types = FeeType.query.order_by(FeeType.name.asc()).all()
    last_backup = get_setting("last_backup","Never")
    fmt_preview = f"{get_setting('receipt_prefix','AY')}{(ay.name if ay else 'Unset').replace('-','')}-R-{int(get_setting('receipt_seq','1')):04d}"
    school = get_setting('school_name','My School')
    mode = get_setting('receipt_number_mode','auto')
    rules = PhonePeFeeRule.query.order_by(PhonePeFeeRule.name.asc()).all()
    return render_template('settings/index.html', ay=ay, fee_types=fee_types,
                           last_backup=last_backup, fmt_preview=fmt_preview,
                           school=school, number_mode=mode, rules=rules)

@settings_bp.route('/year/activate', methods=['POST'])
@login_required
def year_activate():
    name = request.form['name']
    ay = AcademicYear.query.filter_by(name=name).first()
    if not ay:
        ay = AcademicYear(name=name, start_date=date.today(), end_date=date(date.today().year+1, 3, 31))
        db.session.add(ay)
    for a in AcademicYear.query.all():
        a.is_active = (a.id == ay.id)
    db.session.commit()
    flash(f'Active Academic Year: {ay.name}','success')
    return redirect(url_for('settings.index'))

@settings_bp.route('/year/rollover', methods=['POST'])
@login_required
def year_rollover():
    cur = AcademicYear.query.filter_by(is_active=True).first()
    if not cur:
        flash('Set an active year first.','warning'); return redirect(url_for('settings.index'))
    parts = cur.name.split('-')
    nxt = f"{int(parts[0])+1}-{int(parts[1])+1}" if len(parts)==2 and parts[0].isdigit() else "Next"
    from datetime import date as _d
    new = AcademicYear(name=nxt, start_date=_d.today(), end_date=_d(_d.today().year+1, 3, 31), is_active=True)
    cur.is_active=False
    db.session.add(new); db.session.commit()
    flash(f'Rolled over to {new.name}','success')
    return redirect(url_for('settings.index'))

@settings_bp.route('/receipt', methods=['POST'])
@login_required
def receipt_format():
    set_setting("receipt_number_mode", request.form.get('mode','auto'))
    set_setting("receipt_prefix", request.form.get('prefix','AY'))
    set_setting("receipt_seq", request.form.get('seq','1'))
    flash('Receipt numbering saved','success')
    return redirect(url_for('settings.index'))

@settings_bp.route('/school', methods=['POST'])
@login_required
def set_school():
    name = request.form.get('school_name','').strip() or 'My School'
    set_setting("school_name", name)
    flash('School name saved','success')
    return redirect(url_for('settings.index'))

@settings_bp.route('/backup')
@login_required
def backup_now():
    path = backup_sqlite()
    set_setting("last_backup","Today")
    flash(f'Backup created at {path}','success')
    return redirect(url_for('settings.index'))

# UPI Fee Rules
@settings_bp.route('/upi_rules', methods=['POST'])
@login_required
def upi_rules_save():
    name = request.form['name']
    percent = request.form.get('percent','0')
    flat = request.form.get('flat','0')
    active = True if request.form.get('active')=='on' else False
    r = PhonePeFeeRule(name=name, percent=float(percent or 0), flat=float(flat or 0), active=active)
    db.session.add(r); db.session.commit()
    flash('UPI fee rule added','success')
    return redirect(url_for('settings.index'))
