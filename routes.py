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
    
    try:
        response = Response.query.filter_by(user_id=current_user.id, question_id=1).first()
        if response and response.answer:
            try:
                selected = json.loads(response.answer)
                if not isinstance(selected, list):
                    selected = []
            except json.JSONDecodeError:
                selected = []
        else:
            selected = []
    except Exception as e:
        logger.error(f"Error loading selected initiatives: {str(e)}")
        selected = []
    
    return render_template('business_initiatives.html', 
                         initiatives=initiatives,
                         selected=selected)

@routes.route('/save-initiatives', methods=['POST'])
@login_required
def save_initiatives():
    setup = get_latest_setup(current_user.id)
    if not setup:
        return redirect(url_for('routes.setup'))
        
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
        else:
            response = Response(
                user_id=current_user.id,
                question_id=1,
                answer=json.dumps(selected),
                is_valid=True
            )
            db.session.add(response)
            
        db.session.commit()
        return redirect(url_for('routes.questionnaire', initiative_index=0))
        
    except Exception as e:
        db.session.rollback()
        flash('Failed to save initiatives. Please try again.', 'error')
        return redirect(url_for('routes.initiatives'))

@routes.route('/questionnaire')
@routes.route('/questionnaire/<initiative_index>')
@login_required
def questionnaire(initiative_index=None):
    setup = get_latest_setup(current_user.id)
    if not setup:
        return redirect(url_for('routes.setup'))
        
    initiatives_response = Response.query.filter_by(
        user_id=current_user.id,
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
        
        questions = {
            current_initiative: Question.query.filter_by(
                strategic_goal=current_initiative
            ).order_by(Question.order).all()
        }
        
        saved_answers = {}
        answers = Response.query.filter_by(
            user_id=current_user.id,
            is_valid=True
        ).all()
        
        for answer in answers:
            try:
                if answer.question_id != 1:
                    saved_answers[answer.question_id] = int(answer.answer)
            except (ValueError, TypeError):
                continue
        
        prev_url = url_for('routes.initiatives') if index == 0 else url_for('routes.questionnaire', initiative_index=index-1)
        next_url = url_for('routes.questionnaire', initiative_index=index+1) if index < len(selected_initiatives)-1 else None
        
        progress = calculate_progress()
        
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
        
        if not isinstance(answer, int) or not 0 <= answer <= 4:
            return jsonify({
                'status': 'error',
                'message': 'Invalid answer value'
            }), 400
        
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
    try:
        initiatives_response = Response.query.filter_by(
            user_id=current_user.id,
            question_id=1
        ).first()
        
        if not initiatives_response:
            return 0
            
        try:
            selected_initiatives = json.loads(initiatives_response.answer)
            if not isinstance(selected_initiatives, list):
                return 0
        except (json.JSONDecodeError, TypeError):
            return 0
        
        questions = Question.query.filter(
            Question.strategic_goal.in_(selected_initiatives)
        ).all()
        
        if not questions:
            return 0
            
        total_questions = len(questions)
        question_ids = [q.id for q in questions]
        
        answered_questions = Response.query.filter(
            Response.user_id == current_user.id,
            Response.is_valid == True,
            Response.question_id.in_(question_ids)
        ).count()
        
        progress = (answered_questions / total_questions) * 100
        return min(progress, 100)
        
    except Exception as e:
        logger.error(f"Error calculating progress: {str(e)}")
        return 0

@routes.route('/api/progress')
@login_required
def get_progress():
    setup = get_latest_setup(current_user.id)
    if not setup:
        return jsonify({
            'error': 'Setup not completed'
        }), 403
        
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

def calculate_maturity_score(answers, questions):
    if not answers:
        return 0
    
    total_score = 0
    max_possible = len(questions) * 4
    
    for answer in answers:
        try:
            score = int(answer.answer)
            total_score += score
        except (ValueError, TypeError):
            continue
    
    if max_possible == 0:
        return 0
        
    return (total_score / max_possible) * 5

def get_strengths_and_gaps(answers, questions):
    strengths = []
    gaps = []
    
    for answer in answers:
        question = next((q for q in questions if q.id == answer.question_id), None)
        if not question:
            continue
            
        try:
            score = int(answer.answer)
            if score >= 3:
                strengths.append({
                    'area': question.major_cnapp_area,
                    'detail': question.text,
                    'score': score
                })
            elif score <= 1:
                gaps.append({
                    'area': question.major_cnapp_area,
                    'detail': question.text,
                    'score': score
                })
        except (ValueError, TypeError):
            continue
            
    return strengths, gaps

def get_recommendations(gaps):
    recommendations = []
    
    for gap in gaps:
        if gap['score'] == 0:
            urgency = "Critical"
        else:
            urgency = "Important"
            
        recommendations.append({
            'area': gap['area'],
            'urgency': urgency,
            'recommendation': f"Improve {gap['area'].lower()} capabilities by addressing: {gap['detail']}"
        })
        
    return recommendations

@routes.route('/generate-roadmap')
@login_required
def generate_roadmap():
    try:
        setup = get_latest_setup(current_user.id)
        if not setup:
            flash('Please complete setup first.', 'error')
            return redirect(url_for('routes.setup'))
            
        initiatives_response = Response.query.filter_by(
            user_id=current_user.id,
            question_id=1
        ).first()
        
        if not initiatives_response:
            flash('Please select your initiatives first.', 'error')
            return redirect(url_for('routes.initiatives'))
            
        selected_initiatives = json.loads(initiatives_response.answer)
        
        answers = Response.query.filter_by(
            user_id=current_user.id,
            is_valid=True
        ).all()
        
        if len(answers) < 2:
            flash('Please complete the questionnaire before generating the roadmap.', 'error')
            return redirect(url_for('routes.questionnaire', initiative_index=0))
            
        content = []
        
        content.append("# Cloud Security Maturity Assessment\n\n")
        content.append(f"Generated on: {datetime.now().strftime('%B %d, %Y')}\n\n")
        
        content.append("## Executive Summary\n\n")
        content.append(f"This assessment was conducted for {setup.leader_employer} ")
        content.append(f"by {setup.advisor_name} (Security Advisor) ")
        content.append(f"in collaboration with {setup.leader_name} (Security Leader).\n\n")
        
        content.append("## Assessment Details\n\n")
        content.append("### Stakeholders\n\n")
        content.append(f"**Security Advisor:**\n- Name: {setup.advisor_name}\n- Email: {setup.advisor_email}\n\n")
        content.append(f"**Security Leader:**\n- Name: {setup.leader_name}\n- Email: {setup.leader_email}\n")
        content.append(f"- Organization: {setup.leader_employer}\n\n")
        
        total_score = 0
        total_initiatives = len(selected_initiatives)
        
        content.append("## Initiative Analysis\n\n")
        
        for initiative in selected_initiatives:
            content.append(f"### {initiative}\n\n")
            
            questions = Question.query.filter_by(strategic_goal=initiative).all()
            
            initiative_answers = [a for a in answers if a.question_id != 1]
            
            maturity_score = calculate_maturity_score(initiative_answers, questions)
            total_score += maturity_score
            
            content.append(f"**Current Maturity Level:** {maturity_score:.1f}/5.0\n\n")
            
            strengths, gaps = get_strengths_and_gaps(initiative_answers, questions)
            
            if strengths:
                content.append("#### Strengths\n")
                for strength in strengths:
                    content.append(f"- {strength['area']}: {strength['detail']}\n")
                content.append("\n")
                
            if gaps:
                content.append("#### Gaps\n")
                for gap in gaps:
                    content.append(f"- {gap['area']}: {gap['detail']}\n")
                content.append("\n")
                
            recommendations = get_recommendations(gaps)
            if recommendations:
                content.append("#### Recommendations\n")
                for rec in recommendations:
                    content.append(f"- [{rec['urgency']}] {rec['recommendation']}\n")
                content.append("\n")
                
        overall_score = total_score / total_initiatives if total_initiatives > 0 else 0
        content.insert(2, f"**Overall Maturity Score:** {overall_score:.1f}/5.0\n\n")
        
        google_drive = GoogleDriveService()
        doc_title = f"Cloud Security Maturity Assessment - {setup.leader_employer}"
        doc_content = "".join(content)
        
        doc_id = google_drive.create_presentation(current_user.get_credentials(), doc_title, doc_content)
        
        if not doc_id:
            raise Exception("Failed to create document in Google Drive")
            
        presentation = Presentation(
            user_id=current_user.id,
            google_doc_id=doc_id
        )
        db.session.add(presentation)
        db.session.commit()
        
        flash('Roadmap generated successfully!', 'success')
        return redirect(f"https://docs.google.com/document/d/{doc_id}")
        
    except Exception as e:
        logger.error(f"Error generating roadmap: {str(e)}")
        db.session.rollback()
        flash('Failed to generate roadmap. Please try again.', 'error')
        return redirect(url_for('routes.questionnaire', initiative_index=0))

@routes.route('/admin/questions')
@login_required
def admin_questions():
    questions = Question.query.order_by(Question.strategic_goal, Question.order).all()
    return render_template('admin/questions.html', questions=questions)

@routes.route('/admin/questions/add', methods=['GET', 'POST'])
@login_required
def admin_add_question():
    if request.method == 'POST':
        try:
            options = request.form['options'].split(',')
            options = [opt.strip() for opt in options if opt.strip()]
            
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
            db.session.rollback()
            logger.error(f"Error adding question: {str(e)}")
            flash('Failed to add question. Please try again.', 'error')
    
    return render_template('admin/question_form.html')

@routes.route('/admin/questions/<int:question_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_question(question_id):
    question = Question.query.get_or_404(question_id)
    
    if request.method == 'POST':
        try:
            options = request.form['options'].split(',')
            options = [opt.strip() for opt in options if opt.strip()]
            
            question.strategic_goal = request.form['strategic_goal']
            question.major_cnapp_area = request.form['major_cnapp_area']
            question.text = request.form['text']
            question.options = options
            question.weighting_score = request.form['weighting_score']
            question.order = int(request.form['order'])
            
            db.session.commit()
            flash('Question updated successfully!', 'success')
            return redirect(url_for('routes.admin_questions'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating question: {str(e)}")
            flash('Failed to update question. Please try again.', 'error')
    
    return render_template('admin/question_form.html', question=question)

@routes.route('/admin/questions/<int:question_id>/delete', methods=['POST'])
@login_required
def admin_delete_question(question_id):
    question = Question.query.get_or_404(question_id)
    try:
        db.session.delete(question)
        db.session.commit()
        flash('Question deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting question: {str(e)}")
        flash('Failed to delete question. Please try again.', 'error')
    return redirect(url_for('routes.admin_questions'))