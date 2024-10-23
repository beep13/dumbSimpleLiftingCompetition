from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from models import db, WeeklyWorkout, WorkoutTemplate, Exercise, User
from sqlalchemy import func
from datetime import datetime, timedelta
from extensions import db

admin = Blueprint('admin', __name__)

@admin.route('/create_weekly_workout', methods=['GET', 'POST'])
def create_weekly_workout():
    if 'user_id' not in session:
        abort(403)  # Forbidden
    
    user = db.session.get(User, session['user_id'])
    if not user or not user.is_admin:
        abort(403)  # Forbidden

    if request.method == 'POST':
        week_start_date = datetime.strptime(request.form['week_start_date'], '%Y-%m-%d').date()
        # Normalize to Sunday
        week_start_date -= timedelta(days=week_start_date.weekday() + 1)
        weekly_workout = WeeklyWorkout(week_start_date=week_start_date)

        days = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
        for day in days:
            template_id = request.form.get(f'{day}_template')
            if template_id == 'rest':
                setattr(weekly_workout, f'{day}_template_id', None)
            elif template_id:
                setattr(weekly_workout, f'{day}_template_id', template_id)

        db.session.add(weekly_workout)
        db.session.commit()
        flash('Weekly workout created successfully!', 'success')
        return redirect(url_for('admin.view_weekly_workouts'))

    templates = WorkoutTemplate.query.all()
    return render_template('admin/create_weekly_workout.html', templates=templates)

@admin.route('/view_weekly_workouts')
def view_weekly_workouts():
    if 'user_id' not in session:
        abort(403)  # Forbidden
    
    user = db.session.get(User, session['user_id'])
    if not user or not user.is_admin:
        abort(403)  # Forbidden

    weekly_workouts = WeeklyWorkout.query.order_by(WeeklyWorkout.week_start_date.desc()).all()
    return render_template('admin/view_weekly_workouts.html', weekly_workouts=weekly_workouts)

@admin.route('/view_template/<int:template_id>')
def view_template(template_id):
    if 'user_id' not in session:
        abort(403)  # Forbidden
    
    user = db.session.get(User, session['user_id'])
    if not user or not user.is_admin:
        abort(403)  # Forbidden

    template = WorkoutTemplate.query.get_or_404(template_id)
    return_to = request.args.get('return_to', 'admin.view_weekly_workouts')
    workout_id = request.args.get('workout_id')
    return render_template('admin/view_template.html', template=template, return_to=return_to, workout_id=workout_id)

@admin.route('/edit_weekly_workout/<int:workout_id>', methods=['GET', 'POST'])
def edit_weekly_workout(workout_id):
    if 'user_id' not in session:
        abort(403)  # Forbidden
    
    user = db.session.get(User, session['user_id'])
    if not user or not user.is_admin:
        abort(403)  # Forbidden

    workout = db.session.get(WeeklyWorkout, workout_id)
    if not workout:
        abort(404)  # Not Found

    templates = WorkoutTemplate.query.all()

    if request.method == 'POST':
        workout.week_start_date = datetime.strptime(request.form['week_start_date'], '%Y-%m-%d').date()
        days = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
        for day in days:
            template_id = request.form.get(f'{day}_template')
            if template_id == 'rest':
                setattr(workout, f'{day}_template_id', None)
            elif template_id:
                setattr(workout, f'{day}_template_id', int(template_id))
            else:
                setattr(workout, f'{day}_template_id', None)

        db.session.commit()
        flash('Weekly workout updated successfully!', 'success')
        return redirect(url_for('admin.view_weekly_workouts'))

    return render_template('admin/edit_weekly_workout.html', workout=workout, templates=templates)

@admin.route('/view_weekly_workout/<int:workout_id>')
def view_weekly_workout(workout_id):
    if 'user_id' not in session:
        abort(403)  # Forbidden
    
    user = db.session.get(User, session['user_id'])
    if not user or not user.is_admin:
        abort(403)  # Forbidden

    workout = db.session.get(WeeklyWorkout, workout_id)
    if not workout:
        abort(404)  # Not Found

    return render_template('admin/view_weekly_workout.html', workout=workout)
