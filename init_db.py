from models import Question, User, db
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clear_and_init_db():
    try:
        # Drop all tables using SQLAlchemy models
        db.drop_all()
        db.session.commit()
        
        # Create fresh tables
        db.create_all()
        
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
