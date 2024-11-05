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
                if not any(row):  # Skip empty rows
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
        db.create_all()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise

def init_questions():
    """Initialize questions in the database"""
    from models import Question
    
    # Only initialize if no questions exist
    if Question.query.count() == 0:
        # First question - Strategic goals selection
        strategic_question = {
            'text': 'Please select your top Business Initiatives in Cloud Security',
            'question_type': 'multiple_choice',
            'options': [
                {
                    'title': 'Cloud Adoption and Business Alignment',
                    'description': 'Ensure cloud adoption supports overall business objectives.',
                    'icon': 'cloud'
                },
                {
                    'title': 'Achieving Key Business Outcomes',
                    'description': 'Drive security practices that directly support business outcomes.',
                    'icon': 'target'
                },
                {
                    'title': 'Maximizing ROI for Cloud Security',
                    'description': 'Evaluate cloud security investments to maximize return on investment.',
                    'icon': 'dollar-sign'
                },
                {
                    'title': 'Integration of Cloud Security with Business Strategy',
                    'description': 'Integrate cloud security practices within broader IT strategies.',
                    'icon': 'git-merge'
                },
                {
                    'title': 'Driving Innovation and Value Delivery',
                    'description': 'Facilitate secure innovation and risk management.',
                    'icon': 'zap'
                },
                {
                    'title': 'Supporting Digital Transformation',
                    'description': 'Support digital transformation initiatives securely.',
                    'icon': 'refresh-cw'
                },
                {
                    'title': 'Balancing Rapid Adoption with Compliance',
                    'description': 'Balance rapid cloud adoption with compliance requirements.',
                    'icon': 'shield'
                }
            ],
            'required': True,
            'validation_rules': {'min_count': 1, 'max_count': 3},
            'order': 1
        }

        try:
            # Add strategic goals question
            q = Question(
                text=strategic_question['text'],
                question_type=strategic_question['question_type'],
                options=strategic_question['options'],
                required=strategic_question.get('required', True),
                validation_rules=strategic_question.get('validation_rules', {}),
                order=strategic_question.get('order', 0)
            )
            db.session.add(q)
            
            # Load and add questions from CSV
            questions_by_goal = parse_csv_questions()
            order = 2  # Start after strategic goals question
            
            for goal, questions in questions_by_goal.items():
                for q_data in questions:
                    options = [
                        {
                            'title': opt.strip(),
                            'description': '',
                            'icon': 'check-circle'
                        } for opt in q_data['options']
                    ]
                    
                    q = Question(
                        text=q_data['text'],
                        question_type='multiple_choice',
                        options=options,
                        required=True,
                        validation_rules={'min_count': 1, 'max_count': 1},
                        parent_question_id=1,  # Strategic goals question ID
                        parent_answer=goal,
                        order=order
                    )
                    db.session.add(q)
                    order += 1
            
            db.session.commit()
            logger.info("Questions initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing questions: {e}")
            db.session.rollback()
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
        init_db_tables()
        init_questions()
    app.run(host='0.0.0.0', port=8080)
