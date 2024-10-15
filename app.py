from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from sqlalchemy import func
import os

app = Flask(__name__)

# Secret key configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')

# Database configuration
uri = os.environ.get("DATABASE_URL") 
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = uri or 'sqlite:///workouts.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    workouts = db.relationship('Workout', backref='user', lazy=True)
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Exercise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    muscle_group = db.Column(db.String(50), nullable=False)

class Workout(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    sets = db.relationship('Set', backref='workout', lazy=True)

class Set(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workout_id = db.Column(db.Integer, db.ForeignKey('workout.id'), nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey('exercise.id'), nullable=False)
    weight = db.Column(db.Float, nullable=False)
    reps = db.Column(db.Integer, nullable=False)
    exercise = db.relationship('Exercise')

class WeeklyWorkout(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.String(10), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    exercises = db.relationship('WorkoutExercise', backref='weekly_workout', lazy=True, cascade="all, delete-orphan")

class WorkoutExercise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    weekly_workout_id = db.Column(db.Integer, db.ForeignKey('weekly_workout.id'), nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey('exercise.id'), nullable=False)
    sets = db.Column(db.Integer, nullable=False)
    reps = db.Column(db.Integer, nullable=False)

    exercise = db.relationship('Exercise')

@app.route('/')
def index():
    user = None
    suggested_workout = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        today = datetime.now().strftime('%A')
        suggested_workout = WeeklyWorkout.query.filter_by(day=today).first()
    return render_template('index.html', user=user, suggested_workout=suggested_workout)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Username already exists')
            return redirect(url_for('register'))
        
        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            flash('Login successful')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out')
    return redirect(url_for('index'))

@app.route('/add_workout', methods=['GET', 'POST'])
def add_workout():
    if 'user_id' not in session:
        flash('Please login to add a workout')
        return redirect(url_for('login'))
    
    exercises = Exercise.query.all()
    
    if request.method == 'POST':
        date_str = request.form['date']
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        user_id = session.get('user_id')
        if user_id is None:
            flash('User not found. Please log in again.')
            return redirect(url_for('login'))
        
        user = User.query.get(user_id)
        if user is None:
            flash('User not found. Please log in again.')
            return redirect(url_for('login'))
        
        workout = Workout(user_id=user.id, date=date)
        db.session.add(workout)
        
        for i in range(1, int(request.form['set_count']) + 1):
            exercise_id = request.form[f'exercise_{i}']
            weight = float(request.form[f'weight_{i}'])
            reps = int(request.form[f'reps_{i}'])
            
            set = Set(workout=workout, exercise_id=exercise_id, weight=weight, reps=reps)
            db.session.add(set)
        
        try:
            db.session.commit()
            flash('Workout added successfully')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {str(e)}')
            return redirect(url_for('add_workout'))
    
    return render_template('add_workout.html', exercises=exercises)

@app.route('/leaderboard')
def leaderboard():
    muscle_group = request.args.get('muscle_group', '')
    time_period = request.args.get('time_period', 'all')
    
    base_query = db.session.query(
        User.username, 
        func.sum(Set.weight * Set.reps).label('total_volume')
    ).select_from(User).join(User.workouts).join(Workout.sets).join(Set.exercise)
    
    if muscle_group:
        base_query = base_query.filter(Exercise.muscle_group == muscle_group)
    
    # Apply time period filter
    today = datetime.now().date()
    if time_period == 'week':
        start_date = today - timedelta(days=today.weekday())
        base_query = base_query.filter(Workout.date >= start_date)
    elif time_period == 'month':
        start_date = today.replace(day=1)
        base_query = base_query.filter(Workout.date >= start_date)
    elif time_period == 'year':
        start_date = today.replace(month=1, day=1)
        base_query = base_query.filter(Workout.date >= start_date)
    
    leaderboard = base_query.group_by(User.id).order_by(func.sum(Set.weight * Set.reps).desc()).all()
    
    muscle_groups = db.session.query(Exercise.muscle_group).distinct().all()
    muscle_groups = [group[0] for group in muscle_groups]
    
    return render_template('leaderboard.html', 
                           leaderboard=leaderboard, 
                           muscle_groups=muscle_groups, 
                           selected_group=muscle_group,
                           selected_period=time_period)

@app.route('/user_profile')
def user_profile():
    if 'user_id' not in session:
        flash('Please login to view your profile')
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if user is None:
        flash('User not found')
        return redirect(url_for('index'))
    
    workouts = Workout.query.filter_by(user_id=user.id).order_by(Workout.date.desc()).all()
    return render_template('user_profile.html', user=user, workouts=workouts)

@app.route('/edit_workout/<int:workout_id>', methods=['GET', 'POST'])
def edit_workout(workout_id):
    if 'user_id' not in session:
        flash('Please login to edit workouts')
        return redirect(url_for('login'))
    
    workout = Workout.query.get_or_404(workout_id)
    if workout.user_id != session['user_id']:
        abort(403)
    
    exercises = Exercise.query.all()
    
    if request.method == 'POST':
        workout.date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
        
        # Remove existing sets
        for set in workout.sets:
            db.session.delete(set)
        
        # Add new sets
        for i in range(1, int(request.form['set_count']) + 1):
            exercise_id = request.form[f'exercise_{i}']
            weight = float(request.form[f'weight_{i}'])
            reps = int(request.form[f'reps_{i}'])
            
            set = Set(workout=workout, exercise_id=exercise_id, weight=weight, reps=reps)
            db.session.add(set)
        
        try:
            db.session.commit()
            flash('Workout updated successfully')
            return redirect(url_for('user_profile'))
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {str(e)}')
    
    return render_template('edit_workout.html', workout=workout, exercises=exercises)

@app.route('/delete_workout/<int:workout_id>', methods=['POST'])
def delete_workout(workout_id):
    if 'user_id' not in session:
        flash('Please login to delete workouts')
        return redirect(url_for('login'))
    
    workout = Workout.query.get_or_404(workout_id)
    if workout.user_id != session['user_id']:
        abort(403)
    
    try:
        db.session.delete(workout)
        db.session.commit()
        flash('Workout deleted successfully')
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred: {str(e)}')
    
    return redirect(url_for('user_profile'))

def populate_exercises():
    exercises = [
        ('Bench Press', 'Chest'),
        ('Squat', 'Legs'),
        ('Deadlift', 'Back'),
        ('Overhead Press', 'Shoulders'),
        ('Bicep Curl', 'Arms'),
        ('Tricep Extension', 'Arms'),
        ('Lat Pulldown', 'Back'),
        ('Leg Press', 'Legs'),
        ('Dumbbell Fly', 'Chest'),
        ('Calf Raise', 'Legs')
    ]
    
    for name, muscle_group in exercises:
        exercise = Exercise.query.filter_by(name=name).first()
        if not exercise:
            new_exercise = Exercise(name=name, muscle_group=muscle_group)
            db.session.add(new_exercise)
    
    db.session.commit()

@app.route('/admin/weekly_workout', methods=['GET', 'POST'])
def admin_weekly_workout():
    if 'user_id' not in session:
        flash('Please login to access this page')
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        abort(403)
    
    if request.method == 'POST':
        WeeklyWorkout.query.delete()
        
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        for day in days:
            name = request.form.get(f'{day}_name')
            if name:
                workout = WeeklyWorkout(day=day, name=name)
                db.session.add(workout)
                
                exercise_count = int(request.form.get(f'{day}_exercise_count', 0))
                for i in range(1, exercise_count + 1):
                    exercise_id = request.form.get(f'{day}_exercise_{i}')
                    sets = request.form.get(f'{day}_sets_{i}')
                    reps = request.form.get(f'{day}_reps_{i}')
                    if exercise_id and sets and reps:
                        exercise = WorkoutExercise(exercise_id=exercise_id, sets=sets, reps=reps)
                        workout.exercises.append(exercise)
        
        db.session.commit()
        flash('Weekly workout routine updated successfully')
        return redirect(url_for('admin_weekly_workout'))
    
    weekly_workouts = WeeklyWorkout.query.all()
    exercises = Exercise.query.all()
    return render_template('admin_weekly_workout.html', weekly_workouts=weekly_workouts, exercises=exercises)

with app.app_context():
    db.create_all()
    populate_exercises()

if __name__ == '__main__':
    app.run(debug=True)
