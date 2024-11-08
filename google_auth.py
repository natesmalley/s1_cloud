import json
import os
import requests
import logging
from flask import Blueprint, redirect, request, url_for, flash, render_template, current_app
from flask_login import login_required, login_user, logout_user, current_user
from oauthlib.oauth2 import WebApplicationClient, OAuth2Error
from extensions import db, get_db
from models import User
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs
from time import sleep
from sqlalchemy.exc import OperationalError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

google_auth = Blueprint('google_auth', __name__)

# OAuth 2 client setup
GOOGLE_CLIENT_ID = os.environ["GOOGLE_OAUTH_CLIENT_ID"]
GOOGLE_CLIENT_SECRET = os.environ["GOOGLE_OAUTH_CLIENT_SECRET"]
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

REQUIRED_SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/documents"
]

def get_db_session():
    try:
        return get_db()
    except Exception as e:
        logger.error(f"Error getting DB session: {e}")
        return db.session

def get_redirect_url():
    # Production URL
    prod_url = "https://cloud-security-assessment.replit.app/google_login/callback"
    
    # Development URL - for local testing
    dev_url = "https://8767fe56-c668-4fa2-9723-292ada26865d-00-2p1xk2p8ugpyl.kirk.replit.dev/google_login/callback"
    
    # Check if we're in production environment
    is_production = os.environ.get('REPL_SLUG') == 'cloud-security-assessment'
    return prod_url if is_production else dev_url

def sanitize_callback_url(url):
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query, keep_blank_values=True)
    filtered_params = {k: v for k, v in query_params.items() if k != 'state'}
    sanitized_query = urlencode(filtered_params, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, sanitized_query, parsed.fragment))

# OAuth 2 client setup
client = WebApplicationClient(GOOGLE_CLIENT_ID)

def get_google_provider_cfg():
    try:
        return requests.get(GOOGLE_DISCOVERY_URL).json()
    except Exception as e:
        logger.error(f"Error getting Google provider config: {e}")
        return None

@google_auth.route("/google_login")
def login():
    try:
        # Find out what URL to hit for Google login
        google_provider_cfg = get_google_provider_cfg()
        if not google_provider_cfg:
            flash("Error fetching Google configuration.", "error")
            return redirect(url_for("routes.index"))
            
        authorization_endpoint = google_provider_cfg["authorization_endpoint"]
        redirect_uri = get_redirect_url()
        logger.info(f"Using redirect URI: {redirect_uri}")

        # Use library to construct the request for Google login
        request_uri = client.prepare_request_uri(
            authorization_endpoint,
            redirect_uri=redirect_uri,
            scope=REQUIRED_SCOPES
        )
        logger.info(f"Full authorization request URI: {request_uri}")
        return redirect(request_uri)
        
    except Exception as e:
        logger.error(f"Error in login route: {e}")
        flash("An error occurred during login. Please try again.", "error")
        return redirect(url_for("routes.index"))

@google_auth.route("/google_login/callback")
def callback():
    try:
        # Get authorization code Google sent back
        code = request.args.get("code")
        if not code:
            flash("Error: No authorization code received", "error")
            return redirect(url_for("routes.index"))

        # Find out what URL to hit to get tokens
        google_provider_cfg = get_google_provider_cfg()
        if not google_provider_cfg:
            flash("Error fetching Google configuration.", "error")
            return redirect(url_for("routes.index"))

        token_endpoint = google_provider_cfg["token_endpoint"]
        redirect_uri = get_redirect_url()
        logger.info(f"Callback using redirect URI: {redirect_uri}")

        # Get the full callback URL
        callback_url = request.url
        if callback_url.startswith('http://'):
            callback_url = 'https://' + callback_url[7:]
        
        # Prepare token request
        token_url, headers, body = client.prepare_token_request(
            token_endpoint,
            authorization_response=callback_url,
            redirect_url=redirect_uri,
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
        userinfo_response = requests.get(uri, headers=headers, data=body)
        
        if not userinfo_response.ok:
            flash("Failed to get user info from Google.", "error")
            return redirect(url_for("routes.index"))

        userinfo = userinfo_response.json()
        if not userinfo.get("email_verified"):
            flash("Google account email not verified.", "error")
            return redirect(url_for("routes.index"))

        users_email = userinfo["email"]
        users_name = userinfo.get("given_name", users_email.split("@")[0])

        # Get database session with fallback
        session = get_db_session()
        user = None
        for _ in range(3):
            try:
                # Try to get existing user
                user = User.query.filter_by(email=users_email).first()
                if not user:
                    # Create a new user
                    user = User(
                        username=users_name,
                        email=users_email,
                        credentials=token_response.text
                    )
                    session.add(user)
                else:
                    # Update existing user's credentials
                    user.credentials = token_response.text
                    
                session.commit()
                break
            except OperationalError:
                session.rollback()
                if _ == 2:  # Last attempt failed
                    raise
                sleep(1)

        # Begin user session
        login_user(user)
        flash(f'Welcome {users_name}!', 'success')
        return redirect(url_for("routes.index"))

    except OAuth2Error as e:
        logger.error(f"OAuth Error: {str(e)}")
        flash("Authentication protocol error. Please check the logs.", "error")
        return redirect(url_for("routes.index"))
    except Exception as e:
        logger.error(f"Error in callback: {str(e)}")
        flash("An error occurred during login. Please try again.", "error")
        return redirect(url_for("routes.index"))

@google_auth.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("routes.index"))
