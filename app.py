import os
import logging
from flask import Flask
from flask_login import current_user
from extensions import db, login_manager
import google_auth
from routes import routes
from db_init import clear_and_init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-key-for-testing')
    app.debug = True  # Enable debug mode

    # Database configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'google_auth.login'

    # Register blueprints
    app.register_blueprint(google_auth.google_auth)
    app.register_blueprint(routes)

    return app

def initialize_database(app):
    with app.app_context():
        try:
            # Drop and recreate all tables
            logger.info("Starting database initialization...")
            db.drop_all()
            db.create_all()
            
            # Initialize with seed data
            clear_and_init_db()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise

app = create_app()

if __name__ == '__main__':
    try:
        # Initialize database before running the app
        initialize_database(app)
        app.run(host='0.0.0.0', port=5000)
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
