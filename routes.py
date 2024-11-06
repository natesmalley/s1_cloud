from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models import Question, Response, Presentation, User, Setup
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

routes = Blueprint('routes', __name__)

@routes.route('/')
def index():
    if current_user.is_authenticated:
        # Check if setup is completed
        setup = Setup.query.filter_by(user_id=current_user.id).first()
        if setup:
            return redirect(url_for('routes.initiatives'))
        return redirect(url_for('routes.setup'))
    return render_template('index.html')

@routes.route('/setup', methods=['GET', 'POST'])
@login_required
def setup():
    if request.method == 'POST':
        try:
            setup_info = Setup(
                user_id=current_user.id,
                advisor_name=request.form['advisor_name'],
                advisor_email=request.form['advisor_email'],
                leader_name=request.form['leader_name'],
                leader_email=request.form['leader_email'],
                leader_employer=request.form['leader_employer']
            )
            db.session.add(setup_info)
            db.session.commit()
            return redirect(url_for('routes.initiatives'))
        except Exception as e:
            logger.error(f"Error saving setup information: {str(e)}")
            db.session.rollback()
            return render_template('setup.html', error="Failed to save setup information. Please try again.")
    
    # Check if setup already exists
    existing_setup = Setup.query.filter_by(user_id=current_user.id).first()
    if existing_setup:
        return redirect(url_for('routes.initiatives'))
        
    return render_template('setup.html')

@routes.route('/initiatives', methods=['GET', 'POST'])
@login_required
def initiatives():
    initiatives = [
        {
            'title': 'Cloud Adoption and Business Alignment',
            'description': 'Ensure cloud adoption is in line with the organization\'s overarching business objectives, providing a secure and compliant foundation for business activities.'
        },
        {
            'title': 'Achieving Key Business Outcomes',
            'description': 'Drive security practices that directly support business outcomes, ensuring risk mitigation efforts contribute positively to overall business performance.'
        },
        {
            'title': 'Maximizing ROI for Cloud Security',
            'description': 'Evaluate cloud security investments to maximize return on investment, ensuring that security measures are both effective and financially sustainable.'
        },
        {
            'title': 'Integration of Cloud Security with Business Strategy',
            'description': 'Integrate cloud security practices within the broader IT and business strategies to ensure cohesive growth, operational efficiency, and security posture.'
        },
        {
            'title': 'Driving Innovation and Value Delivery',
            'description': 'Facilitate secure innovation by embedding proactive risk management into cloud projects, enabling business opportunities while minimizing risk.'
        },
        {
            'title': 'Supporting Digital Transformation',
            'description': 'Leverage cloud security to support digital transformation initiatives, ensuring that new technologies and processes are securely adopted.'
        },
        {
            'title': 'Balancing Rapid Adoption with Compliance',
            'description': 'Achieve a balance between rapidly adopting cloud technologies and maintaining compliance, ensuring security does not hinder business agility.'
        }
    ]
    
    # Get previously selected initiatives
    response = Response.query.filter_by(user_id=current_user.id, question_id=1).first()
    selected = json.loads(response.answer) if response else []
    
    return render_template('business_initiatives.html', 
                         initiatives=initiatives,
                         selected=selected)

@routes.route('/save-initiatives', methods=['POST'])
@login_required
def save_initiatives():
    selected = request.form.getlist('selected_initiatives')
    
    if not 1 <= len(selected) <= 3:
        flash('Please select between 1 and 3 initiatives.', 'error')
        return redirect(url_for('routes.initiatives'))
    
    try:
        response = Response.query.filter_by(
            user_id=current_user.id,
            question_id=1
        ).first()
        
        if response:
            response.answer = json.dumps(selected)
            response.is_valid = True
        else:
            response = Response(
                user_id=current_user.id,
                question_id=1,
                answer=json.dumps(selected),
                is_valid=True
            )
            db.session.add(response)
            
        db.session.commit()
        return redirect(url_for('routes.questionnaire'))
        
    except Exception as e:
        db.session.rollback()
        flash('Failed to save initiatives. Please try again.', 'error')
        return redirect(url_for('routes.initiatives'))

