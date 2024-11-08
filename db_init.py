from extensions import db
from models import Question, User, Setup, Response, Presentation, Initiative
from sqlalchemy import text
import csv
import logging
from sqlalchemy.exc import IntegrityError, ProgrammingError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_initiatives():
    try:
        # Clear existing initiatives
        Initiative.query.delete()
        
        # Read CSV and create unique initiatives
        with open('questions.csv', 'r') as file:
            reader = csv.DictReader(file)
            initiatives = set()
            for row in reader:
                if not row['Strategic Goal'] or row['Strategic Goal'].startswith('**'):
                    continue
                initiatives.add(row['Strategic Goal'].strip())
            
            # Add each unique initiative
            for order, initiative in enumerate(sorted(initiatives)):
                init = Initiative(
                    title=initiative,
                    description=f"Focus on {initiative.lower()} to improve cloud security maturity",
                    order=order
                )
                db.session.add(init)
                logger.info(f"Added initiative: {initiative}")
        
        db.session.commit()
        logger.info("Successfully initialized all initiatives")
        
    except Exception as e:
        logger.error(f"Error initializing initiatives: {e}")
        db.session.rollback()
        raise

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
        # Drop all tables in the correct order
        logger.info("Dropping existing tables...")
        try:
            db.session.execute(text('DROP TABLE IF EXISTS response CASCADE'))
            db.session.execute(text('DROP TABLE IF EXISTS presentation CASCADE'))
            db.session.execute(text('DROP TABLE IF EXISTS setup CASCADE'))
            db.session.execute(text('DROP TABLE IF EXISTS question CASCADE'))
            db.session.execute(text('DROP TABLE IF EXISTS initiative CASCADE'))
            db.session.execute(text('DROP TABLE IF EXISTS users CASCADE'))
            db.session.commit()
            logger.info("All tables dropped successfully")
        except (IntegrityError, ProgrammingError) as e:
            logger.warning(f"Error dropping tables (this is normal for first run): {e}")
            db.session.rollback()
        
        # Create fresh tables
        logger.info("Creating tables...")
        db.create_all()
        logger.info("Tables created successfully")
        
        # Initialize questions and initiatives
        logger.info("Initializing questions...")
        init_questions()
        logger.info("Initializing initiatives...")
        init_initiatives()
        
        logger.info("Database initialized successfully!")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        db.session.rollback()
        raise
