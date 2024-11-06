from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from extensions import db
from models import Question, Response, Presentation, User, Setup
from google_drive import GoogleDriveService
from functools import wraps
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

routes = Blueprint('routes', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please login first.', 'error')
            return redirect(url_for('google_auth.login'))
        if not current_user.email.endswith('@s1.ai'):
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

initiatives_list = [
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

@routes.route('/')
def index():
    if current_user.is_authenticated:
        setup = get_latest_setup(current_user.id)
        if setup:
            all_setups = Setup.query.filter_by(leader_email=setup.leader_email).all()
            setup_ids = [s.id for s in all_setups]
            initiatives_response = Response.query.filter(
                Response.setup_id.in_(setup_ids),
                Response.question_id == 1
            ).order_by(Response.timestamp.desc()).first()
            
            if initiatives_response:
                return redirect(url_for('routes.questionnaire', initiative_index=0))
            return redirect(url_for('routes.initiatives'))
        return redirect(url_for('routes.setup'))
    return render_template('index.html')

@routes.route('/setup', methods=['GET', 'POST'])
@login_required
def setup():
    existing_setup = get_latest_setup(current_user.id)
    if existing_setup and request.method == 'GET':
        flash('Setup already completed.', 'info')
        return redirect(url_for('routes.initiatives'))

    if request.method == 'POST':
        try:
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
        except Exception as e:
            logger.error(f"Error saving setup information: {str(e)}")
            db.session.rollback()
            flash('Failed to save setup information. Please try again.', 'error')
    
    return render_template('setup.html')

@routes.route('/initiatives', methods=['GET', 'POST'])
@login_required
def initiatives():
    setup_redirect = check_setup_required()
    if setup_redirect:
        return setup_redirect
    
    setup = get_latest_setup(current_user.id)
    leader_email = setup.leader_email
    all_setups = Setup.query.filter_by(leader_email=leader_email).all()
    setup_ids = [s.id for s in all_setups]
    
    try:
        response = Response.query.filter(
            Response.setup_id.in_(setup_ids),
            Response.question_id == 1
        ).order_by(Response.timestamp.desc()).first()
        
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
                               initiatives=initiatives_list,
                               selected=selected)
        
        try:
            response = Response.query.filter(
                Response.setup_id.in_(setup_ids),
                Response.question_id == 1
            ).order_by(Response.timestamp.desc()).first()
            
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
                        initiatives=initiatives_list,
                        selected=selected)

