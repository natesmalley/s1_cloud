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

def get_latest_setup(user_id):
    return Setup.query.filter_by(user_id=user_id).order_by(Setup.created_at.desc()).first()

@routes.route('/')
def index():
    if current_user.is_authenticated:
        setup = get_latest_setup(current_user.id)
        if setup:
            initiatives_response = Response.query.filter_by(
                setup_id=setup.id,
                question_id=1
            ).first()
            if initiatives_response:
                return redirect(url_for('routes.questionnaire', initiative_index=0))
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
                leader_employer=request.form['leader_employer'],
                created_at=datetime.utcnow()
            )
            db.session.add(setup_info)
            db.session.commit()
            flash('Setup completed successfully!', 'success')
            return redirect(url_for('routes.initiatives'))
        except Exception as e:
            logger.error(f"Error saving setup information: {str(e)}")
            db.session.rollback()
            flash('Failed to save setup information. Please try again.', 'error')
    
    return render_template('setup.html')

@routes.route('/initiatives', methods=['GET', 'POST'])
@login_required
def initiatives():
    setup = get_latest_setup(current_user.id)
    if not setup:
        return redirect(url_for('routes.setup'))
    
    initiatives = [
        {
            "title": "Cloud Adoption and Business Alignment",
            "description": "Ensure cloud adoption is in line with the organization's overarching business objectives, providing a secure and compliant foundation for business activities."
        },
        {
            "title": "Achieving Key Business Outcomes",
            "description": "Drive security practices that directly support business outcomes, ensuring risk mitigation efforts contribute positively to overall business performance."
        },
        {
            "title": "Maximizing ROI for Cloud Security",
            "description": "Evaluate cloud security investments to maximize return on investment, ensuring that security measures are both effective and financially sustainable."
        },
        {
            "title": "Integration of Cloud Security with Business Strategy",
            "description": "Integrate cloud security practices within the broader IT and business strategies to ensure cohesive growth, operational efficiency, and security posture."
        },
        {
            "title": "Driving Innovation and Value Delivery",
            "description": "Facilitate secure innovation by embedding proactive risk management into cloud projects, enabling business opportunities while minimizing risk."
        },
        {
            "title": "Supporting Digital Transformation",
            "description": "Leverage cloud security to support digital transformation initiatives, ensuring that new technologies and processes are securely adopted."
        },
        {
            "title": "Balancing Rapid Adoption with Compliance",
            "description": "Achieve a balance between rapidly adopting cloud technologies and maintaining compliance, ensuring security does not hinder business agility."
        }
    ]
    
    try:
        response = Response.query.filter_by(setup_id=setup.id, question_id=1).first()
        selected = []
        if response and response.answer:
            try:
                selected = json.loads(response.answer)
                if not isinstance(selected, list):
                    selected = []
            except (json.JSONDecodeError, TypeError):
                selected = []
    except Exception as e:
        logger.error(f"Error loading selected initiatives: {str(e)}")
        selected = []
    
    if request.method == 'POST':
        selected = request.form.getlist('selected_initiatives')
        
        if not 1 <= len(selected) <= 3:
            flash('Please select between 1 and 3 initiatives.', 'error')
            return render_template('business_initiatives.html', 
                                initiatives=initiatives,
                                selected=selected)
        
        try:
            response = Response.query.filter_by(setup_id=setup.id, question_id=1).first()
            
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
            return redirect(url_for('routes.questionnaire', initiative_index=0))
            
        except Exception as e:
            logger.error(f"Error saving initiatives: {str(e)}")
            db.session.rollback()
            flash('Failed to save initiatives. Please try again.', 'error')
    
    return render_template('business_initiatives.html', 
                         initiatives=initiatives,
                         selected=selected)

