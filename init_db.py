from app import create_app
from extensions import db
from models import Question
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_questions():
    questions = [
        {
            'text': 'What is your organization\'s primary business domain?',
            'question_type': 'multiple_choice',
            'options': ['Technology', 'Healthcare', 'Finance', 'Education', 'Other'],
            'required': True,
            'order': 1
        },
        {
            'text': 'What are your main business objectives for the next year?',
            'question_type': 'text',
            'required': True,
            'validation_rules': {'min_length': 50},
            'order': 2
        },
        {
            'text': 'How many employees does your organization have?',
            'question_type': 'multiple_choice',
            'options': ['1-10', '11-50', '51-200', '201-1000', '1000+'],
            'required': True,
            'order': 3
        },
        {
            'text': 'What is your current technology stack?',
            'question_type': 'text',
            'required': False,
            'validation_rules': {'min_length': 20},
            'order': 4
        },
        {
            'text': 'What are your biggest challenges right now?',
            'question_type': 'text',
            'required': True,
            'validation_rules': {'min_length': 100},
            'order': 5
        }
    ]

    try:
        for q_data in questions:
            q = Question.query.filter_by(text=q_data['text']).first()
            if not q:
                q = Question(
                    text=q_data['text'],
                    question_type=q_data['question_type'],
                    options=q_data.get('options'),
                    required=q_data.get('required', True),
                    validation_rules=q_data.get('validation_rules'),
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
    # Drop tables in correct order
    try:
        # Drop tables in reverse dependency order
        db.session.execute('DROP TABLE IF EXISTS response CASCADE')
        db.session.execute('DROP TABLE IF EXISTS presentation CASCADE')
        db.session.execute('DROP TABLE IF EXISTS question CASCADE')
        db.session.execute('DROP TABLE IF EXISTS "user" CASCADE')
        # Drop sequences
        db.session.execute('DROP SEQUENCE IF EXISTS question_id_seq CASCADE')
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
