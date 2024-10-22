from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from extensions import db
from models import WorkoutTemplate, WorkoutTemplateExercise, Exercise, User

workout_templates = Blueprint('workout_templates', __name__)

@workout_templates.route('/templates')
def list_templates():
    user_id = session.get('user_id')
    if not user_id:
        flash('Please log in to view your templates', 'warning')
        return redirect(url_for('login'))
    
    templates = WorkoutTemplate.query.all()
    templates_dict = [template.to_dict() for template in templates]
    return render_template('workout_templates/list.html', templates=templates_dict)

@workout_templates.route('/templates/new', methods=['GET', 'POST'])
def new_template():
    user_id = session.get('user_id')
    if not user_id:
        flash('Please log in to create a template', 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        template = WorkoutTemplate(name=name, created_by=user_id)
        db.session.add(template)
        
        exercise_count = int(request.form['exercise_count'])
        for i in range(1, exercise_count + 1):
            exercise_id = request.form[f'exercise_{i}']
            sets = int(request.form[f'sets_{i}'])
            reps = int(request.form[f'reps_{i}'])
            
            template_exercise = WorkoutTemplateExercise(
                template=template,
                exercise_id=exercise_id,
                sets=sets,
                reps=reps
            )
            db.session.add(template_exercise)
        
        db.session.commit()
        flash('Workout template created successfully', 'success')
        return redirect(url_for('workout_templates.list_templates'))
    
    exercises = Exercise.query.all()
    return render_template('workout_templates/new.html', exercises=exercises)

@workout_templates.route('/templates/<int:template_id>/edit', methods=['GET', 'POST'])
def edit_template(template_id):
    user_id = session.get('user_id')
    if not user_id:
        flash('Please log in to edit a template', 'warning')
        return redirect(url_for('login'))

    template = WorkoutTemplate.query.get_or_404(template_id)
    if template.created_by != user_id:
        flash('You do not have permission to edit this template', 'danger')
        return redirect(request.referrer or url_for('workout_templates.list_templates'))

    if request.method == 'POST':
        template.name = request.form['name']
        
        # Remove existing exercises
        for exercise in template.exercises:
            db.session.delete(exercise)
        
        # Add new exercises
        exercise_count = int(request.form['exercise_count'])
        for i in range(1, exercise_count + 1):
            exercise_id = request.form[f'exercise_{i}']
            sets = int(request.form[f'sets_{i}'])
            reps = int(request.form[f'reps_{i}'])
            
            template_exercise = WorkoutTemplateExercise(
                template=template,
                exercise_id=exercise_id,
                sets=sets,
                reps=reps
            )
            db.session.add(template_exercise)
        
        db.session.commit()
        flash('Workout template updated successfully', 'success')
        return redirect(url_for('workout_templates.list_templates'))
    
    exercises = Exercise.query.all()
    return render_template('workout_templates/edit.html', template=template, exercises=exercises)

@workout_templates.route('/templates/<int:template_id>/delete', methods=['POST'])
def delete_template(template_id):
    user_id = session.get('user_id')
    if not user_id:
        flash('Please log in to delete a template', 'warning')
        return redirect(url_for('login'))

    template = WorkoutTemplate.query.get_or_404(template_id)
    if template.created_by != user_id:
        flash('You do not have permission to delete this template', 'danger')
        return redirect(request.referrer or url_for('workout_templates.list_templates'))
    
    db.session.delete(template)
    db.session.commit()
    flash('Workout template deleted successfully', 'success')
    return redirect(url_for('workout_templates.list_templates'))

@workout_templates.route('/load_template/<int:template_id>', methods=['GET'])
def load_template(template_id):
    template = WorkoutTemplate.query.get_or_404(template_id)
    return jsonify(template.to_dict())

@workout_templates.route('/view/<int:template_id>')
def view_template(template_id):
    template = WorkoutTemplate.query.get_or_404(template_id)
    template_dict = template.to_dict()
    return render_template('workout_templates/view.html', template=template_dict)