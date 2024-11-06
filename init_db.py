from app import create_app
from extensions import db
from models import Question
import csv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_questions():
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
                strategic_goal=row['Strategic Goal'],
                major_cnapp_area=row['Major CNAPP Area'],
                text=row['Guided Questions'],
                options=options,
                weighting_score=row['Weighting Score (Maturity)'],
                order=order
            )
            order += 1
            db.session.add(question)
    
    db.session.commit()

def clear_and_init_db():
    try:
        # Drop tables in correct order to handle dependencies
        for table in reversed(db.metadata.sorted_tables):
            logger.info(f"Dropping table: {table.name}")
            table.drop(db.engine, checkfirst=True)
        
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
