from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from extensions import db
from models import Question, Response, Presentation, User
from google_drive import GoogleDriveService
import re
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

routes = Blueprint('routes', __name__)
google_drive = GoogleDriveService()

@routes.after_request
def add_header(response):
    if 'static' in request.path:
        response.cache_control.max_age = 0  # No caching for static files
        response.cache_control.no_cache = True
        response.cache_control.no_store = True
        response.headers['Pragma'] = 'no-cache'
    return response

def validate_answer(question, answer):
    """Validate answer based on question type and rules"""
    if not answer:
        return False, "Answer cannot be empty"
        
    if question.question_type == 'multiple_choice':
        # Handle array of answers for multiple selection
        answer_list = answer if isinstance(answer, list) else [answer]
        
        # Get valid options from question
        valid_options = [opt['title'] for opt in question.options]
        
        # Validate that all selected options are valid
        if not all(opt in valid_options for opt in answer_list):
            return False, "Invalid option(s) selected"
        
        # Check min/max count validation rules
        if question.validation_rules:
            min_count = question.validation_rules.get('min_count', 0)
            max_count = question.validation_rules.get('max_count', len(valid_options))
            
            if len(answer_list) < min_count:
                return False, f"Please select at least {min_count} option(s)"
            if len(answer_list) > max_count:
                return False, f"Please select no more than {max_count} option(s)"
            
    return True, None

def calculate_progress(user_id):
    """Calculate user's progress through the questionnaire"""
    try:
        total_questions = Question.query.count()
        answered_questions = Response.query.filter_by(
            user_id=user_id,
            is_valid=True
        ).count()
        
        if total_questions == 0:
            return 0
            
        progress = (answered_questions / total_questions) * 100
        
        # Update user's progress
        user = User.query.get(user_id)
        if user:
            user.progress_percentage = progress
            db.session.commit()
        
        return progress
    except Exception as e:
        logger.error(f"Error calculating progress: {str(e)}")
        return 0

@routes.route('/')
def index():
    if current_user.is_authenticated:
        if not current_user.setup_completed:
            return redirect(url_for('routes.setup'))
        return redirect(url_for('routes.questionnaire'))
    return render_template('index.html')

@routes.route('/setup', methods=['GET', 'POST'])
@login_required
def setup():
    if current_user.setup_completed:
        return redirect(url_for('routes.questionnaire'))

    if request.method == 'POST':
        try:
            current_user.recorder_name = request.form['recorder_name']
            current_user.recorder_email = request.form['recorder_email']
            current_user.customer_company = request.form['customer_company']
            current_user.customer_name = request.form['customer_name']
            current_user.customer_title = request.form['customer_title']
            current_user.customer_email = request.form['customer_email']
            current_user.setup_completed = True
            
            db.session.commit()
            flash('Setup information saved successfully!', 'success')
            return redirect(url_for('routes.questionnaire'))
            
        except Exception as e:
            logger.error(f"Error saving setup information: {e}")
            flash('Error saving setup information. Please try again.', 'error')
            db.session.rollback()
            
    return render_template('setup.html')

@routes.route('/questionnaire')
@login_required
def questionnaire():
    if not current_user.setup_completed:
        flash('Please complete the setup first.', 'warning')
        return redirect(url_for('routes.setup'))
    return render_template('questionnaire.html')

@routes.route('/api/questions')
@login_required
def get_questions():
    try:
        questions = Question.query.order_by(Question.order).all()
        if not questions:
            logger.warning("No questions found in database")
            
        return jsonify([{
            'id': q.id,
            'text': q.text,
            'question_type': q.question_type,
            'options': q.options,
            'required': q.required,
            'validation_rules': q.validation_rules
        } for q in questions])
    except Exception as e:
        logger.error(f"Error fetching questions: {str(e)}")
        return jsonify({'error': 'Failed to load questions'}), 500

@routes.route('/api/saved-answers')
@login_required
def get_saved_answers():
    try:
        responses = Response.query.filter_by(
            user_id=current_user.id,
            is_valid=True
        ).all()
        return jsonify([{
            'question_id': r.question_id,
            'answer': json.loads(r.answer) if isinstance(r.answer, str) else r.answer
        } for r in responses])
    except Exception as e:
        logger.error(f"Error fetching saved answers: {str(e)}")
        return jsonify({'error': 'Failed to load saved answers'}), 500

