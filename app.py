import os
from flask import Flask
from flask_login import current_user
from extensions import db, login_manager
import google_auth
from routes import routes
import logging
from flask_session import Session
import csv
from io import StringIO

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def parse_csv_questions():
    """Parse questions from the CSV file"""
    try:
        with open('Pasted-Strategic-Goal-Major-CNAPP-Area-Guided-Questions-Multiple-Choice-Answers-Weighting-Score-Maturity--1730839362295.txt', 'r') as file:
            csv_reader = csv.reader(file)
            next(csv_reader)  # Skip header row
            
            questions_by_goal = {}
            current_goal = None
            
            for row in csv_reader:
                # Skip empty or incomplete rows
                if not row or len(row) < 5:
                    continue
                    
                goal, area, question_text, answers, weighting = row
                
                if goal:  # New strategic goal section
                    current_goal = goal
                    if current_goal not in questions_by_goal:
                        questions_by_goal[current_goal] = []
                
                if question_text and current_goal:
                    # Parse multiple choice answers
                    answer_options = [opt.strip() for opt in answers.split(',')]
                    
                    question_data = {
                        'text': question_text,
                        'area': area,
                        'options': answer_options,
                        'weighting': weighting
                    }
                    questions_by_goal[current_goal].append(question_data)
            
            return questions_by_goal
    except Exception as e:
        logger.error(f"Error parsing CSV questions: {e}")
        return {}

def init_db_tables():
    """Initialize database tables"""
    try:
        db.drop_all()  # Clear existing tables
        db.create_all()  # Create fresh tables
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-key-for-testing')
    app.debug = True

    # Session configuration
    app.config['SESSION_TYPE'] = 'filesystem'
    Session(app)

    # Database configuration
    database_url = os.environ.get('DATABASE_URL')
    if database_url and database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    logger.info(f"Initializing app with database URL pattern: {database_url.split('@')[0].split(':')[0]}://*****@*****")

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'google_auth.login'

    # Register blueprints
    app.register_blueprint(google_auth.google_auth)
    app.register_blueprint(routes)

    return app

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        init_db_tables()  # Initialize with fresh data
    app.run(host='0.0.0.0', port=8080)  # Run on port 8080 consistently
