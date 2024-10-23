from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
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
    week_start_date = db.Column(db.Date, nullable=False)
    monday_template_id = db.Column(db.Integer, db.ForeignKey('workout_template.id'))
    tuesday_template_id = db.Column(db.Integer, db.ForeignKey('workout_template.id'))
    wednesday_template_id = db.Column(db.Integer, db.ForeignKey('workout_template.id'))
    thursday_template_id = db.Column(db.Integer, db.ForeignKey('workout_template.id'))
    friday_template_id = db.Column(db.Integer, db.ForeignKey('workout_template.id'))
    saturday_template_id = db.Column(db.Integer, db.ForeignKey('workout_template.id'))
    sunday_template_id = db.Column(db.Integer, db.ForeignKey('workout_template.id'))

    monday_template = db.relationship('WorkoutTemplate', foreign_keys=[monday_template_id])
    tuesday_template = db.relationship('WorkoutTemplate', foreign_keys=[tuesday_template_id])
    wednesday_template = db.relationship('WorkoutTemplate', foreign_keys=[wednesday_template_id])
    thursday_template = db.relationship('WorkoutTemplate', foreign_keys=[thursday_template_id])
    friday_template = db.relationship('WorkoutTemplate', foreign_keys=[friday_template_id])
    saturday_template = db.relationship('WorkoutTemplate', foreign_keys=[saturday_template_id])
    sunday_template = db.relationship('WorkoutTemplate', foreign_keys=[sunday_template_id])

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

class WorkoutTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    exercises = db.relationship('WorkoutTemplateExercise', backref='template', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'created_by_name': db.session.get(User, self.created_by).username,
            'created_by_id': self.created_by,
            'exercises': [{
                'name': db.session.get(Exercise, exercise.exercise_id).name,
                'sets': exercise.sets,
                'reps': exercise.reps
            } for exercise in self.exercises]
        }

class WorkoutTemplateExercise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey('workout_template.id'), nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey('exercise.id'), nullable=False)
    sets = db.Column(db.Integer, nullable=False)
    reps = db.Column(db.Integer, nullable=False)

    exercise = db.relationship('Exercise')
