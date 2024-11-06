import logging
from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from extensions import db
from models import Question, Response, User, Setup, Initiative
from functools import wraps
import json
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

routes = Blueprint('routes', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please login first.', 'error')
            return redirect(url_for('google_auth.login'))
            
        admin_emails = [
            'mpsmalls11@gmail.com',
            'Jaldevi72@gmail.com',
            'm_mcgrail@outlook.com'
        ]
        
        if not (current_user.email.endswith('@sentinelone.com') or current_user.email in admin_emails):
            flash('Admin access required.', 'error')
            return redirect(url_for('routes.index'))
        return f(*args, **kwargs)
    return decorated_function

def get_latest_setup(user_id=None, leader_email=None):
    try:
        if leader_email:
            return Setup.query.filter_by(leader_email=leader_email).order_by(Setup.created_at.desc()).first()
        return Setup.query.filter_by(user_id=user_id).order_by(Setup.created_at.desc()).first()
    except Exception as e:
        logger.error(f"Error getting latest setup: {e}")
        return None

def check_setup_required():
    if current_user.is_authenticated:
        setup = get_latest_setup(current_user.id)
        if not setup:
            flash('Please complete the setup first.', 'info')
            return redirect(url_for('routes.setup'))
    return None

@routes.route('/')
def index():
    if current_user.is_authenticated:
        try:
            setup = get_latest_setup(current_user.id)
            if setup:
                initiatives_response = Response.query.filter_by(
                    setup_id=setup.id,
                    question_id=1
                ).order_by(Response.timestamp.desc()).first()
                
                if initiatives_response:
                    return redirect(url_for('routes.questionnaire', initiative_index=0))
                return redirect(url_for('routes.initiatives'))
            return redirect(url_for('routes.setup'))
        except Exception as e:
            logger.error(f"Error in index route: {str(e)}")
            flash('An error occurred. Please try again.', 'error')
    return render_template('index.html')

@routes.route('/setup', methods=['GET', 'POST'])
@login_required
def setup():
    try:
        if request.method == 'POST':
            required_fields = ['advisor_name', 'advisor_email', 'leader_name', 
                             'leader_email', 'leader_employer']
            
            if not all(field in request.form and request.form[field].strip() for field in required_fields):
                flash('All fields are required and cannot be empty.', 'error')
                return render_template('setup.html')

            setup_info = Setup(
                user_id=current_user.id,
                advisor_name=request.form['advisor_name'].strip(),
                advisor_email=request.form['advisor_email'].strip(),
                leader_name=request.form['leader_name'].strip(),
                leader_email=request.form['leader_email'].strip(),
                leader_employer=request.form['leader_employer'].strip(),
                created_at=datetime.utcnow()
            )
            db.session.add(setup_info)
            db.session.commit()
            
            flash('Setup completed successfully!', 'success')
            return redirect(url_for('routes.initiatives'))

        existing_setup = get_latest_setup(current_user.id)
        return render_template('setup.html', setup=existing_setup)
            
    except Exception as e:
        logger.error(f"Error in setup: {str(e)}")
        db.session.rollback()
        flash('Failed to save setup information. Please try again.', 'error')
        return render_template('setup.html')

@routes.route('/initiatives', methods=['GET', 'POST'])
@login_required
def initiatives():
    setup_redirect = check_setup_required()
    if setup_redirect:
        return setup_redirect
    
    try:
        setup = get_latest_setup(current_user.id)
        if not setup:
            flash('Setup information not found.', 'error')
            return redirect(url_for('routes.setup'))
        
        initiatives = Initiative.query.order_by(Initiative.order).all()
        if not initiatives:
            flash('No initiatives available. Please contact an administrator.', 'error')
            return redirect(url_for('routes.index'))
            
        response = Response.query.filter_by(
            setup_id=setup.id,
            question_id=1
        ).order_by(Response.timestamp.desc()).first()
        
        selected = []
        if response and response.answer:
            try:
                selected = json.loads(response.answer)
                if not isinstance(selected, list):
                    selected = []
            except (json.JSONDecodeError, TypeError):
                selected = []
                
        if request.method == 'POST':
            selected = request.form.getlist('selected_initiatives')
            
            if not 1 <= len(selected) <= 3:
                flash('Please select between 1 and 3 initiatives.', 'error')
                return render_template('business_initiatives.html', 
                                   initiatives=initiatives,
                                   selected=selected)
            
            try:
                response = Response.query.filter_by(
                    setup_id=setup.id,
                    question_id=1
                ).first()
                
                if response:
                    response.answer = json.dumps(selected)
                    response.is_valid = True
                else:
                    response = Response(
                        setup_id=setup.id,
                        question_id=1,
                        answer=json.dumps(selected),
                        is_valid=True
                    )
                    db.session.add(response)
                    
                db.session.commit()
                session['current_initiative_index'] = 0
                flash('Initiatives saved successfully!', 'success')
                return redirect(url_for('routes.questionnaire', initiative_index=0))
                
            except Exception as e:
                logger.error(f"Error saving initiatives: {str(e)}")
                db.session.rollback()
                flash('Failed to save initiatives. Please try again.', 'error')
        
        return render_template('business_initiatives.html', 
                           initiatives=initiatives,
                           selected=selected)
                           
    except Exception as e:
        logger.error(f"Error in initiatives: {str(e)}")
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('routes.index'))

