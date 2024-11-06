from models import Question, User, db
import logging
from sqlalchemy import text

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clear_and_init_db():
    try:
        # First drop schema and recreate it
        with db.engine.connect() as conn:
            conn.execute(text('DROP SCHEMA IF EXISTS public CASCADE;'))
            conn.execute(text('CREATE SCHEMA public;'))
            conn.execute(text('GRANT ALL ON SCHEMA public TO public;'))
            conn.commit()

        # Create all tables first
        db.create_all()
        db.session.commit()

        # Verify tables are created before proceeding
        with db.engine.connect() as conn:
            result = conn.execute(text('''
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'question'
                );
            '''))
            if not result.scalar():
                raise Exception("Tables were not created properly")

        # Initialize strategic goals question
        strategic_question = Question(
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
        db.session.commit()

        # Get strategic ID for child questions
        strategic_id = strategic_question.id

        # Initialize remaining questions
        from app import parse_csv_questions
        questions_by_goal = parse_csv_questions()
        order = 2

        for goal, questions in questions_by_goal.items():
            for q_data in questions:
                try:
                    question = Question(
                        text=q_data['text'],
                        question_type='multiple_choice',
                        options=[{
                            'title': opt.strip(),
                            'description': '',
                            'icon': 'check-circle'
                        } for opt in q_data['options']],
                        required=True,
                        validation_rules={'min_count': 1, 'max_count': 1},
                        parent_question_id=strategic_id,
                        parent_answer=goal,
                        order=order
                    )
                    db.session.add(question)
                    order += 1
                except Exception as e:
                    logger.error(f"Error adding question: {str(e)}")
                    db.session.rollback()
                    raise

            # Commit after each goal's questions
            db.session.commit()

        logger.info("Database initialized successfully!")

    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        db.session.rollback()
        raise

if __name__ == '__main__':
    from app import create_app
    app = create_app()
    with app.app_context():
        clear_and_init_db()