@routes.route('/api/submit-answer', methods=['POST'])
@login_required
def submit_answer():
    try:
        data = request.json
        logger.info(f"Received answer submission: {data}")
        
        if not data or 'question_id' not in data or 'answer' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Missing required fields'
            }), 400
        
        question = Question.query.get(data['question_id'])
        if not question:
            return jsonify({
                'status': 'error',
                'message': 'Question not found'
            }), 404
        
        # Validate answer
        is_valid, validation_message = validate_answer(question, data['answer'])
        
        # Log validation results
        logger.info(f"Validation result for question {question.id}: valid={is_valid}, message={validation_message}")
        
        if not is_valid and question.required:
            return jsonify({
                'status': 'success',
                'is_valid': False,
                'message': validation_message
            }), 200
        
        # Ensure user exists
        user = User.query.get(current_user.id)
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found'
            }), 404
        
        # Update or create response
        try:
            response = Response.query.filter_by(
                user_id=current_user.id,
                question_id=data['question_id']
            ).first()
            
            answer_json = json.dumps(data['answer']) if isinstance(data['answer'], (list, dict)) else data['answer']
            
            if response:
                response.answer = answer_json
                response.is_valid = is_valid
                response.validation_message = validation_message
            else:
                response = Response(
                    user_id=current_user.id,
                    question_id=data['question_id'],
                    answer=answer_json,
                    is_valid=is_valid,
                    validation_message=validation_message
                )
                db.session.add(response)
            
            db.session.commit()
            
            # Update progress
            progress = calculate_progress(current_user.id)
            
            return jsonify({
                'status': 'success',
                'progress': progress,
                'is_valid': is_valid,
                'message': validation_message
            })
        except Exception as e:
            logger.error(f"Database error while saving response: {str(e)}")
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': 'Failed to save answer. Please try again.'
            }), 500
            
    except Exception as e:
        logger.error(f"Error submitting answer: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@routes.route('/api/progress')
@login_required
def get_progress():
    try:
        progress = calculate_progress(current_user.id)
        return jsonify({
            'progress': progress
        })
    except Exception as e:
        logger.error(f"Error getting progress: {str(e)}")
        return jsonify({
            'error': 'Failed to get progress'
        }), 500

@routes.route('/api/validate-answers')
@login_required
def validate_all_answers():
    try:
        questions = Question.query.all()
        responses = Response.query.filter_by(user_id=current_user.id).all()
        answered_questions = {r.question_id: r for r in responses}
        
        invalid_questions = []
        for question in questions:
            if question.required and question.id not in answered_questions:
                invalid_questions.append({
                    'question_id': question.id,
                    'message': 'This question requires an answer'
                })
            elif question.id in answered_questions:
                response = answered_questions[question.id]
                answer = json.loads(response.answer) if isinstance(response.answer, str) else response.answer
                is_valid, message = validate_answer(question, answer)
                if not is_valid and question.required:
                    invalid_questions.append({
                        'question_id': question.id,
                        'message': message
                    })
        
        return jsonify({
            'is_valid': len(invalid_questions) == 0,
            'invalid_questions': invalid_questions
        })
    except Exception as e:
        logger.error(f"Error validating all answers: {str(e)}")
        return jsonify({
            'error': 'Failed to validate answers'
        }), 500

@routes.route('/api/generate-roadmap', methods=['POST'])
@login_required
def generate_roadmap():
    try:
        # Verify all required questions are answered and valid
        validation_result = validate_all_answers()
        validation_data = validation_result.get_json()
        
        if not validation_data['is_valid']:
            return jsonify({
                'status': 'error',
                'message': 'Please answer all required questions correctly before generating the roadmap',
                'invalid_questions': validation_data['invalid_questions']
            }), 400
        
        responses = Response.query.filter_by(
            user_id=current_user.id,
            is_valid=True
        ).all()
        
        content = generate_roadmap_content(responses)
        
        doc_id = google_drive.create_presentation(
            current_user.credentials,
            f"Cloud Security Roadmap - {current_user.customer_company}",
            content
        )
        
        if doc_id:
            presentation = Presentation(
                user_id=current_user.id,
                google_doc_id=doc_id
            )
            db.session.add(presentation)
            db.session.commit()
            return jsonify({'status': 'success', 'doc_id': doc_id})
        
        return jsonify({
            'status': 'error',
            'message': 'Failed to create presentation'
        }), 500
    except Exception as e:
        logger.error(f"Error generating roadmap: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'An error occurred while generating the roadmap'
        }), 500

def generate_roadmap_content(responses):
    content = "# Cloud Security Roadmap\n\n"
    content += "## Selected Business Initiatives\n\n"
    
    for response in responses:
        question = Question.query.get(response.question_id)
        if question:
            content += f"### {question.text}\n"
            answer = json.loads(response.answer) if isinstance(response.answer, str) else response.answer
            if isinstance(answer, list):
                for item in answer:
                    content += f"- {item}\n"
            else:
                content += f"{answer}\n"
            content += "\n"
    
    return content