@routes.route('/questionnaire')
@routes.route('/questionnaire/<int:initiative_index>')
@login_required
def questionnaire(initiative_index=None):
    setup_redirect = check_setup_required()
    if setup_redirect:
        return setup_redirect
        
    setup = get_latest_setup(current_user.id)
    if not setup:
        flash('Setup not found', 'error')
        return redirect(url_for('routes.setup'))
        
    leader_email = setup.leader_email
    all_setups = Setup.query.filter_by(leader_email=leader_email).all()
    setup_ids = [s.id for s in all_setups]
    
    initiatives_response = Response.query.filter(
        Response.setup_id.in_(setup_ids),
        Response.question_id == 1
    ).order_by(Response.timestamp.desc()).first()
    
    if not initiatives_response:
        flash('Please select your initiatives first.', 'info')
        return redirect(url_for('routes.initiatives'))
    
    try:
        selected_initiatives = json.loads(initiatives_response.answer)
        if not isinstance(selected_initiatives, list):
            flash('Invalid initiatives data. Please select again.', 'error')
            return redirect(url_for('routes.initiatives'))
            
        if not 1 <= len(selected_initiatives) <= 3:
            flash('Please select between 1 and 3 initiatives.', 'error')
            return redirect(url_for('routes.initiatives'))
            
        try:
            index = int(initiative_index or 0)
            if index >= len(selected_initiatives):
                return redirect(url_for('routes.assessment_results'))
            if index < 0:
                index = 0
        except (TypeError, ValueError):
            index = 0
            
        current_initiative = selected_initiatives[index]
        questions = {
            current_initiative: Question.query.filter_by(
                strategic_goal=current_initiative
            ).order_by(Question.order).all()
        }
        
        saved_answers = {}
        answers = Response.query.filter(
            Response.setup_id.in_(setup_ids),
            Response.is_valid == True
        ).all()
        
        for answer in answers:
            try:
                if answer.question_id != 1:
                    saved_answers[answer.question_id] = json.loads(answer.answer)
            except (json.JSONDecodeError, TypeError):
                continue
        
        prev_url = url_for('routes.initiatives') if index == 0 else url_for('routes.questionnaire', initiative_index=index-1)
        next_url = url_for('routes.questionnaire', initiative_index=index+1) if index < len(selected_initiatives)-1 else url_for('routes.assessment_results')
        
        total_questions = Question.query.filter(
            Question.strategic_goal.in_(selected_initiatives)
        ).count()
        
        answered_questions = Response.query.filter(
            Response.setup_id.in_(setup_ids),
            Response.is_valid == True,
            Response.question_id != 1
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
        flash('An error occurred. Please try again.', 'error')
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
        
    leader_email = setup.leader_email
    try:
        data = request.get_json()
        question_id = data.get('question_id')
        answer = data.get('answer')
        
        if question_id is None or answer is None:
            return jsonify({
                'status': 'error',
                'message': 'Missing required fields'
            }), 400
        
        all_setups = Setup.query.filter_by(leader_email=leader_email).all()
        setup_ids = [s.id for s in all_setups]
        
        response = Response.query.filter(
            Response.setup_id.in_(setup_ids),
            Response.question_id == question_id
        ).order_by(Response.timestamp.desc()).first()
        
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
        
        initiatives_response = Response.query.filter(
            Response.setup_id.in_(setup_ids),
            Response.question_id == 1
        ).order_by(Response.timestamp.desc()).first()
        
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
            Response.setup_id.in_(setup_ids),
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

@routes.route('/assessment_results')
@login_required
def assessment_results():
    setup = get_latest_setup(current_user.id)
    if not setup:
        flash('Setup not found', 'error')
        return redirect(url_for('routes.setup'))
        
    leader_email = setup.leader_email
    all_setups = Setup.query.filter_by(leader_email=leader_email).all()
    setup_ids = [s.id for s in all_setups]
    
    responses = Response.query.filter(
        Response.setup_id.in_(setup_ids),
        Response.is_valid == True
    ).all()
    
    initiatives_response = next((r for r in responses if r.question_id == 1), None)
    if not initiatives_response:
        flash('No initiatives found', 'error')
        return redirect(url_for('routes.initiatives'))
        
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
            response = next((r for r in responses if r.question_id == question.id), None)
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
    
    return render_template('assessment_results.html',
                       setup=setup,
                       results=results)

@routes.route('/generate_roadmap')
@login_required
def generate_roadmap():
    setup_redirect = check_setup_required()
    if setup_redirect:
        return setup_redirect
        
    setup = get_latest_setup(current_user.id)
    leader_email = setup.leader_email
    all_setups = Setup.query.filter_by(leader_email=leader_email).all()
    setup_ids = [s.id for s in all_setups]
    
    initiatives_response = Response.query.filter(
        Response.setup_id.in_(setup_ids),
        Response.question_id == 1
    ).order_by(Response.timestamp.desc()).first()
    
    if not initiatives_response:
        flash('Please select your initiatives first.', 'info')
        return redirect(url_for('routes.initiatives'))
        
    try:
        selected_initiatives = json.loads(initiatives_response.answer)
        if not isinstance(selected_initiatives, list):
            flash('Invalid initiatives data. Please select again.', 'error')
            return redirect(url_for('routes.initiatives'))
            
        for initiative in selected_initiatives:
            questions = Question.query.filter_by(
                strategic_goal=initiative
            ).all()
            
            for question in questions:
                response = Response.query.filter(
                    Response.setup_id.in_(setup_ids),
                    Response.question_id == question.id,
                    Response.is_valid == True
                ).first()
                
                if not response:
                    flash(f'Please answer all questions for {initiative}.', 'error')
                    index = selected_initiatives.index(initiative)
                    return redirect(url_for('routes.questionnaire', initiative_index=index))
        
        return render_template('roadmap_generation.html')
        
    except Exception as e:
        logger.error(f"Error in generate_roadmap: {str(e)}")
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('routes.initiatives'))

