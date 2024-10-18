from flask import Flask, render_template, request, redirect, url_for, flash, session, abort, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from sqlalchemy import func
import os
from dotenv import load_dotenv
import logging
from stravalib.client import Client
from stravalib.exc import AccessUnauthorized
from werkzeug.utils import secure_filename
from shutil import copy2
import uuid
from PIL import Image
from io import BytesIO

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Secret key configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
# Strava configuration
app.config['STRAVA_CLIENT_ID'] = os.getenv('STRAVA_CLIENT_ID')
app.config['STRAVA_CLIENT_SECRET'] = os.getenv('STRAVA_CLIENT_SECRET')
app.config['STRAVA_REDIRECT_URI'] = os.getenv('STRAVA_REDIRECT_URI', 'http://localhost:5000/strava/callback')

app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'profile_pictures')

# Database configuration
try:
    if os.getenv('FLASK_ENV') == 'production':
        database_url = os.getenv('DATABASE_URL')
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DEVELOPMENT_DATABASE_URL')

    if not app.config['SQLALCHEMY_DATABASE_URI']:
        raise ValueError("Database URL is not set")

    logger.info(f"Using database: {app.config['SQLALCHEMY_DATABASE_URI']}")
except Exception as e:
    logger.error(f"Error configuring database: {str(e)}")
    raise

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# local file storage
try:
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
except Exception as e:
    logger.error(f"Error creating upload folder: {str(e)}")
    raise

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    workouts = db.relationship('Workout', backref='user', lazy=True)
    is_admin = db.Column(db.Boolean, default=False)
    profile_picture = db.Column(db.String(255), nullable=False, default='placeholderAvatar.jpg')

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
    sets = db.relationship('Set', backref='workout', lazy=True, cascade='all, delete-orphan')

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

class StravaAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    access_token = db.Column(db.String(255), nullable=False)
    refresh_token = db.Column(db.String(255), nullable=False)
    token_expiry = db.Column(db.DateTime, nullable=False)

    user = db.relationship('User', backref=db.backref('strava_account', uselist=False))

