from app import create_app
from extensions import db
from models import Question, User, Setup, Response, Presentation
from sqlalchemy import text
import csv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_questions():
    try:
        # Clear existing questions
        Question.query.delete()
        
        # Read CSV and create questions
        with open('questions.csv', 'r') as file:
            reader = csv.DictReader(file)
            order = 0
            for row in reader:
                if not row['Strategic Goal'] or row['Strategic Goal'].startswith('**'):
                    continue
                    
                options = [opt.strip() for opt in row['Multiple Choice Answers'].split(',')]
                
                question = Question(
                    strategic_goal=row['Strategic Goal'].strip(),
                    major_cnapp_area=row['Major CNAPP Area'].strip(),
                    text=row['Guided Questions'],
                    options=options,
                    weighting_score=row['Weighting Score (Maturity)'],
                    order=order
                )
                order += 1
                db.session.add(question)
                logger.info(f"Added question for initiative: {question.strategic_goal}")
        
        db.session.commit()
        logger.info("Successfully initialized all questions")
        
    except Exception as e:
        logger.error(f"Error initializing questions: {e}")
        db.session.rollback()
        raise

def clear_and_init_db():
    try:
        # Drop all tables in the correct order to handle dependencies
        logger.info("Dropping existing tables...")
        db.session.execute(text('DROP TABLE IF EXISTS response CASCADE'))
        db.session.execute(text('DROP TABLE IF EXISTS presentation CASCADE'))
        db.session.execute(text('DROP TABLE IF EXISTS setup CASCADE'))
        db.session.execute(text('DROP TABLE IF EXISTS question CASCADE'))
        db.session.execute(text('DROP TABLE IF EXISTS users CASCADE'))
        db.session.commit()
        logger.info("All tables dropped successfully")
        
        # Create fresh tables in the correct order
        logger.info("Creating tables...")
        db.create_all()
        logger.info("Tables created successfully")
        
        # Verify users table exists
        result = db.session.execute(text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'users')"))
        if not result.scalar():
            raise Exception("Users table was not created properly")
        logger.info("Users table verified")
        
        # Initialize questions
        logger.info("Initializing questions...")
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
