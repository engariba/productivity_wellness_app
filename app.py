from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_jwt_extended import JWTManager
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timezone
import atexit
import sqlite3

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['JWT_SECRET_KEY'] = 'your_jwt_secret_key'

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
jwt = JWTManager(app)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='pending')  # New field for status
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))  # Updated
    completed_at = db.Column(db.DateTime, default=None)  # Updated

class Expense(db.Model):  # Added Expense model
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(100), nullable=False)
    duration = db.Column(db.Integer, nullable=False)  # Duration in minutes
    date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
@login_required
def home():
    return redirect(url_for('dashboard'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.password == password:
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', tasks=tasks)

@app.route('/add_task', methods=['POST'])
@login_required
def add_task():
    task_description = request.form['task']
    new_task = Task(description=task_description, user_id=current_user.id)
    db.session.add(new_task)
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/delete_task/<int:task_id>')
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id == current_user.id:
        db.session.delete(task)
        db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/log_water', methods=['POST'])
def log_water():
    amount = request.form['amount']
    date_time = datetime.now(timezone.utc)  # Use timezone-aware datetime
    conn = sqlite3.connect('fitness.db')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS water_intake (id INTEGER PRIMARY KEY AUTOINCREMENT, amount REAL, date_time TEXT)')
    cursor.execute('INSERT INTO water_intake (amount, date_time) VALUES (?, ?)', (amount, date_time))
    conn.commit()
    conn.close()
    return redirect(url_for('water_intake'))

@app.route('/water_intake')
def water_intake():
    conn = sqlite3.connect('fitness.db')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS water_intake (id INTEGER PRIMARY KEY AUTOINCREMENT, amount REAL, date_time TEXT)')
    cursor.execute('SELECT * FROM water_intake')
    data = cursor.fetchall()
    conn.close()
    return render_template('water_intake.html', data=data)

def stretch_reminder():
    print('Time to stretch!')

scheduler = BackgroundScheduler()
scheduler.add_job(stretch_reminder, 'interval', minutes=30)  # Changed to 30 minutes for testing
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

@app.route('/log_expense', methods=['POST'])
def log_expense():
    description = request.form.get('description')
    amount = request.form.get('amount')
    new_expense = Expense(description=description, amount=amount)
    db.session.add(new_expense)
    db.session.commit()
    return jsonify({'message': 'Expense logged successfully'})

@app.route('/log_expense_form')
@login_required
def log_expense_form():
    return render_template('log_expense_form.html')

@app.route('/productivity_report')
@login_required
def productivity_report():
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    
    # Process task data for visualization
    completed_tasks = [task for task in tasks if task.status == 'completed']
    pending_tasks = [task for task in tasks if task.status == 'pending']

    completed_count = len(completed_tasks)
    pending_count = len(pending_tasks)

    task_counts = {
        'completed': completed_count,
        'pending': pending_count
    }

    # Generate chart data using Plotly
    chart_data = generate_charts(task_counts)

    return render_template('productivity_report.html', chart_data=chart_data)

def generate_charts(task_counts):
    import plotly.graph_objs as go
    import plotly.io as pio

    fig = go.Figure(data=[
        go.Bar(name='Tasks', x=list(task_counts.keys()), y=list(task_counts.values()))
    ])

    fig.update_layout(title='Productivity Report', xaxis_title='Task Status', yaxis_title='Number of Tasks')

    chart_html = pio.to_html(fig, full_html=False)

    return chart_html

@app.route('/complete_task/<int:task_id>')
@login_required
def complete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id == current_user.id:
        task.status = 'completed'
        task.completed_at = datetime.now(timezone.utc)  # Updated
        db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/log_activity', methods=['GET', 'POST'])
@login_required
def log_activity():
    if request.method == 'POST':
        activity_type = request.form['type']
        duration = request.form['duration']
        new_activity = Activity(type=activity_type, duration=duration, user_id=current_user.id)
        db.session.add(new_activity)
        db.session.commit()
        return redirect(url_for('view_activities'))
    return render_template('log_activity.html')

@app.route('/view_activities')
@login_required
def view_activities():
    activities = Activity.query.filter_by(user_id=current_user.id).all()
    return render_template('view_activities.html', activities=activities)


if __name__ == '__main__':
    app.run(debug=True)
