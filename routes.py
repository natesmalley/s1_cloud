import logging
from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models import Question, Response, Presentation, User, Setup, Initiative
from google_drive import GoogleDriveService
from functools import wraps
import json
from datetime import datetime

# Configure logging
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
    if leader_email:
        return Setup.query.filter_by(leader_email=leader_email).order_by(Setup.created_at.desc()).first()
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
    if current_user.is_authenticated:
        setup = get_latest_setup(current_user.id)
        if setup:
            try:
                initiatives_response = Response.query.filter_by(
                    setup_id=setup.id,
                    question_id=1
                ).order_by(Response.timestamp.desc()).first()
                
                if initiatives_response:
                    return redirect(url_for('routes.questionnaire', initiative_index=0))
                return redirect(url_for('routes.initiatives'))
            except Exception as e:
                logger.error(f"Error in index route: {str(e)}")
                flash('An error occurred. Please try again.', 'error')
                return render_template('index.html')
        return redirect(url_for('routes.setup'))
    return render_template('index.html')

@routes.route('/setup', methods=['GET', 'POST'])
@login_required
def setup():
    try:
        if request.method == 'POST':
            required_fields = ['advisor_name', 'advisor_email', 'leader_name', 
                             'leader_email', 'leader_employer']
            if not all(field in request.form for field in required_fields):
                flash('All fields are required.', 'error')
                return render_template('setup.html')

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

        existing_setup = get_latest_setup(current_user.id)
        if existing_setup:
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
        
        if initiative_index >= len(selected_initiatives):
            return redirect(url_for('routes.generate_roadmap'))
            
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
                except json.JSONDecodeError:
                    continue
        
        total_questions = sum(len(Question.query.filter_by(
            strategic_goal=init
        ).all()) for init in selected_initiatives)
        
        answered = len([r for r in responses if r.question_id != 1])
        progress = (answered / total_questions * 100) if total_questions > 0 else 0
        
        return render_template('questionnaire.html',
                           current_initiative=current_initiative,
                           questions={current_initiative: questions},
                           saved_answers=saved_answers,
                           progress=progress,
                           prev_url=url_for('routes.initiatives') if initiative_index == 0 else url_for('routes.questionnaire', initiative_index=initiative_index-1),
                           next_url=url_for('routes.questionnaire', initiative_index=initiative_index+1) if initiative_index < len(selected_initiatives)-1 else None)
                           
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

        # Validate question exists
        question = Question.query.get(question_id)
        if not question:
            return jsonify({
                'status': 'error',
                'message': 'Question not found'
            }), 404

        # Get or create response
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

@routes.route('/generate_roadmap')
@login_required
def generate_roadmap():
    setup_redirect = check_setup_required()
    if setup_redirect:
        return setup_redirect
        
    setup = get_latest_setup(current_user.id)
    initiatives_response = Response.query.filter_by(
        setup_id=setup.id,
        question_id=1
    ).order_by(Response.timestamp.desc()).first()
    
    if not initiatives_response:
        flash('Please select your initiatives first.', 'info')
        return redirect(url_for('routes.initiatives'))
        
    try:
        selected_initiatives = json.loads(initiatives_response.answer)
        if not isinstance(selected_initiatives, list):
            flash('Invalid initiatives data. Please select again.', 'error')
            return redirect(url_for('routes.initiatives'))
            
        # Check if all questions are answered
        all_answered = True
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
                    all_answered = False
                    break
                    
            if not all_answered:
                break
                
        if not all_answered:
            flash('Please answer all questions before generating the roadmap.', 'info')
            return redirect(url_for('routes.questionnaire', initiative_index=0))
            
        return render_template('roadmap_generation.html')
        
    except json.JSONDecodeError:
        flash('Invalid initiatives data. Please select again.', 'error')
        return redirect(url_for('routes.initiatives'))
    except Exception as e:
        logger.error(f"Error generating roadmap: {str(e)}")
        flash('An error occurred while generating the roadmap. Please try again.', 'error')
        return redirect(url_for('routes.initiatives'))

@routes.route('/api/generate-assessment', methods=['POST'])
@login_required
def generate_assessment():
    try:
        if not current_user.credentials:
            return jsonify({
                'status': 'error',
                'message': 'Google Drive access not authorized'
            }), 401
            
        setup = get_latest_setup(current_user.id)
        if not setup:
            return jsonify({
                'status': 'error',
                'message': 'Setup not found'
            }), 404
            
        # Get assessment results
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
        results = {}
        
        for initiative in selected_initiatives:
            questions = Question.query.filter_by(
                strategic_goal=initiative
            ).order_by(Question.order).all()
            
            initiative_results = []
            total_maturity = 0
            question_count = 0
            
            for question in questions:
                response = Response.query.filter_by(
                    setup_id=setup.id,
                    question_id=question.id,
                    is_valid=True
                ).first()
                
                if response:
                    answer_index = int(json.loads(response.answer))
                    maturity_score = answer_index + 1
                    total_maturity += maturity_score
                    question_count += 1
                    
                    initiative_results.append({
                        'area': question.major_cnapp_area,
                        'question': question.text,
                        'answer': question.options[answer_index],
                        'maturity_score': maturity_score
                    })
            
            avg_maturity = round(total_maturity / question_count, 1) if question_count > 0 else 0
            results[initiative] = {
                'questions': initiative_results,
                'average_maturity': avg_maturity
            }
            
        # Generate content for Google Doc
        content = f"""Cloud Security Maturity Assessment Results
Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}

Assessment Information:
Security Advisor: {setup.advisor_name} ({setup.advisor_email})
Security Leader: {setup.leader_name} ({setup.leader_email})
Organization: {setup.leader_employer}

"""
        
        for initiative, data in results.items():
            content += f"\n{initiative}\n"
            content += f"Average Maturity Score: {data['average_maturity']}/5\n\n"
            
            for question in data['questions']:
                content += f"Area: {question['area']}\n"
                content += f"Question: {question['question']}\n"
                content += f"Response: {question['answer']}\n"
                content += f"Maturity Score: {question['maturity_score']}/5\n\n"
                
        # Create Google Doc
        drive_service = GoogleDriveService()
        doc_id = drive_service.create_presentation(
            current_user.credentials,
            f"Cloud Security Maturity Assessment - {setup.leader_employer}",
            content
        )
        
        if not doc_id:
            return jsonify({
                'status': 'error',
                'message': 'Failed to create Google Doc'
            }), 500
            
        # Save presentation record
        presentation = Presentation(
            user_id=current_user.id,
            google_doc_id=doc_id
        )
        db.session.add(presentation)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'doc_url': f"https://docs.google.com/document/d/{doc_id}"
        })
        
    except Exception as e:
        logger.error(f"Error generating assessment: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'An error occurred while generating the assessment'
        }), 500
