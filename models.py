from extensions import db
from flask_login import UserMixin
from datetime import datetime

class User(UserMixin, db.Model):
    __tablename__ = 'users'  # Change from default 'user' to 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    credentials = db.Column(db.String(2048))  # Store OAuth credentials
    last_question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=True)
    progress_percentage = db.Column(db.Float, default=0.0)

class Setup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # Updated foreign key
    advisor_name = db.Column(db.String(100), nullable=False)
    advisor_email = db.Column(db.String(120), nullable=False)
    leader_name = db.Column(db.String(100), nullable=False)
    leader_email = db.Column(db.String(120), nullable=False, index=True)
    leader_employer = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    strategic_goal = db.Column(db.String(200), nullable=False)
    major_cnapp_area = db.Column(db.String(100), nullable=False)
    text = db.Column(db.String(500), nullable=False)
    options = db.Column(db.JSON)  # Will store multiple choice options
    weighting_score = db.Column(db.String(20))  # Store the maturity score range
    order = db.Column(db.Integer, default=0)

class Response(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    setup_id = db.Column(db.Integer, db.ForeignKey('setup.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    answer = db.Column(db.JSON, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_valid = db.Column(db.Boolean, default=True)
    validation_message = db.Column(db.String(200))
    
    __table_args__ = (
        db.UniqueConstraint('setup_id', 'question_id', name='unique_setup_question_response'),
    )

class Presentation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # Updated foreign key
    google_doc_id = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Initiative(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    order = db.Column(db.Integer, default=0)
