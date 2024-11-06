import os
import requests
import logging
from flask import Blueprint, redirect, request, url_for, flash, session
from flask_login import login_user, logout_user, login_required
from oauthlib.oauth2 import WebApplicationClient
from extensions import db
from models import User

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

# Create blueprint
google_auth = Blueprint('google_auth', __name__)
client = WebApplicationClient(GOOGLE_CLIENT_ID)

@google_auth.route("/google_login")
def login():
    try:
        # Get discovery URL for Google login
        google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
        authorization_endpoint = google_provider_cfg["authorization_endpoint"]

        # Construct the callback URL with HTTPS
        base_url = request.url_root.replace('http://', 'https://')
        callback_url = base_url.rstrip('/') + '/google_login/callback'
        
        # Log the callback URL for debugging
        logger.info(f"Using callback URL: {callback_url}")

        # Use library to construct the request for login
        request_uri = client.prepare_request_uri(
            authorization_endpoint,
            redirect_uri=callback_url,
            scope=["openid", "email", "profile", "https://www.googleapis.com/auth/drive.file", 
                  "https://www.googleapis.com/auth/documents"]
        )
        return redirect(request_uri)
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        flash("Failed to initiate login. Please try again.", "error")
        return redirect(url_for("routes.index"))

@google_auth.route("/google_login/callback")
def callback():
    try:
        # Get authorization code
        code = request.args.get("code")
        if not code:
            flash("Authentication failed - no code received.", "error")
            return redirect(url_for("routes.index"))

        # Get token endpoint
        google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
        token_endpoint = google_provider_cfg["token_endpoint"]

        # Construct the callback URL with HTTPS
        base_url = request.url_root.replace('http://', 'https://')
        callback_url = base_url.rstrip('/') + '/google_login/callback'

        # Prepare token request
        token_url, headers, body = client.prepare_token_request(
            token_endpoint,
            authorization_response=request.url,
            redirect_url=callback_url,
            code=code
        )
        
        # Get tokens
        token_response = requests.post(
            token_url,
            headers=headers,
            data=body,
            auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
        )

        # Parse the tokens
        client.parse_request_body_response(token_response.text)

        # Get user info from Google
        userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
        uri, headers, body = client.add_token(userinfo_endpoint)
        userinfo_response = requests.get(uri, headers=headers)
        
        if userinfo_response.json().get("email_verified"):
            unique_id = userinfo_response.json()["sub"]
            users_email = userinfo_response.json()["email"]
            users_name = userinfo_response.json()["name"]
            
            # Create or update user
            user = User.query.filter_by(email=users_email).first()
            if not user:
                user = User(
                    username=users_name,
                    email=users_email
                )
                db.session.add(user)
                db.session.commit()

            # Begin user session
            login_user(user)

            # Send user to setup or questionnaire
            if user.setup_completed:
                return redirect(url_for("routes.questionnaire"))
            return redirect(url_for("routes.setup"))
        else:
            flash("Google authentication failed.", "error")
            return redirect(url_for("routes.index"))

    except Exception as e:
        logger.error(f"Callback error: {str(e)}")
        flash("Authentication failed. Please try again.", "error")
        return redirect(url_for("routes.index"))

@google_auth.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("routes.index"))
