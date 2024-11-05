from extensions import db
from flask_login import UserMixin
from datetime import datetime

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    google_drive_folder = db.Column(db.String(256))
    last_question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=True)
    progress_percentage = db.Column(db.Float, default=0.0)
    
    # Recorder Information
    recorder_name = db.Column(db.String(100))
    recorder_email = db.Column(db.String(120))
    
    # Customer Information
    customer_company = db.Column(db.String(100))
    customer_name = db.Column(db.String(100))
    customer_title = db.Column(db.String(100))
    customer_email = db.Column(db.String(120))
    
    # Setup completion flag
    setup_completed = db.Column(db.Boolean, default=False)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    question_type = db.Column(db.String(50), nullable=False)
    options = db.Column(db.JSON)  # Will store structured options with title, description, and icon
    required = db.Column(db.Boolean, default=True, nullable=False)
    validation_rules = db.Column(db.JSON)  # Will store min_count and max_count for multiple selections
    parent_question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=True)
    parent_answer = db.Column(db.String(500), nullable=True)
    order = db.Column(db.Integer, default=0)

class Response(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    answer = db.Column(db.JSON, nullable=False)  # Changed to JSON to store multiple selections
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_valid = db.Column(db.Boolean, default=True)
    validation_message = db.Column(db.String(200))
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'question_id', name='unique_user_question_response'),
    )

class Presentation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    google_doc_id = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
