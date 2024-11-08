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

# Global configuration
max_retries = 3

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

routes = Blueprint('routes', __name__)

def get_latest_setup(user_id):
    return Setup.query.filter_by(user_id=user_id).order_by(Setup.created_at.desc()).first()

def check_setup_required():
    if current_user.is_authenticated:
        setup = get_latest_setup(current_user.id)
        if not setup:
            flash('Please complete the setup first.', 'info')
            return redirect(url_for('routes.setup'))
    return None

@routes.route('/')
def index():
    try:
        if current_user.is_authenticated:
            setup = get_latest_setup(current_user.id)
            if not setup:
                flash('Please complete your setup information first.', 'info')
                return redirect(url_for('routes.setup'))

            # Check for initiatives selection
            initiatives_response = Response.query.filter_by(
                setup_id=setup.id,
                question_id=1
            ).order_by(Response.timestamp.desc()).first()
            
            if not initiatives_response:
                flash('Please select your strategic initiatives.', 'info')
                return redirect(url_for('routes.initiatives'))
            
            try:
                selected_initiatives = json.loads(initiatives_response.answer)
                if not isinstance(selected_initiatives, list) or not selected_initiatives:
                    flash('Please select valid initiatives.', 'info')
                    return redirect(url_for('routes.initiatives'))
                
                # Calculate total questions and answered questions
                total_questions = sum(
                    len(Question.query.filter_by(strategic_goal=str(init)).all())
                    for init in selected_initiatives
                )
                
                answered = len(Response.query.filter(
                    Response.setup_id == setup.id,
                    Response.is_valid == True,
                    Response.question_id != 1
                ).all())
                
                # If questionnaire is incomplete
                if answered < total_questions:
                    # Get the current initiative index
                    initiative_index = session.get('current_initiative_index', 0)
                    if initiative_index >= len(selected_initiatives):
                        initiative_index = 0
                    
                    # Find first incomplete initiative
                    for idx, initiative in enumerate(selected_initiatives[initiative_index:]):
                        questions = Question.query.filter_by(
                            strategic_goal=str(initiative)
                        ).all()
                        responses = Response.query.filter(
                            Response.setup_id == setup.id,
                            Response.question_id.in_([q.id for q in questions]),
                            Response.is_valid == True
                        ).all()
                        
                        if len(responses) < len(questions):
                            initiative_index = idx
                            break
                    
                    flash('Please complete the questionnaire for all selected initiatives.', 'info')
                    return redirect(url_for('routes.questionnaire', 
                                        initiative_index=initiative_index))
                
                # If everything is complete, show results
                return redirect(url_for('routes.assessment_results'))
                
            except (json.JSONDecodeError, TypeError):
                flash('Invalid initiative data. Please try again.', 'error')
                return redirect(url_for('routes.initiatives'))
        
        # If not authenticated, show landing page
        return render_template('index.html')
        
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
            
            retry_count = 0
            while retry_count < max_retries:
                try:
                    db.session.add(setup_info)
                    db.session.commit()
                    break
                except OperationalError:
                    if retry_count == max_retries - 1:
                        raise
                    retry_count += 1
                    sleep(1)
                    db.session.rollback()
            
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
            return redirect(url_for('routes.assessment_results'))
            
        current_initiative = selected_initiatives[initiative_index]
        
        # Ensure string comparison for strategic goal
        questions = Question.query.filter_by(
            strategic_goal=str(current_initiative)
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
            if response.question_id != 1:  # Skip initiatives response
                try:
                    answer_data = json.loads(response.answer)
                    saved_answers[response.question_id] = (
                        answer_data[0] if isinstance(answer_data, list) else answer_data
                    )
                except (json.JSONDecodeError, TypeError):
                    continue
        
        # Calculate progress across all initiatives
        total_questions = sum(
            len(Question.query.filter_by(strategic_goal=str(init)).all())
            for init in selected_initiatives
        )
        
        answered = len([r for r in responses if r.question_id != 1 and r.is_valid])
        progress = (answered / total_questions * 100) if total_questions > 0 else 0
        
        session['current_initiative_index'] = initiative_index
        
        return render_template('questionnaire.html',
                           current_initiative=current_initiative,
                           questions={current_initiative: questions},
                           saved_answers=saved_answers,
                           progress=progress,
                           prev_url=url_for('routes.initiatives') if initiative_index == 0 
                                  else url_for('routes.questionnaire', initiative_index=initiative_index-1),
                           next_url=url_for('routes.questionnaire', initiative_index=initiative_index+1) 
                                  if initiative_index < len(selected_initiatives)-1 
                                  else url_for('routes.assessment_results'))
                           
    except Exception as e:
        logger.error(f"Error in questionnaire route: {str(e)}")
        flash('An error occurred. Please try again.', 'error')
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

        # Validate answer type and convert if necessary
        try:
            if isinstance(answer, str):
                answer = int(answer)
            elif isinstance(answer, list):
                answer = [int(a) if isinstance(a, str) else a for a in answer]
        except (ValueError, TypeError):
            return jsonify({
                'status': 'error',
                'message': 'Invalid answer format'
            }), 400

        # Validate question exists
        question = Question.query.get(question_id)
        if not question:
            return jsonify({
                'status': 'error',
                'message': 'Question not found'
            }), 404

        # Validate answer is within range
        if isinstance(answer, int) and (answer < 0 or answer >= len(question.options)):
            return jsonify({
                'status': 'error',
                'message': 'Answer out of range'
            }), 400

        retry_count = 0
        while retry_count < max_retries:
            try:
                response = Response.query.filter_by(
                    setup_id=setup.id,
                    question_id=question_id
                ).first()

                if response:
                    response.answer = json.dumps([answer] if isinstance(answer, int) else answer)
                    response.is_valid = True
                    response.timestamp = datetime.utcnow()
                else:
                    response = Response(
                        setup_id=setup.id,
                        question_id=question_id,
                        answer=json.dumps([answer] if isinstance(answer, int) else answer),
                        is_valid=True,
                        timestamp=datetime.utcnow()
                    )
                    db.session.add(response)

                db.session.commit()
                break
            except OperationalError:
                if retry_count == max_retries - 1:
                    return jsonify({
                        'status': 'error',
                        'message': 'Failed to save answer'
                    }), 500
                retry_count += 1
                sleep(1)
                db.session.rollback()

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

        try:
            selected_initiatives = json.loads(initiatives_response.answer)
            if not isinstance(selected_initiatives, list):
                selected_initiatives = []
        except (json.JSONDecodeError, TypeError):
            selected_initiatives = []

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
            'progress': progress,
            'answered': answered,
            'total': total_questions
        })

    except Exception as e:
        logger.error(f"Error in save_answer: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@routes.route('/assessment_results')
@login_required
def assessment_results():
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
            flash('No initiatives found. Please select your initiatives.', 'error')
            return redirect(url_for('routes.initiatives'))

        try:
            selected_initiatives = json.loads(initiatives_response.answer)
            if not isinstance(selected_initiatives, list) or not selected_initiatives:
                flash('Invalid initiatives data. Please select your initiatives again.', 'error')
                return redirect(url_for('routes.initiatives'))
        except (json.JSONDecodeError, TypeError):
            flash('Invalid initiatives data. Please select your initiatives again.', 'error')
            return redirect(url_for('routes.initiatives'))

        results = {}
        total_questions = 0
        total_answers = 0

        # Process each initiative
        for initiative in selected_initiatives:
            # Get questions for this initiative
            questions = Question.query.filter_by(
                strategic_goal=str(initiative)
            ).order_by(Question.order).all()

            if not questions:
                logger.warning(f"No questions found for initiative: {initiative}")
                continue

            total_questions += len(questions)

            # Get responses for these questions
            question_ids = [q.id for q in questions]
            responses = Response.query.filter(
                Response.setup_id == setup.id,
                Response.question_id.in_(question_ids),
                Response.is_valid == True
            ).all()

            total_answers += len(responses)

            # Map responses to questions
            response_map = {r.question_id: r for r in responses}

            # Calculate results for this initiative
            initiative_results = []
            total_maturity = 0
            question_count = 0

            for question in questions:
                response = response_map.get(question.id)
                if response:
                    try:
                        # Parse the answer value from JSON
                        answer_data = json.loads(response.answer)
                        answer_value = answer_data[0] if isinstance(answer_data, list) else answer_data

                        # Calculate maturity score (1-5 scale)
                        maturity_score = answer_value + 1

                        total_maturity += maturity_score
                        question_count += 1

                        initiative_results.append({
                            'area': question.major_cnapp_area,
                            'question': question.text,
                            'answer': question.options[answer_value].strip(),
                            'maturity_score': maturity_score
                        })
                    except (json.JSONDecodeError, IndexError, TypeError) as e:
                        logger.error(f"Error processing answer for question {question.id}: {e}")
                        continue

            # Calculate average maturity for this initiative
            average_maturity = round(total_maturity / question_count, 1) if question_count > 0 else 0

            results[initiative] = {
                'questions': initiative_results,
                'average_maturity': average_maturity
            }

        # Check if all questions are answered
        if total_answers < total_questions:
            flash('Please complete all questions before viewing results.', 'info')
            return redirect(url_for('routes.questionnaire', initiative_index=0))

        return render_template('assessment_results.html',
                           setup=setup,
                           results=results)

    except Exception as e:
        logger.error(f"Error in assessment_results: {str(e)}")
        flash('An error occurred loading results. Please try again.', 'error')
        return redirect(url_for('routes.index'))

# Admin routes for initiatives
@routes.route('/admin/initiatives')
@login_required
def admin_initiatives():
    # Admin authorization check
    if not current_user.email.endswith('@sentinelone.com') and current_user.email not in [
        'mpsmalls11@gmail.com', 'jaldevi72@gmail.com', 
        'm_mcgrail@outlook.com', 'gcastill0portfolio@gmail.com'
    ]:
        flash('Unauthorized access', 'error')
        return redirect(url_for('routes.index'))
        
    initiatives = Initiative.query.order_by(Initiative.order).all()
    return render_template('admin/initiatives.html', initiatives=initiatives)

@routes.route('/admin/initiatives/add', methods=['GET', 'POST'])
@login_required
def admin_add_initiative():
    # Admin authorization check
    if not current_user.email.endswith('@sentinelone.com') and current_user.email not in [
        'mpsmalls11@gmail.com', 'jaldevi72@gmail.com', 
        'm_mcgrail@outlook.com', 'gcastill0portfolio@gmail.com'
    ]:
        flash('Unauthorized access', 'error')
        return redirect(url_for('routes.index'))
        
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        
        if not title or not description:
            flash('All fields are required', 'error')
            return render_template('admin/initiative_form.html')
            
        initiative = Initiative(
            title=title,
            description=description,
            order=Initiative.query.count()
        )
        
        try:
            db.session.add(initiative)
            db.session.commit()
            flash('Initiative added successfully', 'success')
            return redirect(url_for('routes.admin_initiatives'))
        except Exception as e:
            db.session.rollback()
            flash('Error adding initiative', 'error')
            return render_template('admin/initiative_form.html')
            
    return render_template('admin/initiative_form.html')

@routes.route('/admin/initiatives/<int:initiative_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_initiative(initiative_id):
    # Admin authorization check
    if not current_user.email.endswith('@sentinelone.com') and current_user.email not in [
        'mpsmalls11@gmail.com', 'jaldevi72@gmail.com', 
        'm_mcgrail@outlook.com', 'gcastill0portfolio@gmail.com'
    ]:
        flash('Unauthorized access', 'error')
        return redirect(url_for('routes.index'))
        
    initiative = Initiative.query.get_or_404(initiative_id)
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        
        if not title or not description:
            flash('All fields are required', 'error')
            return render_template('admin/initiative_form.html', initiative=initiative)
            
        try:
            initiative.title = title
            initiative.description = description
            db.session.commit()
            flash('Initiative updated successfully', 'success')
            return redirect(url_for('routes.admin_initiatives'))
        except Exception as e:
            db.session.rollback()
            flash('Error updating initiative', 'error')
            return render_template('admin/initiative_form.html', initiative=initiative)
            
    return render_template('admin/initiative_form.html', initiative=initiative)

@routes.route('/admin/initiatives/<int:initiative_id>/delete', methods=['POST'])
@login_required
def admin_delete_initiative(initiative_id):
    # Admin authorization check
    if not current_user.email.endswith('@sentinelone.com') and current_user.email not in [
        'mpsmalls11@gmail.com', 'jaldevi72@gmail.com', 
        'm_mcgrail@outlook.com', 'gcastill0portfolio@gmail.com'
    ]:
        flash('Unauthorized access', 'error')
        return redirect(url_for('routes.index'))
        
    initiative = Initiative.query.get_or_404(initiative_id)
    
    try:
        db.session.delete(initiative)
        db.session.commit()
        flash('Initiative deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting initiative', 'error')
        
    return redirect(url_for('routes.admin_initiatives'))
