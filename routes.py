from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models import Question, Response, Presentation, User, Setup
from google_drive import GoogleDriveService
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

routes = Blueprint('routes', __name__)

[Previous content...]

@routes.route('/admin/questions')
@login_required
def admin_questions():
    # Get all questions ordered by strategic goal and order
    questions = Question.query.order_by(Question.strategic_goal, Question.order).all()
    return render_template('admin/questions.html', questions=questions)

@routes.route('/admin/questions/add', methods=['GET', 'POST'])
@login_required
def admin_add_question():
    if request.method == 'POST':
        try:
            options = [opt.strip() for opt in request.form['options'].split(',')]
            question = Question(
                strategic_goal=request.form['strategic_goal'],
                major_cnapp_area=request.form['major_cnapp_area'],
                text=request.form['text'],
                options=options,
                weighting_score=request.form['weighting_score'],
                order=int(request.form['order'])
            )
            db.session.add(question)
            db.session.commit()
            flash('Question added successfully!', 'success')
            return redirect(url_for('routes.admin_questions'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding question: {str(e)}', 'error')
            
    return render_template('admin/question_form.html')

@routes.route('/admin/questions/edit/<int:question_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_question(question_id):
    question = Question.query.get_or_404(question_id)
    if request.method == 'POST':
        try:
            question.strategic_goal = request.form['strategic_goal']
            question.major_cnapp_area = request.form['major_cnapp_area']
            question.text = request.form['text']
            question.options = [opt.strip() for opt in request.form['options'].split(',')]
            question.weighting_score = request.form['weighting_score']
            question.order = int(request.form['order'])
            db.session.commit()
            flash('Question updated successfully!', 'success')
            return redirect(url_for('routes.admin_questions'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating question: {str(e)}', 'error')
            
    return render_template('admin/question_form.html', question=question)

@routes.route('/admin/questions/delete/<int:question_id>', methods=['POST'])
@login_required
def admin_delete_question(question_id):
    question = Question.query.get_or_404(question_id)
    try:
        db.session.delete(question)
        db.session.commit()
        flash('Question deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting question: {str(e)}', 'error')
    return redirect(url_for('routes.admin_questions'))
