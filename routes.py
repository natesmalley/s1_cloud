import logging
from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from extensions import db, get_db
from models import Question, Response, User, Setup, Initiative
from functools import wraps
import json
from datetime import datetime
from sqlalchemy.exc import OperationalError
from time import sleep
from google_drive import GoogleDriveService

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
            'jaldevi72@gmail.com',
            'm_mcgrail@outlook.com',
            'sentinelhowie@gmail.com',
            's1.slappey@gmail.com',
            'gcastill0portfolio@gmail.com'
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
            if not setup:
                return redirect(url_for('routes.setup'))
                
            initiatives_response = Response.query.filter_by(
                setup_id=setup.id,
                question_id=1
            ).order_by(Response.timestamp.desc()).first()
            
            if not initiatives_response:
                return redirect(url_for('routes.initiatives'))
            
            # Check if all questions are answered for selected initiatives
            selected_initiatives = json.loads(initiatives_response.answer)
            total_questions = sum(
                len(Question.query.filter_by(strategic_goal=str(init)).all())
                for init in selected_initiatives
            )
            
            answered = len(Response.query.filter(
                Response.setup_id == setup.id,
                Response.is_valid == True,
                Response.question_id != 1
            ).all())
            
            if answered < total_questions:
                initiative_index = session.get('current_initiative_index', 0)
                return redirect(url_for('routes.questionnaire', initiative_index=initiative_index))
            
            return redirect(url_for('routes.assessment_results'))
            
        except Exception as e:
            logger.error(f"Error in index route: {str(e)}")
            flash('An error occurred. Please try again.', 'error')
            db.session.rollback()
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
                    response.timestamp = datetime.utcnow()
                else:
                    response = Response(
                        setup_id=setup.id,
                        question_id=1,
                        answer=json.dumps(selected),
                        is_valid=True,
                        timestamp=datetime.utcnow()
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
        
        if not initiatives_response:
            flash('Please select your initiatives first.', 'info')
            return redirect(url_for('routes.initiatives'))
            
        try:
            selected_initiatives = json.loads(initiatives_response.answer)
            if not isinstance(selected_initiatives, list) or not selected_initiatives:
                flash('Invalid initiatives data. Please select again.', 'error')
                return redirect(url_for('routes.initiatives'))
        except (json.JSONDecodeError, TypeError):
            flash('Invalid initiatives data. Please select again.', 'error')
            return redirect(url_for('routes.initiatives'))
        
        if initiative_index >= len(selected_initiatives):
            # Check if all questions are answered
            total_questions = sum(
                len(Question.query.filter_by(strategic_goal=str(init)).all())
                for init in selected_initiatives
            )
            
            answered = len(Response.query.filter(
                Response.setup_id == setup.id,
                Response.is_valid == True,
                Response.question_id != 1
            ).all())
            
            if answered < total_questions:
                # Redirect to first unanswered initiative
                for idx, initiative in enumerate(selected_initiatives):
                    questions = Question.query.filter_by(strategic_goal=str(initiative)).all()
                    responses = Response.query.filter(
                        Response.setup_id == setup.id,
                        Response.question_id.in_([q.id for q in questions]),
                        Response.is_valid == True
                    ).all()
                    
                    if len(responses) < len(questions):
                        return redirect(url_for('routes.questionnaire', initiative_index=idx))
            
            return redirect(url_for('routes.assessment_results'))
            
        current_initiative = selected_initiatives[initiative_index]
        questions = Question.query.filter_by(
            strategic_goal=str(current_initiative)
        ).order_by(Question.order).all()
        
        if not questions:
            flash(f'No questions found for {current_initiative}', 'error')
            return redirect(url_for('routes.initiatives'))
            
        # Add retry logic for database operations
        max_retries = 3
        retry_count = 0
        saved_answers = {}
        
        while retry_count < max_retries:
            try:
                responses = Response.query.filter_by(
                    setup_id=setup.id,
                    is_valid=True
                ).all()
                break
            except OperationalError:
                retry_count += 1
                if retry_count == max_retries:
                    raise
                sleep(1)
        
        for response in responses:
            if response.question_id != 1:
                try:
                    answer_data = json.loads(response.answer)
                    saved_answers[response.question_id] = answer_data[0] if isinstance(answer_data, list) else answer_data
                except (json.JSONDecodeError, TypeError):
                    continue
        
        total_questions = sum(len(Question.query.filter_by(
            strategic_goal=str(init)
        ).all()) for init in selected_initiatives)
        
        answered = len([r for r in responses if r.question_id != 1 and r.is_valid])
        progress = (answered / total_questions * 100) if total_questions > 0 else 0
        
        session['current_initiative_index'] = initiative_index
        
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

        # Handle both single integer and array answers
        answer_value = answer if isinstance(answer, list) else [answer]

        response = Response.query.filter_by(
            setup_id=setup.id,
            question_id=question_id
        ).first()

        if response:
            response.answer = json.dumps(answer_value)
            response.is_valid = True
            response.timestamp = datetime.utcnow()
        else:
            response = Response(
                setup_id=setup.id,
                question_id=question_id,
                answer=json.dumps(answer_value),
                is_valid=True,
                timestamp=datetime.utcnow()
            )
            db.session.add(response)

        db.session.commit()

        # Calculate progress
        initiatives_response = Response.query.filter_by(
            setup_id=setup.id,
            question_id=1
        ).first()

        if not initiatives_response:
            return jsonify({
                'status': 'error',
                'message': 'No initiatives found'
            }), 404

        # Parse selected initiatives as strings
        selected_initiatives = json.loads(initiatives_response.answer)
        if not isinstance(selected_initiatives, list):
            return jsonify({
                'status': 'error',
                'message': 'Invalid initiatives data'
            }), 400

        # Ensure initiative values are strings
        selected_initiatives = [str(init) if not isinstance(init, str) else init 
                              for init in selected_initiatives]

        # Calculate total questions using string comparison
        total_questions = sum(
            len(Question.query.filter_by(strategic_goal=str(init)).all())
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
    try:
        setup = get_latest_setup(current_user.id)
        if not setup:
            flash('Setup information not found.', 'error')
            return redirect(url_for('routes.setup'))

        initiatives_response = Response.query.filter_by(
            setup_id=setup.id,
            question_id=1
        ).first()

        if not initiatives_response:
            flash('No initiatives found.', 'error')
            return redirect(url_for('routes.initiatives'))

        selected_initiatives = json.loads(initiatives_response.answer)
        results = {}

        for initiative in selected_initiatives:
            # Ensure initiative is a string
            initiative = str(initiative)
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
                    answer_data = json.loads(response.answer)
                    answer_index = answer_data[0] if isinstance(answer_data, list) else answer_data
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

        return render_template('assessment_results.html', results=results, setup=setup)

    except Exception as e:
        logger.error(f"Error generating assessment results: {str(e)}")
        flash('An error occurred while generating results.', 'error')
        return redirect(url_for('routes.initiatives'))

@routes.route('/generate-roadmap')
@login_required
def generate_roadmap():
    try:
        setup = get_latest_setup(current_user.id)
        if not setup:
            flash('Please complete setup first.', 'info')
            return redirect(url_for('routes.setup'))

        initiatives_response = Response.query.filter_by(
            setup_id=setup.id,
            question_id=1
        ).first()

        if not initiatives_response:
            flash('Please complete the assessment first.', 'info')
            return redirect(url_for('routes.initiatives'))

        # Check if all questions are answered
        selected_initiatives = json.loads(initiatives_response.answer)
        total_questions = sum(
            len(Question.query.filter_by(strategic_goal=str(init)).all())
            for init in selected_initiatives
        )

        answered = len(Response.query.filter(
            Response.setup_id == setup.id,
            Response.is_valid == True,
            Response.question_id != 1
        ).all())

        if answered < total_questions:
            flash('Please complete all questions before generating the roadmap.', 'info')
            current_initiative_index = session.get('current_initiative_index', 0)
            return redirect(url_for('routes.questionnaire', initiative_index=current_initiative_index))

        return render_template('roadmap_generation.html')

    except Exception as e:
        logger.error(f"Error accessing roadmap generation: {str(e)}")
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('routes.assessment_results'))

@routes.route('/admin/questions')
@login_required
@admin_required
def admin_questions():
    questions = Question.query.order_by(Question.strategic_goal, Question.order).all()
    return render_template('admin/questions.html', questions=questions)

@routes.route('/admin/initiatives')
@login_required
@admin_required
def admin_initiatives():
    initiatives = Initiative.query.order_by(Initiative.order).all()
    return render_template('admin/initiatives.html', initiatives=initiatives)

@routes.route('/admin/initiatives/add', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_add_initiative():
    if request.method == 'POST':
        try:
            initiative = Initiative(
                title=request.form['title'],
                description=request.form['description'],
                order=0  # Will be last in order
            )
            db.session.add(initiative)
            db.session.commit()
            flash('Initiative added successfully!', 'success')
            return redirect(url_for('routes.admin_initiatives'))
        except Exception as e:
            logger.error(f"Error adding initiative: {str(e)}")
            flash('Error adding initiative', 'error')
            db.session.rollback()
    return render_template('admin/initiative_form.html')

@routes.route('/admin/initiatives/<int:initiative_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_initiative(initiative_id):
    initiative = Initiative.query.get_or_404(initiative_id)
    if request.method == 'POST':
        try:
            initiative.title = request.form['title']
            initiative.description = request.form['description']
            db.session.commit()
            flash('Initiative updated successfully!', 'success')
            return redirect(url_for('routes.admin_initiatives'))
        except Exception as e:
            logger.error(f"Error updating initiative: {str(e)}")
            flash('Error updating initiative', 'error')
            db.session.rollback()
    return render_template('admin/initiative_form.html', initiative=initiative)

@routes.route('/admin/initiatives/<int:initiative_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_initiative(initiative_id):
    initiative = Initiative.query.get_or_404(initiative_id)
    try:
        db.session.delete(initiative)
        db.session.commit()
        flash('Initiative deleted successfully!', 'success')
    except Exception as e:
        logger.error(f"Error deleting initiative: {str(e)}")
        flash('Error deleting initiative', 'error')
        db.session.rollback()
    return redirect(url_for('routes.admin_initiatives'))

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
    question = Question.query.get_or_404(question_id)
    try:
        db.session.delete(question)
        db.session.commit()
        flash('Question deleted successfully!', 'success')
    except Exception as e:
        logger.error(f"Error deleting question: {str(e)}")
        flash('Error deleting question', 'error')
        db.session.rollback()
    return redirect(url_for('routes.admin_questions'))
