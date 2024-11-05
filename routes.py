from flask import render_template, jsonify, request, redirect, url_for
from flask_login import login_required, current_user
from app import app
from extensions import db
from models import Question, Response, Presentation
from google_drive import GoogleDriveService

google_drive = GoogleDriveService()

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('setup'))
    return render_template('index.html')

@app.route('/setup')
@login_required
def setup():
    return render_template('setup.html')

@app.route('/questionnaire')
@login_required
def questionnaire():
    return render_template('questionnaire.html')

@app.route('/api/questions', methods=['GET'])
@login_required
def get_questions():
    question_id = request.args.get('after_question', type=int)
    if question_id:
        previous_answer = Response.query.filter_by(
            user_id=current_user.id,
            question_id=question_id
        ).first()
        
        questions = Question.query.filter_by(
            parent_question_id=question_id,
            parent_answer=previous_answer.answer if previous_answer else None
        ).all()
    else:
        questions = Question.query.filter_by(parent_question_id=None).limit(7).all()
    
    return jsonify([{
        'id': q.id,
        'text': q.text,
        'type': q.question_type,
        'options': q.options
    } for q in questions])

@app.route('/api/saved-answers', methods=['GET'])
@login_required
def get_saved_answers():
    responses = Response.query.filter_by(user_id=current_user.id).all()
    return jsonify([{
        'question_id': r.question_id,
        'answer': r.answer
    } for r in responses])

@app.route('/api/submit-answer', methods=['POST'])
@login_required
def submit_answer():
    data = request.json
    
    # Validate required fields
    if not data or 'question_id' not in data or 'answer' not in data:
        return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400
    
    # Validate answer is not empty
    if not data['answer'] or not str(data['answer']).strip():
        return jsonify({'status': 'error', 'message': 'Answer cannot be empty'}), 400
    
    # Check if question exists
    question = Question.query.get(data['question_id'])
    if not question:
        return jsonify({'status': 'error', 'message': 'Question not found'}), 404
    
    # Update existing response or create new one
    response = Response.query.filter_by(
        user_id=current_user.id,
        question_id=data['question_id']
    ).first()
    
    if response:
        response.answer = data['answer']
    else:
        response = Response(
            user_id=current_user.id,
            question_id=data['question_id'],
            answer=data['answer']
        )
        db.session.add(response)
    
    try:
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/generate-roadmap', methods=['POST'])
@login_required
def generate_roadmap():
    # Verify all questions are answered
    questions = Question.query.all()
    responses = Response.query.filter_by(user_id=current_user.id).all()
    answered_questions = {r.question_id for r in responses}
    
    missing_questions = [q.id for q in questions if q.id not in answered_questions]
    if missing_questions:
        return jsonify({
            'status': 'error',
            'message': 'Please answer all questions before generating the roadmap'
        }), 400
    
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
    
    return jsonify({'status': 'error', 'message': 'Failed to create presentation'})

def generate_roadmap_content(responses):
    content = "# Strategic Roadmap\n\n"
    content += "## Executive Summary\n"
    # Add more sections based on responses
    return content
