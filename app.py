import os
from flask import Flask, request, jsonify, redirect, url_for, flash, render_template
from flask_login import current_user
from extensions import db, login_manager
import google_auth
from routes import routes
import logging
from flask_session import Session
import csv
from io import StringIO
from time import time
from datetime import datetime
from init_db import clear_and_init_db
from google_auth import google_auth
import requests
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-key-for-testing')
    app.debug = True

    # Session configuration
    app.config['SESSION_TYPE'] = 'filesystem'
    Session(app)

    # Database configuration
    database_url = os.environ.get('DATABASE_URL')
    if database_url and database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    logger.info(f"Initializing app with database URL pattern: {database_url.split('@')[0].split(':')[0]}://*****@*****")

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'google_auth.login'

    # Register blueprints
    try:
        app.register_blueprint(google_auth)
        app.register_blueprint(routes)
    except Exception as e:
        logger.error(f"Failed to register blueprints: {str(e)}")

    # Define a basic route for the root URL
    @app.route('/')
    def index():
        # Allow unauthenticated users to see landing page
        return render_template('index.html')

    # Add error handling middleware
    @app.errorhandler(404)
    def handle_404_error(error):
        logger.warning(f"404 Not Found: {request.path}")
        return render_template('404.html'), 404

    @app.errorhandler(Exception)
    def handle_error(error):
        logger.error(f"Unhandled error: {str(error)}")
        if request.path.startswith('/api/'):
            return jsonify({'error': str(error)}), 500
        if isinstance(error, Exception):
            return render_template('auth_error.html', error_message=str(error)), 500
        flash("An unexpected error occurred. Please try again.", "error")
        return redirect(url_for("index"))

    # Add performance monitoring middleware
    @app.before_request
    def start_timer():
        request.start_time = time.time()

    @app.after_request
    def log_request(response):
        if request.path.startswith('/static/'):
            return response

        now = time.time()
        duration = round(now - request.start_time, 3)

        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'method': request.method,
            'path': request.path,
            'status': response.status_code,
            'duration': duration,
            'user': current_user.email if not current_user.is_anonymous else None,
            'ip': request.remote_addr
        }

        logger.info(f"Request completed: {log_data}")
        return response

    return app

if __name__ == '__main__':
    for _ in range(3):  # Retry logic to handle temporary failures
        try:
            app = create_app()
            with app.app_context():
                clear_and_init_db()  # Initialize database with fresh data
            app.run(host='0.0.0.0', port=8080)  # Run on port 8080 for Flask
            break
        except requests.RequestException as e:
            logger.error(f"Failed to start app due to network error: {str(e)}. Retrying...")
            time.sleep(2)
        except Exception as e:
            logger.error(f"Failed to start app: {str(e)}. Retrying...")
            time.sleep(2)
    else:
        logger.critical("Failed to start the app after multiple retries. Exiting.")
