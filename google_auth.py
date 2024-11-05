import json
import os
import requests
import logging
from flask import Blueprint, redirect, request, url_for, flash, render_template, current_app
from flask_login import login_required, login_user, logout_user, current_user
from oauthlib.oauth2 import WebApplicationClient, OAuth2Error
from extensions import db
from models import User

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GOOGLE_CLIENT_ID = os.environ["GOOGLE_OAUTH_CLIENT_ID"]
GOOGLE_CLIENT_SECRET = os.environ["GOOGLE_OAUTH_CLIENT_SECRET"]
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

# Use exact URL from logs
REDIRECT_URL = 'https://8767fe56-c668-4fa2-9723-292ada26865d-00-2p1xk2p8ugpyl.kirk.replit.dev/google_login/callback'

REQUIRED_SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/documents"
]

logger.info(f"""To make Google authentication work:
1. Go to https://console.cloud.google.com/apis/credentials
2. Create a new OAuth 2.0 Client ID
3. Add {REDIRECT_URL} to Authorized redirect URIs

For detailed instructions, see:
https://docs.replit.com/additional-resources/google-auth-in-flask#set-up-your-oauth-app--client
""")

client = WebApplicationClient(GOOGLE_CLIENT_ID)
google_auth = Blueprint("google_auth", __name__)

def log_oauth_error(error, context=""):
    """Helper function to log OAuth errors with context"""
    error_details = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        'context': context
    }
    if hasattr(error, 'response'):
        try:
            error_details['response'] = error.response.json()
        except:
            error_details['response'] = error.response.text if error.response else 'No response body'
        error_details['status_code'] = error.response.status_code if error.response else 'No status code'
    
    logger.error(f"OAuth Error: {json.dumps(error_details, indent=2)}")
    return error_details

@google_auth.route("/google_login")
def login():
    try:
        logger.info("Initiating Google OAuth login process")
        logger.debug(f"Using redirect URI: {REDIRECT_URL}")
        logger.debug(f"Requesting scopes: {', '.join(REQUIRED_SCOPES)}")

        google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
        authorization_endpoint = google_provider_cfg["authorization_endpoint"]

        request_uri = client.prepare_request_uri(
            authorization_endpoint,
            redirect_uri=REDIRECT_URL,
            scope=REQUIRED_SCOPES,
        )
        logger.info("Redirecting to Google authorization endpoint")
        return redirect(request_uri)

    except OAuth2Error as e:
        error_details = log_oauth_error(e, "OAuth configuration error during login")
        flash("Authentication configuration error. Please try again later.", "error")
        if current_app.debug:
            flash(f"Debug: {error_details}", "error")
        return redirect(url_for("index"))

    except requests.exceptions.RequestException as e:
        error_details = log_oauth_error(e, "Failed to connect to Google Discovery URL")
        flash("Unable to connect to authentication service. Please try again later.", "error")
        if current_app.debug:
            flash(f"Debug: {error_details}", "error")
        return redirect(url_for("index"))

    except Exception as e:
        error_details = log_oauth_error(e, "Unexpected error during login initiation")
        flash("An unexpected error occurred. Please try again.", "error")
        if current_app.debug:
            flash(f"Debug: {error_details}", "error")
        return redirect(url_for("index"))

@google_auth.route("/google_login/callback")
def callback():
    try:
        code = request.args.get("code")
        if not code:
            logger.error("No authorization code received in callback")
            flash("Authentication failed: No authorization code received", "error")
            return redirect(url_for("index"))

        logger.info("Received authorization code, preparing token request")
        logger.debug(f"Callback URL: {request.url}")
        logger.debug(f"Using redirect URI for token request: {REDIRECT_URL}")

        google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
        token_endpoint = google_provider_cfg["token_endpoint"]

        token_url, headers, body = client.prepare_token_request(
            token_endpoint,
            authorization_response=request.url,
            redirect_url=REDIRECT_URL,
            code=code,
        )
        
        logger.info("Sending token request to Google")
        logger.debug(f"Token request details - URL: {token_url}, Headers: {headers}")
        
        token_response = requests.post(
            token_url,
            headers=headers,
            data=body,
            auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
        )

        if not token_response.ok:
            error_details = log_oauth_error(token_response, "Token request failed")
            flash(f"Authentication failed: {token_response.reason}", "error")
            if current_app.debug:
                flash(f"Debug: Token error - {error_details}", "error")
            return redirect(url_for("index"))

        logger.info("Successfully received token response")
        token_data = token_response.json()
        logger.debug(f"Received token response with keys: {', '.join(token_data.keys())}")
        
        client.parse_request_body_response(json.dumps(token_data))

        logger.info("Fetching user information")
        userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
        uri, headers, body = client.add_token(userinfo_endpoint)
        logger.debug(f"User info request - URI: {uri}")
        
        userinfo_response = requests.get(uri, headers=headers, data=body)

        if not userinfo_response.ok:
            error_details = log_oauth_error(userinfo_response, "Failed to get user info")
            flash("Failed to get user information", "error")
            if current_app.debug:
                flash(f"Debug: User info error - {error_details}", "error")
            return redirect(url_for("index"))

        userinfo = userinfo_response.json()
        if not userinfo.get("email_verified"):
            logger.error(f"Email not verified for user: {userinfo.get('email')}")
            flash("Authentication failed: Email not verified by Google", "error")
            return redirect(url_for("index"))

        users_email = userinfo["email"]
        users_name = userinfo.get("given_name", users_email.split("@")[0])

        logger.info(f"Creating/updating user: {users_email}")
        user = User.query.filter_by(email=users_email).first()
        if not user:
            user = User(username=users_name, email=users_email)
            db.session.add(user)
            db.session.commit()
            logger.info(f"Created new user: {users_email}")

        login_user(user)
        logger.info(f"User logged in successfully: {users_email}")
        
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        return redirect(url_for("index"))

    except OAuth2Error as e:
        error_details = log_oauth_error(e, "OAuth protocol error during callback")
        flash("Authentication protocol error. Please try again.", "error")
        if current_app.debug:
            flash(f"Debug: {error_details}", "error")
        return redirect(url_for("index"))

    except requests.exceptions.RequestException as e:
        error_details = log_oauth_error(e, "Network error during authentication")
        flash("Network error during authentication. Please try again.", "error")
        if current_app.debug:
            flash(f"Debug: {error_details}", "error")
        return redirect(url_for("index"))

    except Exception as e:
        error_details = log_oauth_error(e, "Unexpected error during authentication")
        flash("An unexpected error occurred during authentication.", "error")
        if current_app.debug:
            flash(f"Debug: {error_details}", "error")
        return redirect(url_for("index"))

@google_auth.route("/logout")
@login_required
def logout():
    logger.info(f"User logging out: {current_user.email if current_user else 'Unknown'}")
    logout_user()
    return redirect(url_for("index"))
