from app import create_app
from extensions import db
from models import Question
import logging
from sqlalchemy import text

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_questions():
    questions = [
        {
            'text': 'Please select your top three struggles with cloud adoption and security (select exactly three):',
            'question_type': 'multiple_choice',
            'options': [
                'Aligning cloud adoption with business objectives',
                'Achieving measurable business outcomes through cloud strategy',
                'Evaluating ROI for cloud security initiatives',
                'Integrating cloud security with IT/business strategies',
                'Measuring cloud security impact on innovation',
                'Managing digital transformation initiatives',
                'Balancing rapid adoption with security compliance',
                'Communicating risks to leadership effectively',
                'Ensuring long-term growth and scalability',
                'Managing strategic partnerships and third-party services'
            ],
            'required': True,
            'validation_rules': {'exact_count': 3},
            'order': 1
        },
        {
            'text': 'What is your preferred timeline for addressing these challenges?',
            'question_type': 'multiple_choice',
            'options': ['0-3 months', '3-6 months', '6-12 months', '12+ months'],
            'required': True,
            'order': 2
        },
        {
            'text': 'What is your organization's primary industry?',
            'question_type': 'multiple_choice',
            'options': ['Technology', 'Healthcare', 'Finance', 'Education', 'Other'],
            'required': True,
            'order': 3
        },
        {
            'text': 'Additional Comments or Requirements',
            'question_type': 'text',
            'required': False,
            'validation_rules': {},
            'order': 4
        }
    ]

    try:
        # First clear existing questions
        Question.query.delete()
        db.session.commit()
        
        # Add new questions
        for q_data in questions:
            q = Question(
                text=q_data['text'],
                question_type=q_data['question_type'],
                options=q_data.get('options'),
                required=q_data.get('required', True),
                validation_rules=q_data.get('validation_rules', {}),
                order=q_data.get('order', 0)
            )
            db.session.add(q)
        
        db.session.commit()
        logger.info("Questions initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing questions: {e}")
        db.session.rollback()
        raise

def clear_and_init_db():
    try:
        # Drop tables using SQLAlchemy text()
        db.session.execute(text('DROP TABLE IF EXISTS response CASCADE'))
        db.session.execute(text('DROP TABLE IF EXISTS presentation CASCADE'))
        db.session.execute(text('DROP TABLE IF EXISTS question CASCADE'))
        db.session.execute(text('DROP TABLE IF EXISTS "user" CASCADE'))
        db.session.commit()
        
        # Create fresh tables
        db.create_all()
        # Initialize questions
        init_questions()
        logger.info("Database initialized successfully!")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        db.session.rollback()
        raise

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        clear_and_init_db()
