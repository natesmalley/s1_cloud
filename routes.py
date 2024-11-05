from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from extensions import db
from models import Question, Response, Presentation, User
from google_drive import GoogleDriveService
import re
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

routes = Blueprint('routes', __name__)
google_drive = GoogleDriveService()

def validate_answer(question, answer):
    """Validate answer based on question type and rules"""
    if not answer or not str(answer).strip():
        return False, "Answer cannot be empty"
        
    if question.question_type == 'multiple_choice':
        if answer not in question.options:
            return False, "Invalid option selected"
            
    if question.validation_rules:
        rules = question.validation_rules
        if rules.get('min_length') and len(str(answer)) < rules['min_length']:
            return False, f"Answer must be at least {rules['min_length']} characters long"
            
        if rules.get('max_length') and len(str(answer)) > rules['max_length']:
            return False, f"Answer must not exceed {rules['max_length']} characters"
            
        if rules.get('pattern'):
            if not re.match(rules['pattern'], str(answer)):
                return False, "Answer format is invalid"
                
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
        return render_template('questionnaire.html')
    return render_template('index.html')

@routes.route('/setup')
@login_required
def setup():
    return render_template('setup.html')

@routes.route('/questionnaire')
@login_required
def questionnaire():
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
            'type': q.question_type,
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
            'answer': r.answer
        } for r in responses])
    except Exception as e:
        logger.error(f"Error fetching saved answers: {str(e)}")
        return jsonify({'error': 'Failed to load saved answers'}), 500

@routes.route('/api/submit-answer', methods=['POST'])
@login_required
def submit_answer():
    try:
        data = request.json
        
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
        if not is_valid and question.required:
            return jsonify({
                'status': 'error',
                'message': validation_message
            }), 400
        
        # Update or create response
        response = Response.query.filter_by(
            user_id=current_user.id,
            question_id=data['question_id']
        ).first()
        
        if response:
            response.answer = data['answer']
            response.is_valid = is_valid
            response.validation_message = validation_message
        else:
            response = Response(
                user_id=current_user.id,
                question_id=data['question_id'],
                answer=data['answer'],
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
        logger.error(f"Error submitting answer: {str(e)}")
        db.session.rollback()
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
                is_valid, message = validate_answer(question, response.answer)
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
            f"Roadmap for {current_user.username}",
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
    content = "# Strategic Roadmap\n\n"
    content += "## Executive Summary\n"
    # Add more sections based on responses
    return content