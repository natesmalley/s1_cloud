from models import Question, User, db
import logging
from sqlalchemy import text

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_questions():
    """Initialize remaining questions after strategic goals question"""
    from app import parse_csv_questions
    try:
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
        logger.info("Additional questions initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing additional questions: {e}")
        db.session.rollback()
        raise

def clear_and_init_db():
    try:
        # Drop existing tables and recreate schema
        db.session.close()
        db.session.commit()
        
        with db.engine.connect() as conn:
            conn.execute(text('DROP SCHEMA public CASCADE;'))
            conn.execute(text('CREATE SCHEMA public;'))
            conn.commit()
        
        # Create fresh tables
        db.create_all()
        
        # Initialize strategic goals question first
        strategic_question = Question(
            id=1,
            text='Please select your top Business Initiatives in Cloud Security',
            question_type='multiple_choice',
            options=[
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
            required=True,
            validation_rules={'min_count': 1, 'max_count': 3},
            order=1
        )
        db.session.add(strategic_question)
        db.session.commit()  # Commit first question separately
        
        # Then initialize other questions
        init_questions()
        
        logger.info("Database initialized successfully!")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        db.session.rollback()
        raise

if __name__ == '__main__':
    from app import create_app
    app = create_app()
    with app.app_context():
        clear_and_init_db()
