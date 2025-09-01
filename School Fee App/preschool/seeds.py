from .extensions import db
from .models import User

def seed_owner():
    if not User.query.filter_by(username="owner").first():
        u = User(username="owner", full_name="Owner", role="Owner")
        u.set_password("owner123")
        db.session.add(u); db.session.commit()
