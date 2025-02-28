from app import app, db
from app import User, Task, Expense  # Ensure Expense model is imported

def init_db():
    with app.app_context():
        db.drop_all()  # Drop existing tables
        db.create_all()  # Create new tables
        # Add a default user for testing
        if not User.query.filter_by(username='admin').first():
            default_user = User(username='admin', password='admin123')
            db.session.add(default_user)
            db.session.commit()

if __name__ == "__main__":
    init_db()