@routes.route('/questionnaire')
@routes.route('/questionnaire/<int:initiative_index>')
@login_required
def questionnaire(initiative_index=0):
    try:
        setup = get_latest_setup(current_user.id)
        if not setup:
            flash('Please complete the setup first.', 'info')
            return redirect(url_for('routes.setup'))
            
        initiatives_response = Response.query.filter_by(
            setup_id=setup.id,
            question_id=1
        ).first()
        
        if not initiatives_response or not initiatives_response.answer:
            flash('Please select your initiatives first.', 'info')
            return redirect(url_for('routes.initiatives'))
            
        try:
            selected_initiatives = json.loads(initiatives_response.answer)
            if not isinstance(selected_initiatives, list) or not selected_initiatives:
                flash('Invalid initiatives data. Please select again.', 'error')
                return redirect(url_for('routes.initiatives'))
        except json.JSONDecodeError:
            flash('Invalid initiatives data. Please select again.', 'error')
            return redirect(url_for('routes.initiatives'))
        
        session['current_initiative_index'] = initiative_index
        
        if initiative_index >= len(selected_initiatives):
            return redirect(url_for('routes.assessment_results'))
            
        current_initiative = selected_initiatives[initiative_index]
        questions = Question.query.filter_by(
            strategic_goal=current_initiative
        ).order_by(Question.order).all()
        
        if not questions:
            flash(f'No questions found for {current_initiative}', 'error')
            return redirect(url_for('routes.initiatives'))
            
        saved_answers = {}
        responses = Response.query.filter_by(
            setup_id=setup.id,
            is_valid=True
        ).all()
        
        for response in responses:
            if response.question_id != 1:
                try:
                    saved_answers[response.question_id] = json.loads(response.answer)
                except (json.JSONDecodeError, TypeError):
                    continue
        
        total_questions = sum(len(Question.query.filter_by(
            strategic_goal=init
        ).all()) for init in selected_initiatives)
        
        answered = len([r for r in responses if r.question_id != 1 and r.is_valid])
        progress = (answered / total_questions * 100) if total_questions > 0 else 0
        
        return render_template('questionnaire.html',
                           current_initiative=current_initiative,
                           questions={current_initiative: questions},
                           saved_answers=saved_answers,
                           progress=progress,
                           prev_url=url_for('routes.initiatives') if initiative_index == 0 else url_for('routes.questionnaire', initiative_index=initiative_index-1),
                           next_url=url_for('routes.questionnaire', initiative_index=initiative_index+1) if initiative_index < len(selected_initiatives)-1 else url_for('routes.assessment_results'))
                           
    except Exception as e:
        logger.error(f"Error loading questionnaire: {str(e)}")
        flash('An error occurred while loading the questionnaire. Please try again.', 'error')
        return redirect(url_for('routes.initiatives'))

