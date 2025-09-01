from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user
from .extensions import db
from .models import User, AuditLog
from .security import role_required, audit
from .utils import backup_sqlite

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/users', methods=['GET','POST'])
@role_required(['Owner'])
def users():
    if request.method == 'POST':
        username = request.form['username']; role = request.form['role']; pwd = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Username exists','warning'); return redirect(url_for('admin.users'))
        u = User(username=username, role=role, full_name=username.title()); u.set_password(pwd)
        db.session.add(u); db.session.commit(); audit(current_user.username,'CREATE','user',u.id,{}, {'role':role})
        flash('User created','success'); return redirect(url_for('admin.users'))
    rows = User.query.order_by(User.username.asc()).all()
    return render_template('admin/users.html', rows=rows)

@admin_bp.route('/audit')
@role_required(['Owner','Manager'])
def audit_log():
    rows = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()
    return render_template('admin/audit_log.html', rows=rows)

@admin_bp.route('/backup')
@role_required(['Owner'])
def backup():
    path = backup_sqlite(); flash(f'Backup created at {path}','success'); return redirect(url_for('admin.audit_log'))
