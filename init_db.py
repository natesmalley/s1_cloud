from app import create_app
from extensions import db
from models import Question, User
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_questions():
    questions = [
        {
            'text': 'Please select your top Business Initiatives in Cloud Security',
            'question_type': 'multiple_choice',
            'options': [
                'Cloud Adoption and Business Alignment',
                'Achieving Key Business Outcomes',
                'Maximizing ROI for Cloud Security',
                'Integration of Cloud Security with Business Strategy',
                'Driving Innovation and Value Delivery',
                'Supporting Digital Transformation',
                'Balancing Rapid Adoption with Compliance'
            ],
            'required': True,
            'validation_rules': {'min_count': 1, 'max_count': 3},
            'order': 1
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
                options=q_data['options'],
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
        # Drop all tables using SQLAlchemy models
        db.drop_all()
        db.session.commit()
        
        # Create fresh tables
        db.create_all()
        # Initialize questions
        init_questions()
        
        # Create test user
        test_user = User(
            id=1,
            username="Test User",
            email="test@example.com"
        )
        db.session.add(test_user)
        db.session.commit()
        
        logger.info("Database initialized successfully!")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        db.session.rollback()
        raise

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        clear_and_init_db()