@routes.route('/questionnaire')
@routes.route('/questionnaire/<int:initiative_index>')
@login_required
def questionnaire(initiative_index=None):
    setup = get_latest_setup(current_user.id)
    if not setup:
        return redirect(url_for('routes.setup'))
        
    initiatives_response = Response.query.filter_by(
        setup_id=setup.id,
        question_id=1
    ).first()
    
    if not initiatives_response:
        return redirect(url_for('routes.initiatives'))
    
    try:
        selected_initiatives = json.loads(initiatives_response.answer)
        if not isinstance(selected_initiatives, list):
            return redirect(url_for('routes.initiatives'))
            
        try:
            index = int(initiative_index or 0)
            if index < 0 or index >= len(selected_initiatives):
                index = 0
        except (TypeError, ValueError):
            index = 0
            
        current_initiative = selected_initiatives[index]
        
        # Update query to ensure we get all questions for the current initiative
        questions = {
            current_initiative: Question.query.filter(
                Question.strategic_goal == current_initiative
            ).order_by(Question.order).all()
        }
        
        if not questions[current_initiative]:
            logger.error(f"No questions found for initiative: {current_initiative}")
        
        # Get saved answers for current setup
        saved_answers = {}
        answers = Response.query.filter_by(
            setup_id=setup.id,
            is_valid=True
        ).all()
        
        for answer in answers:
            try:
                if answer.question_id != 1:  # Skip initiative selection
                    saved_answers[answer.question_id] = json.loads(answer.answer)
            except (json.JSONDecodeError, TypeError):
                continue
        
        # Update navigation URLs
        prev_url = url_for('routes.initiatives') if index == 0 else url_for('routes.questionnaire', initiative_index=index-1)
        next_url = url_for('routes.questionnaire', initiative_index=index+1) if index < len(selected_initiatives)-1 else url_for('routes.generate_roadmap')
        
        # Calculate progress
        total_questions = Question.query.filter(
            Question.strategic_goal.in_(selected_initiatives)
        ).count()
        
        answered_questions = Response.query.filter(
            Response.setup_id == setup.id,
            Response.is_valid == True,
            Response.question_id != 1  # Exclude initiative selection
        ).count()
        
        progress = (answered_questions / total_questions * 100) if total_questions > 0 else 0
        
        return render_template('questionnaire.html',
                           current_initiative=current_initiative,
                           questions=questions,
                           saved_answers=saved_answers,
                           progress=progress,
                           prev_url=prev_url,
                           next_url=next_url)
                           
    except Exception as e:
        logger.error(f"Error in questionnaire: {str(e)}")
        return redirect(url_for('routes.initiatives'))

@routes.route('/api/save-answer', methods=['POST'])
@login_required
def save_answer():
    setup = get_latest_setup(current_user.id)
    if not setup:
        return jsonify({
            'status': 'error',
            'message': 'Setup not completed'
        }), 403
        
    try:
        data = request.get_json()
        question_id = data.get('question_id')
        answer = data.get('answer')
        
        if question_id is None or answer is None:
            return jsonify({
                'status': 'error',
                'message': 'Missing required fields'
            }), 400
        
        response = Response.query.filter_by(
            setup_id=setup.id,
            question_id=question_id
        ).first()
        
        if response:
            response.answer = json.dumps(answer)
            response.is_valid = True
        else:
            response = Response(
                setup_id=setup.id,
                question_id=question_id,
                answer=json.dumps(answer),
                is_valid=True
            )
            db.session.add(response)
            
        db.session.commit()
        
        # Calculate updated progress
        initiatives_response = Response.query.filter_by(
            setup_id=setup.id,
            question_id=1
        ).first()
        
        if not initiatives_response:
            return jsonify({
                'status': 'error',
                'message': 'No initiatives selected'
            }), 400
            
        selected_initiatives = json.loads(initiatives_response.answer)
        total_questions = Question.query.filter(
            Question.strategic_goal.in_(selected_initiatives)
        ).count()
        
        answered_questions = Response.query.filter(
            Response.setup_id == setup.id,
            Response.is_valid == True,
            Response.question_id != 1
        ).count()
        
        progress = (answered_questions / total_questions * 100) if total_questions > 0 else 0
        
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

@routes.route('/generate_roadmap')
@login_required
def generate_roadmap():
    setup = get_latest_setup(current_user.id)
    if not setup:
        return redirect(url_for('routes.setup'))
        
    # Get initiatives response
    initiatives_response = Response.query.filter_by(
        setup_id=setup.id,
        question_id=1
    ).first()
    
    if not initiatives_response:
        return redirect(url_for('routes.initiatives'))
        
    try:
        selected_initiatives = json.loads(initiatives_response.answer)
        if not isinstance(selected_initiatives, list):
            return redirect(url_for('routes.initiatives'))
            
        # Check if all questions are answered
        for initiative in selected_initiatives:
            questions = Question.query.filter_by(
                strategic_goal=initiative
            ).all()
            
            for question in questions:
                response = Response.query.filter_by(
                    setup_id=setup.id,
                    question_id=question.id,
                    is_valid=True
                ).first()
                
                if not response:
                    # Redirect to the first unanswered initiative
                    index = selected_initiatives.index(initiative)
                    return redirect(url_for('routes.questionnaire', initiative_index=index))
        
        # If all questions are answered, show the roadmap generation page
        return render_template('roadmap_generation.html')
        
    except Exception as e:
        logger.error(f"Error in generate_roadmap: {str(e)}")
        return redirect(url_for('routes.initiatives'))
