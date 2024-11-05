import json
import os
import requests
import logging
from flask import Blueprint, redirect, request, url_for, flash, render_template
from flask_login import login_required, login_user, logout_user
from oauthlib.oauth2 import WebApplicationClient
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

logger.info(f"""To make Google authentication work:
1. Go to https://console.cloud.google.com/apis/credentials
2. Create a new OAuth 2.0 Client ID
3. Add {REDIRECT_URL} to Authorized redirect URIs

For detailed instructions, see:
https://docs.replit.com/additional-resources/google-auth-in-flask#set-up-your-oauth-app--client
""")

client = WebApplicationClient(GOOGLE_CLIENT_ID)
google_auth = Blueprint("google_auth", __name__)

@google_auth.route("/google_login")
def login():
    try:
        logger.info("Initiating Google OAuth login process")
        google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
        authorization_endpoint = google_provider_cfg["authorization_endpoint"]

        # Include all required scopes
        request_uri = client.prepare_request_uri(
            authorization_endpoint,
            redirect_uri=REDIRECT_URL,
            scope=[
                "openid", 
                "email", 
                "profile",
                "https://www.googleapis.com/auth/drive.file",
                "https://www.googleapis.com/auth/documents"
            ],
        )
        logger.info(f"Redirecting to Google authorization endpoint")
        return redirect(request_uri)
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to connect to Google Discovery URL: {str(e)}")
        flash("Unable to connect to Google authentication service. Please try again later.", "error")
        return redirect(url_for("index"))
    except Exception as e:
        logger.error(f"Unexpected error during login initiation: {str(e)}")
        flash("An unexpected error occurred. Please try again.", "error")
        return redirect(url_for("index"))

@google_auth.route("/google_login/callback")
def callback():
    try:
        code = request.args.get("code")
        if not code:
            logger.error("No authorization code received in callback")
            flash("Authentication failed: No authorization code received", "error")
            return redirect(url_for("index"))

        logger.info("Received authorization code, fetching token")
        google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
        token_endpoint = google_provider_cfg["token_endpoint"]

        token_url, headers, body = client.prepare_token_request(
            token_endpoint,
            authorization_response=request.url,
            redirect_url=REDIRECT_URL,
            code=code,
        )
        
        logger.info("Requesting access token")
        token_response = requests.post(
            token_url,
            headers=headers,
            data=body,
            auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
        )

        if not token_response.ok:
            logger.error(f"Token request failed: {token_response.status_code} - {token_response.text}")
            flash("Authentication failed: Unable to obtain access token", "error")
            return redirect(url_for("index"))

        client.parse_request_body_response(json.dumps(token_response.json()))

        logger.info("Fetching user information")
        userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
        uri, headers, body = client.add_token(userinfo_endpoint)
        userinfo_response = requests.get(uri, headers=headers, data=body)

        if not userinfo_response.ok:
            logger.error(f"Failed to get user info: {userinfo_response.status_code} - {userinfo_response.text}")
            flash("Authentication failed: Unable to get user info", "error")
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

    except requests.exceptions.RequestException as e:
        logger.error(f"Network error during authentication: {str(e)}")
        flash("Network error during authentication. Please try again.", "error")
        return redirect(url_for("index"))
    except Exception as e:
        logger.error(f"Unexpected error during authentication: {str(e)}")
        flash(f"Authentication error: {str(e)}", "error")
        return redirect(url_for("index"))

@google_auth.route("/logout")
@login_required
def logout():
    logger.info(f"User logging out: {current_user.email if current_user else 'Unknown'}")
    logout_user()
    return redirect(url_for("index"))
