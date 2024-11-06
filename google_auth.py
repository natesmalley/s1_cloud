import json
import os
import requests
import logging
from flask import Blueprint, redirect, request, url_for, flash, render_template, current_app, jsonify
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

# IMPORTANT: DO NOT MODIFY THIS URL - Replit handles port forwarding internally
REDIRECT_URL = 'https://8767fe56-c668-4fa2-9723-292ada26865d-00-2p1xk2p8ugpyl.kirk.replit.dev/google_login/callback'

REQUIRED_SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/documents"
]

client = WebApplicationClient(GOOGLE_CLIENT_ID)
google_auth = Blueprint("google_auth", __name__)

@google_auth.route("/google_login")
def login():
    try:
        logger.info("Initiating Google OAuth login process")
        logger.warning("DO NOT modify the redirect URL - it must match Google OAuth settings exactly")
        
        google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
        authorization_endpoint = google_provider_cfg["authorization_endpoint"]
        
        request_uri = client.prepare_request_uri(
            authorization_endpoint,
            redirect_uri=REDIRECT_URL,
            scope=REQUIRED_SCOPES,
        )
        
        logger.info(f"Authorization request URI: {request_uri}")
        return redirect(request_uri)
    except Exception as e:
        logger.error(f"Error in login: {str(e)}")
        flash("Authentication failed. Please try again.", "error")
        return redirect(url_for("routes.index"))

@google_auth.route("/google_login/callback", methods=['GET'])
def callback():
    try:
        # Log full URL and parameters for debugging
        logger.info(f"Full callback URL: {request.url}")
        logger.info(f"URL parameters: {request.args}")
        logger.info(f"Headers: {request.headers}")
        
        code = request.args.get("code")
        if not code:
            logger.error("No authorization code received")
            flash("Authentication failed - no code received", "error")
            return redirect(url_for("routes.index"))

        # Get token info with detailed logging
        try:
            google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
            token_endpoint = google_provider_cfg["token_endpoint"]
            logger.info(f"Token endpoint: {token_endpoint}")
            
            token_url, headers, body = client.prepare_token_request(
                token_endpoint,
                authorization_response=request.url,
                redirect_uri=REDIRECT_URL,
                code=code
            )
            logger.info(f"Prepared token request URL: {token_url}")
            
            # Make token request with longer timeout
            token_response = requests.post(
                token_url,
                headers=headers,
                data=body,
                auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
                timeout=30  # Increased timeout
            )
            
            if not token_response.ok:
                logger.error(f"Token request failed: {token_response.text}")
                return jsonify({
                    'error': 'token_request_failed',
                    'details': token_response.text
                }), 400
            
            # Parse and log token response
            token_data = token_response.json()
            logger.info("Token response received successfully")
            client.parse_request_body_response(json.dumps(token_data))
            
        except requests.exceptions.Timeout:
            logger.error("Token request timed out")
            flash("Authentication timed out. Please try again.", "error")
            return redirect(url_for("routes.index"))
        except Exception as e:
            logger.error(f"Token request error: {str(e)}")
            flash("Authentication failed. Please try again.", "error")
            return redirect(url_for("routes.index"))
        
        # Get user info with error handling and logging
        try:
            userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
            logger.info(f"User info endpoint: {userinfo_endpoint}")
            
            uri, headers, body = client.add_token(userinfo_endpoint)
            logger.info(f"Prepared user info request URL: {uri}")
            
            userinfo_response = requests.get(uri, headers=headers, timeout=30)
            
            if not userinfo_response.ok:
                logger.error(f"User info request failed: {userinfo_response.text}")
                return jsonify({
                    'error': 'userinfo_request_failed',
                    'details': userinfo_response.text
                }), 400
                
            userinfo = userinfo_response.json()
            logger.info("User info received successfully")
            
        except requests.exceptions.Timeout:
            logger.error("User info request timed out")
            flash("Authentication timed out. Please try again.", "error")
            return redirect(url_for("routes.index"))
        except Exception as e:
            logger.error(f"User info request error: {str(e)}")
            flash("Failed to get user information", "error")
            return redirect(url_for("routes.index"))
            
        # Create or update user with error handling
        try:
            user = User.query.filter_by(email=userinfo["email"]).first()
            if not user:
                logger.info(f"Creating new user account for email: {userinfo['email']}")
                user = User(
                    username=userinfo.get("name", userinfo["email"]),
                    email=userinfo["email"]
                )
                db.session.add(user)
                db.session.commit()
                logger.info("New user account created successfully")
            else:
                logger.info(f"Existing user found for email: {userinfo['email']}")
            
            login_user(user)
            logger.info(f"User logged in successfully: {user.email}")
            
            if user.setup_completed:
                return redirect(url_for('routes.questionnaire'))
            return redirect(url_for('routes.setup'))
            
        except Exception as e:
            logger.error(f"Database error: {e}")
            db.session.rollback()
            return jsonify({
                'error': 'database_error',
                'details': str(e)
            }), 500

    except Exception as e:
        logger.error(f"Unhandled error in callback: {e}")
        return jsonify({'error': str(e)}), 500

@google_auth.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("routes.index"))