@routes.route('/api/generate-assessment', methods=['POST'])
@login_required
def generate_assessment():
    setup = get_latest_setup(current_user.id)
    if not setup:
        return jsonify({
            'status': 'error',
            'message': 'Setup not found'
        }), 404

    leader_email = setup.leader_email
    try:
        if not hasattr(current_user, 'credentials') or not current_user.credentials:
            return jsonify({
                'status': 'error',
                'message': 'No Google Drive credentials found. Please sign in again.'
            }), 401
            
        all_setups = Setup.query.filter_by(leader_email=leader_email).all()
        setup_ids = [s.id for s in all_setups]
        
        responses = Response.query.filter(
            Response.setup_id.in_(setup_ids),
            Response.is_valid == True
        ).all()
        
        initiatives_response = next((r for r in responses if r.question_id == 1), None)
        if not initiatives_response:
            return jsonify({
                'status': 'error',
                'message': 'No initiatives found'
            }), 404
            
        selected_initiatives = json.loads(initiatives_response.answer)
        
        content = f'''Cloud Security Maturity Assessment
Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

Security Advisor: {setup.advisor_name} ({setup.advisor_email})
Security Leader: {setup.leader_name} ({setup.leader_email})
Organization: {setup.leader_employer}

Selected Business Initiatives:
'''
        
        for initiative in selected_initiatives:
            content += f"\n{initiative}\n"
            questions = Question.query.filter_by(strategic_goal=initiative).order_by(Question.order).all()
            
            for question in questions:
                response = next((r for r in responses if r.question_id == question.id), None)
                if response:
                    answer_index = int(json.loads(response.answer))
                    chosen_answer = question.options[answer_index]
                    maturity_score = answer_index + 1
                    
                    content += f"\nQuestion: {question.text}"
                    content += f"\nArea: {question.major_cnapp_area}"
                    content += f"\nResponse: {chosen_answer}"
                    content += f"\nMaturity Level: {maturity_score}/5\n"
        
        drive_service = GoogleDriveService()
        doc_id = drive_service.create_presentation(
            credentials=current_user.credentials,
            title=f"Cloud Security Maturity Assessment - {setup.leader_employer}",
            content=content
        )
        
        if not doc_id:
            logger.error("Failed to create Google Doc")
            return jsonify({
                'status': 'error',
                'message': 'Unable to create document. Please try again.'
            }), 500
            
        doc_url = f"https://docs.google.com/document/d/{doc_id}"
        
        presentation = Presentation(
            user_id=current_user.id,
            google_doc_id=doc_id,
            created_at=datetime.utcnow()
        )
        
        try:
            db.session.add(presentation)
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'doc_url': doc_url
            })
            
        except Exception as e:
            logger.error(f"Error saving presentation record: {str(e)}")
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': 'Failed to save presentation record. Please try again.'
            }), 500
            
    except Exception as e:
        logger.error(f"Error generating assessment: {str(e)}")
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'Failed to generate assessment. Please try again.'
        }), 500

@routes.route('/admin/initiatives')
@admin_required
def admin_initiatives():
    initiatives = [
        {
            "title": initiative["title"],
            "description": initiative["description"]
        } for initiative in initiatives_list
    ]
    return render_template('admin/initiatives.html', initiatives=initiatives)

@routes.route('/admin/initiatives/add', methods=['GET', 'POST'])
@admin_required
def admin_add_initiative():
    if request.method == 'POST':
        try:
            title = request.form['title']
            description = request.form['description']
            
            initiatives_list.append({
                "title": title,
                "description": description
            })
            
            flash('Initiative added successfully!', 'success')
            return redirect(url_for('routes.admin_initiatives'))
        except Exception as e:
            flash(f'Error adding initiative: {str(e)}', 'error')
    return render_template('admin/initiative_form.html')

@routes.route('/admin/initiatives/edit/<string:title>', methods=['GET', 'POST'])
@admin_required
def admin_edit_initiative(title):
    initiative = next((i for i in initiatives_list if i["title"] == title), None)
    if not initiative:
        flash('Initiative not found', 'error')
        return redirect(url_for('routes.admin_initiatives'))
        
    if request.method == 'POST':
        try:
            initiative["title"] = request.form['title']
            initiative["description"] = request.form['description']
            flash('Initiative updated successfully!', 'success')
            return redirect(url_for('routes.admin_initiatives'))
        except Exception as e:
            flash(f'Error updating initiative: {str(e)}', 'error')
    return render_template('admin/initiative_form.html', initiative=initiative)

@routes.route('/admin/initiatives/delete/<string:title>', methods=['POST'])
@admin_required
def admin_delete_initiative(title):
    try:
        initiatives_list[:] = [i for i in initiatives_list if i["title"] != title]
        flash('Initiative deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting initiative: {str(e)}', 'error')
    return redirect(url_for('routes.admin_initiatives'))
