import os
from flask import Flask, render_template
from flask_login import login_required, current_user
from extensions import db, login_manager
import google_auth
from google_drive import GoogleDriveService

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-key-for-testing')

    # Database configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'google_auth.login'

    # Register blueprints
    app.register_blueprint(google_auth.google_auth)

    # Routes
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return render_template('questionnaire.html')
        return render_template('index.html')

    @app.route('/setup')
    @login_required
    def setup():
        return render_template('setup.html')

    @app.route('/questionnaire')
    @login_required
    def questionnaire():
        return render_template('questionnaire.html')

    # Create all database tables
    with app.app_context():
        db.create_all()

    return app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
