import os
from flask import Flask
from flask_login import current_user
from extensions import db, login_manager
import google_auth
from routes import routes

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

    # Create all database tables
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            print(f"Error creating database tables: {e}")
            # Log the error but don't raise it to prevent app from crashing
            pass

    return app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