@routes.route('/questionnaire')
@login_required
def questionnaire():
    # Check if setup is completed
    setup = Setup.query.filter_by(user_id=current_user.id).first()
    if not setup:
        return redirect(url_for('routes.setup'))
        
    # Get selected initiatives
    initiatives_response = Response.query.filter_by(
        user_id=current_user.id,
        question_id=1
    ).first()
    
    if not initiatives_response:
        return redirect(url_for('routes.initiatives'))
    
    selected_initiatives = json.loads(initiatives_response.answer)
    
    # Get questions for selected initiatives
    questions = {}
    for initiative in selected_initiatives:
        questions[initiative] = Question.query.filter_by(
            strategic_goal=initiative
        ).order_by(Question.order).all()
    
    # Get saved answers
    saved_answers = {}
    answers = Response.query.filter_by(
        user_id=current_user.id,
        is_valid=True
    ).all()
    
    for answer in answers:
        if answer.answer.isdigit():  # Check if it's a questionnaire answer
            saved_answers[answer.question_id] = int(answer.answer)
    
    # Calculate progress
    progress = calculate_progress()
    
    return render_template('questionnaire.html',
                         selected_initiatives=selected_initiatives,
                         questions=questions,
                         saved_answers=saved_answers,
                         progress=progress)

@routes.route('/generate-roadmap')
@login_required
def generate_roadmap():
    # Get selected initiatives
    initiatives_response = Response.query.filter_by(
        user_id=current_user.id,
        question_id=1
    ).first()
    
    if not initiatives_response:
        flash('Please select your initiatives first.', 'error')
        return redirect(url_for('routes.initiatives'))
    
    # Get all answers
    answers = Response.query.filter_by(
        user_id=current_user.id,
        is_valid=True
    ).all()
    
    if len(answers) < 2:  # Only initiatives selected, no questions answered
        flash('Please complete the questionnaire before generating the roadmap.', 'error')
        return redirect(url_for('routes.questionnaire'))
    
    try:
        # Here we'll implement the actual roadmap generation logic later
        flash('Roadmap generation coming soon!', 'info')
        return redirect(url_for('routes.questionnaire'))
    except Exception as e:
        logger.error(f"Error generating roadmap: {str(e)}")
        flash('Failed to generate roadmap. Please try again.', 'error')
        return redirect(url_for('routes.questionnaire'))

@routes.route('/api/save-answer', methods=['POST'])
@login_required
def save_answer():
    try:
        data = request.get_json()
        question_id = data.get('question_id')
        answer = data.get('answer')
        
        if question_id is None or answer is None:
            return jsonify({
                'status': 'error',
                'message': 'Missing required fields'
            }), 400
            
        # Validate answer (should be between 0-4 for our 5-point scale)
        if not isinstance(answer, int) or not 0 <= answer <= 4:
            return jsonify({
                'status': 'error',
                'message': 'Invalid answer value'
            }), 400
            
        # Save or update response
        response = Response.query.filter_by(
            user_id=current_user.id,
            question_id=question_id
        ).first()
        
        if response:
            response.answer = str(answer)
            response.is_valid = True
        else:
            response = Response(
                user_id=current_user.id,
                question_id=question_id,
                answer=str(answer),
                is_valid=True
            )
            db.session.add(response)
            
        db.session.commit()
        
        # Calculate new progress
        progress = calculate_progress()
        
        return jsonify({
            'status': 'success',
            'progress': progress
        })
        
    except Exception as e:
        logger.error(f"Error saving answer: {str(e)}")
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'Failed to save answer'
        }), 500

def calculate_progress():
    """Calculate user's progress through the questionnaire"""
    try:
        # Get selected initiatives
        initiatives_response = Response.query.filter_by(
            user_id=current_user.id,
            question_id=1
        ).first()
        
        if not initiatives_response:
            return 0
            
        selected_initiatives = json.loads(initiatives_response.answer)
        
        # Get total questions for selected initiatives
        total_questions = Question.query.filter(
            Question.strategic_goal.in_(selected_initiatives)
        ).count()
        
        if total_questions == 0:
            return 0
        
        # Get number of valid answers (excluding initiatives selection)
        answered_questions = Response.query.filter(
            Response.user_id == current_user.id,
            Response.is_valid == True,
            Response.question_id != 1  # Exclude initiatives selection
        ).count()
        
        return (answered_questions / total_questions) * 100
        
    except Exception as e:
        logger.error(f"Error calculating progress: {str(e)}")
        return 0

@routes.route('/api/progress')
@login_required
def get_progress():
    try:
        progress = calculate_progress()
        return jsonify({
            'progress': progress
        })
    except Exception as e:
        logger.error(f"Error getting progress: {str(e)}")
        return jsonify({
            'error': 'Failed to get progress'
        }), 500