@routes.route('/api/save-answer', methods=['POST'])
@login_required
def save_answer():
    try:
        setup = get_latest_setup(current_user.id)
        if not setup:
            return jsonify({
                'status': 'error',
                'message': 'Setup not found'
            }), 404

        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No data provided'
            }), 400

        question_id = data.get('question_id')
        answer = data.get('answer')

        if question_id is None or answer is None:
            return jsonify({
                'status': 'error',
                'message': 'Missing question_id or answer'
            }), 400

        question = Question.query.get(question_id)
        if not question:
            return jsonify({
                'status': 'error',
                'message': 'Question not found'
            }), 404

        response = Response.query.filter_by(
            setup_id=setup.id,
            question_id=question_id
        ).first()

        if response:
            response.answer = json.dumps(answer)
            response.is_valid = True
            response.timestamp = datetime.utcnow()
        else:
            response = Response(
                setup_id=setup.id,
                question_id=question_id,
                answer=json.dumps(answer),
                is_valid=True,
                timestamp=datetime.utcnow()
            )
            db.session.add(response)

        try:
            db.session.commit()
        except Exception as e:
            logger.error(f"Database error while saving answer: {str(e)}")
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': 'Failed to save answer'
            }), 500

        initiatives_response = Response.query.filter_by(
            setup_id=setup.id,
            question_id=1
        ).first()

        if not initiatives_response:
            return jsonify({
                'status': 'error',
                'message': 'No initiatives found'
            }), 404

        selected_initiatives = json.loads(initiatives_response.answer)
        total_questions = sum(
            len(Question.query.filter_by(strategic_goal=init).all())
            for init in selected_initiatives
        )

        answered = len(Response.query.filter(
            Response.setup_id == setup.id,
            Response.is_valid == True,
            Response.question_id != 1
        ).all())

        progress = (answered / total_questions * 100) if total_questions > 0 else 0

        return jsonify({
            'status': 'success',
            'is_valid': True,
            'progress': progress
        })

    except Exception as e:
        logger.error(f"Error in save_answer: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'An unexpected error occurred'
        }), 500

@routes.route('/assessment_results')
@login_required
def assessment_results():
    setup = get_latest_setup(current_user.id)
    if not setup:
        flash('Setup information not found.', 'error')
        return redirect(url_for('routes.setup'))

    try:
        # Get selected initiatives
        initiatives_response = Response.query.filter_by(
            setup_id=setup.id,
            question_id=1
        ).first()

        if not initiatives_response:
            flash('No initiatives found.', 'error')
            return redirect(url_for('routes.initiatives'))

        selected_initiatives = json.loads(initiatives_response.answer)
        results = {}

        # Process each initiative
        for initiative in selected_initiatives:
            questions = Question.query.filter_by(strategic_goal=initiative).all()
            initiative_results = {
                'questions': [],
                'average_maturity': 0
            }
            
            total_maturity = 0
            answered_count = 0

            for question in questions:
                response = Response.query.filter_by(
                    setup_id=setup.id,
                    question_id=question.id,
                    is_valid=True
                ).first()

                if response:
                    answer_index = json.loads(response.answer)
                    maturity_score = answer_index + 1  # Convert 0-based index to 1-5 score
                    total_maturity += maturity_score
                    answered_count += 1

                    initiative_results['questions'].append({
                        'area': question.major_cnapp_area,
                        'question': question.text,
                        'answer': question.options[answer_index],
                        'maturity_score': maturity_score
                    })

            if answered_count > 0:
                initiative_results['average_maturity'] = round(total_maturity / answered_count, 1)

            results[initiative] = initiative_results

        return render_template('assessment_results.html',
                           setup=setup,
                           results=results)

    except Exception as e:
        logger.error(f"Error generating assessment results: {str(e)}")
        flash('An error occurred while generating results. Please try again.', 'error')
        return redirect(url_for('routes.initiatives'))

@routes.route('/admin/questions')
@login_required
@admin_required
def admin_questions():
    questions = Question.query.order_by(Question.strategic_goal, Question.order).all()
    return render_template('admin/questions.html', questions=questions)

@routes.route('/admin/questions/add', methods=['GET', 'POST'])
@login_required
@admin_required
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
            logger.error(f"Error adding question: {str(e)}")
            flash('Error adding question', 'error')
            db.session.rollback()
    return render_template('admin/question_form.html')

@routes.route('/admin/questions/<int:question_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
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
            logger.error(f"Error updating question: {str(e)}")
            flash('Error updating question', 'error')
            db.session.rollback()
    return render_template('admin/question_form.html', question=question)

@routes.route('/admin/questions/<int:question_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_question(question_id):
    try:
        question = Question.query.get_or_404(question_id)
        db.session.delete(question)
        db.session.commit()
        flash('Question deleted successfully!', 'success')
    except Exception as e:
        logger.error(f"Error deleting question: {str(e)}")
        flash('Error deleting question', 'error')
        db.session.rollback()
    return redirect(url_for('routes.admin_questions'))
