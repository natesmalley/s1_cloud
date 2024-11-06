from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import Question, Response, User
from extensions import db
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

routes = Blueprint('routes', __name__)

@routes.route('/api/auth-check')
def auth_check():
    if current_user.is_authenticated:
        return jsonify({'authenticated': True})
    return jsonify({'authenticated': False}), 401

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
        
        # Save response regardless of validation status
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

            # Calculate and update progress
            progress = calculate_progress(current_user.id)

            return jsonify({
                'status': 'success',
                'is_valid': is_valid,
                'message': validation_message,
                'progress': progress
            })

        except Exception as e:
            logger.error(f"Database error: {str(e)}")
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': 'Failed to save answer'
            }), 500

    except Exception as e:
        logger.error(f"Error submitting answer: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def validate_answer(question, answer):
    """Validate answer based on question type and rules"""
    if not answer:
        return False, "Answer cannot be empty"

    if question.question_type == 'multiple_choice':
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
        # Get total required questions
        total_questions = Question.query.filter_by(required=True).count()
        
        # Get valid answers for required questions
        valid_answers = Response.query.join(Question).filter(
            Response.user_id == user_id,
            Response.is_valid == True,
            Question.required == True
        ).count()

        if total_questions == 0:
            return 0

        progress = (valid_answers / total_questions) * 100
        
        # Update user's progress
        user = User.query.get(user_id)
        if user:
            user.progress_percentage = progress
            db.session.commit()

        return progress
    except Exception as e:
        logger.error(f"Error calculating progress: {str(e)}")
        return 0

@routes.route('/api/progress')
@login_required
def get_progress():
    try:
        progress = calculate_progress(current_user.id)
        return jsonify({'progress': progress})
    except Exception as e:
        logger.error(f"Error getting progress: {str(e)}")
        return jsonify({'error': 'Failed to get progress'}), 500
