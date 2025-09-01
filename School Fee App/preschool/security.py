from flask import redirect, url_for, request
from flask_login import current_user
from functools import wraps

def role_required(roles):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login", next=request.path))
            if current_user.role not in roles:
                return redirect(url_for("index"))
            return fn(*args, **kwargs)
        return wrapped
    return decorator

def audit(**kwargs):
    # stub (place to write AuditLog later)
    return True