class StravaWorkout(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    strava_id = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    distance = db.Column(db.Float, nullable=False)
    moving_time = db.Column(db.Integer, nullable=False)
    average_speed = db.Column(db.Float, nullable=False)
    total_elevation_gain = db.Column(db.Float, nullable=False)

    user = db.relationship('User', backref=db.backref('strava_workouts', lazy='dynamic'))

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
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password_hash=hashed_password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
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
        
        exercise_count = int(request.form['exercise_count'])
        for i in range(1, exercise_count + 1):
            exercise_id = request.form[f'exercise_{i}']
            sets = int(request.form[f'sets_{i}'])
            reps = int(request.form[f'reps_{i}'])
            weight = float(request.form[f'weight_{i}'])
            
            for _ in range(sets):
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
        flash('Please log in to view your profile.', 'warning')
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    workouts = Workout.query.filter_by(user_id=user.id).order_by(Workout.date.desc()).all()
    strava_workouts = StravaWorkout.query.filter_by(user_id=user.id).order_by(StravaWorkout.start_date.desc()).all()
    strava_connected = StravaAccount.query.filter_by(user_id=user.id).first() is not None
    
    profile_picture_url = url_for('static', filename=f'profile_pictures/{user.profile_picture}') if user.profile_picture else None
    
    return render_template('user_profile.html', user=user, workouts=workouts, 
                           strava_workouts=strava_workouts, strava_connected=strava_connected,
                           profile_picture_url=profile_picture_url)

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
        flash('Please login to delete a workout')
        return redirect(url_for('login'))

    workout = Workout.query.get_or_404(workout_id)

    if workout.user_id != session['user_id']:
        flash('You do not have permission to delete this workout')
        return redirect(url_for('user_profile'))

    try:
        db.session.delete(workout)
        db.session.commit()
        flash('Workout deleted successfully')
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred while deleting the workout: {str(e)}')

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
        abort(403)  # Forbidden
    
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        abort(403)  # Forbidden
    
    if request.method == 'POST':
        if 'new_exercise' in request.form:
            name = request.form.get('exercise_name').strip()
            muscle_group = request.form.get('muscle_group')
            
            if name and muscle_group:
                existing_exercise = Exercise.query.filter(func.lower(Exercise.name) == name.lower()).first()
                if existing_exercise:
                    return jsonify({'status': 'error', 'message': f'Exercise "{name}" already exists!'}), 400
                else:
                    new_exercise = Exercise(name=name, muscle_group=muscle_group)
                    db.session.add(new_exercise)
                    db.session.commit()
                    return jsonify({'status': 'success', 'message': f'New exercise "{name}" added successfully!'}), 200
            else:
                return jsonify({'status': 'error', 'message': 'Exercise name and muscle group are required!'}), 400
        else:
            # Handle weekly workout updates
            WeeklyWorkout.query.delete()  # Clear existing workouts
            
            days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            for day in days:
                workout_name = request.form.get(f'{day}_name')
                if workout_name:
                    workout = WeeklyWorkout(day=day, name=workout_name)
                    db.session.add(workout)
                    
                    exercise_count = int(request.form.get(f'{day}_exercise_count', 0))
                    for i in range(1, exercise_count + 1):
                        exercise_id = request.form.get(f'{day}_exercise_{i}')
                        sets = request.form.get(f'{day}_sets_{i}')
                        reps = request.form.get(f'{day}_reps_{i}')
                        if exercise_id and sets and reps:
                            exercise = WorkoutExercise(
                                exercise_id=exercise_id,
                                sets=sets,
                                reps=reps
                            )
                            workout.exercises.append(exercise)
            
            db.session.commit()
            flash('Weekly workout routine updated successfully', 'success')
        
        return redirect(url_for('admin_weekly_workout'))

    # GET request handling
    weekly_workouts = WeeklyWorkout.query.all()
    exercises = Exercise.query.order_by(Exercise.muscle_group, Exercise.name).all()
    muscle_groups = db.session.query(func.distinct(Exercise.muscle_group)).order_by(Exercise.muscle_group).all()
    muscle_groups = [group[0] for group in muscle_groups]  # Flatten the result

    return render_template('admin_weekly_workout.html', 
                           weekly_workouts=weekly_workouts, 
                           exercises=exercises, 
                           muscle_groups=muscle_groups)

@app.route('/exercises', methods=['GET'])
def get_exercises():
    exercises = Exercise.query.order_by(Exercise.muscle_group, Exercise.name).all()
    return jsonify([{'id': e.id, 'name': e.name, 'muscle_group': e.muscle_group} for e in exercises])

@app.context_processor
def utility_processor():
    def get_current_user():
        if 'user_id' in session:
            return User.query.get(session['user_id'])
        return None
    return dict(get_current_user=get_current_user)

@app.route('/strava/auth')
def strava_auth():
    if 'user_id' not in session:
        flash('Please login to connect with Strava', 'warning')
        return redirect(url_for('login'))
    
    client = Client()
    authorize_url = client.authorization_url(
        client_id=app.config['STRAVA_CLIENT_ID'],
        redirect_uri=app.config['STRAVA_REDIRECT_URI'],
        scope=['read_all', 'activity:read_all']
    )
    return redirect(authorize_url)

@app.route('/strava/callback')
def strava_callback():
    if 'user_id' not in session:
        flash('Please login to connect with Strava', 'warning')
        return redirect(url_for('login'))
    
    code = request.args.get('code')
    client = Client()
    token_response = client.exchange_code_for_token(
        client_id=app.config['STRAVA_CLIENT_ID'],
        client_secret=app.config['STRAVA_CLIENT_SECRET'],
        code=code
    )
    
    access_token = token_response['access_token']
    refresh_token = token_response['refresh_token']
    expires_at = datetime.fromtimestamp(token_response['expires_at'])
    
    strava_account = StravaAccount.query.filter_by(user_id=session['user_id']).first()
    if strava_account:
        strava_account.access_token = access_token
        strava_account.refresh_token = refresh_token
        strava_account.token_expiry = expires_at
    else:
        strava_account = StravaAccount(
            user_id=session['user_id'],
            access_token=access_token,
            refresh_token=refresh_token,
            token_expiry=expires_at
        )
        db.session.add(strava_account)
    
    db.session.commit()
    flash('Successfully connected to Strava!', 'success')
    return redirect(url_for('import_strava_workouts'))

@app.route('/strava/import')
def import_strava_workouts():
    if 'user_id' not in session:
        flash('Please login to import Strava workouts', 'warning')
        return redirect(url_for('login'))
    
    strava_account = StravaAccount.query.filter_by(user_id=session['user_id']).first()
    if not strava_account:
        flash('Please connect your Strava account first', 'warning')
        return redirect(url_for('strava_auth'))
    
    client = Client(access_token=strava_account.access_token)
    
    try:
        activities = client.get_activities(after=datetime.utcnow() - timedelta(days=30))
        for activity in activities:
            existing_workout = StravaWorkout.query.filter_by(strava_id=str(activity.id)).first()
            if not existing_workout:
                new_workout = StravaWorkout(
                    user_id=session['user_id'],
                    strava_id=str(activity.id),
                    name=activity.name,
                    type=str(activity.type),
                    start_date=activity.start_date,
                    distance=float(activity.distance),
                    moving_time=int(activity.moving_time),
                    average_speed=float(activity.average_speed),
                    total_elevation_gain=float(activity.total_elevation_gain)
                )
                db.session.add(new_workout)
        
        db.session.commit()
        flash('Successfully imported Strava workouts!', 'success')
    except AccessUnauthorized:
        flash('Strava access token expired. Please reconnect your account.', 'warning')
        return redirect(url_for('strava_auth'))
    
    return redirect(url_for('user_profile'))

@app.route('/strava/disconnect', methods=['POST'])
def strava_disconnect():
    if 'user_id' not in session:
        flash('Please log in to disconnect your Strava account.', 'warning')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    # Get Strava account
    strava_account = StravaAccount.query.filter_by(user_id=user_id).first()
    
    if strava_account:
        # Revoke Strava access token
        client = Client()
        try:
            client.deauthorize(access_token=strava_account.access_token)
        except Exception as e:
            # Log the error, but continue with local cleanup
            print(f"Error revoking Strava token: {str(e)}")
        
        # Remove Strava account from our database
        db.session.delete(strava_account)
    
    # Remove all Strava workouts
    StravaWorkout.query.filter_by(user_id=user_id).delete()
    
    db.session.commit()
    
    flash('Your Strava account has been disconnected and all imported workouts have been removed.', 'success')
    return redirect(url_for('user_profile'))

@app.route('/strava/remove_workout/<int:workout_id>', methods=['POST'])
def remove_strava_workout(workout_id):
    if 'user_id' not in session:
        flash('Please log in to remove Strava workouts.', 'warning')
        return redirect(url_for('login'))
    
    workout = StravaWorkout.query.get_or_404(workout_id)
    if workout.user_id != session['user_id']:
        flash('You do not have permission to remove this workout.', 'danger')
        return redirect(url_for('user_profile'))
    
    db.session.delete(workout)
    db.session.commit()
    
    flash('Strava workout has been removed.', 'success')
    return redirect(url_for('user_profile'))

def resize_and_crop(image, size):
    """Resize and crop an image to fit the specified size."""
    # If the image is larger than the specified size, resize it
    if image.size[0] > size[0] or image.size[1] > size[1]:
        image.thumbnail((size[0], size[1]), Image.LANCZOS)
    
    # Check which dimension is larger
    if image.size[0] > image.size[1]:
        # Width is larger. Calculate the trimming amount
        left = (image.size[0] - size[0]) / 2
        top = 0
        right = (image.size[0] + size[0]) / 2
        bottom = size[1]
    else:
        # Height is larger. Calculate the trimming amount
        left = 0
        top = (image.size[1] - size[1]) / 2
        right = size[0]
        bottom = (image.size[1] + size[1]) / 2
    
    # Crop and return the image
    return image.crop((left, top, right, bottom))

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload_profile_picture', methods=['POST'])
def upload_profile_picture():
    if 'profile-picture' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['profile-picture']
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        # Update user's profile picture in database
        user = User.query.get(session['user_id'])
        user.profile_picture = filename
        db.session.commit()
        flash('Your profile picture has been updated successfully!', 'success')
        return jsonify({'success': 'Profile picture updated successfully'}), 200
    else:
        return jsonify({'error': 'Invalid file type'}), 400

@app.route('/delete_profile_picture', methods=['POST'])
def delete_profile_picture():
    if 'user_id' not in session:
        flash('Please log in to manage your profile picture', 'warning')
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user:
        flash('User not found', 'danger')
        return redirect(url_for('user_profile'))
    
    if user.profile_picture != 'placeholderAvatar.jpg':
        # Delete the current profile picture file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], user.profile_picture)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Reset the user's profile picture to the default
        user.profile_picture = 'placeholderAvatar.jpg'
        db.session.commit()
        
        flash('Profile picture has been reset to default', 'success')
    else:
        flash('You are already using the default profile picture', 'info')
    
    return redirect(url_for('user_profile'))

@app.route('/roster', methods=['GET'])
def roster():
    users = User.query.all()
    return render_template('roster.html', users=users)

with app.app_context():
    db.create_all()
    populate_exercises()

if __name__ == '__main__':
    try:
        app.run(debug=True)
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")