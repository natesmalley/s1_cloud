import json
import os
import requests
import logging
from flask import Blueprint, redirect, request, url_for, flash, render_template, current_app
from flask_login import login_required, login_user, logout_user, current_user
from oauthlib.oauth2 import WebApplicationClient, OAuth2Error
from extensions import db
from models import User
from urllib.parse import urlencode, urlparse, urlunparse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GOOGLE_CLIENT_ID = os.environ["GOOGLE_OAUTH_CLIENT_ID"]
GOOGLE_CLIENT_SECRET = os.environ["GOOGLE_OAUTH_CLIENT_SECRET"]
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

# Use exact URL as specified
REDIRECT_URL = 'https://8767fe56-c668-4fa2-9723-292ada26865d-00-2p1xk2p8ugpyl.kirk.replit.dev/google_login/callback'

REQUIRED_SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/documents"
]

def strip_query_params(url):
    """Remove query parameters from URL while preserving the path"""
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return base

def log_request_details():
    """Log detailed request information"""
    details = {
        'url': request.url,
        'base_url': request.base_url,
        'path': request.path,
        'args': dict(request.args),
        'headers': dict(request.headers),
        'method': request.method,
    }
    logger.info(f"Request details: {json.dumps(details, indent=2)}")
    return details

def log_oauth_error(error, context="", response=None):
    """Enhanced helper function to log OAuth errors with context"""
    error_details = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        'context': context,
        'request_details': log_request_details(),
        'configured_redirect_uri': REDIRECT_URL,
        'actual_callback_url': request.url if hasattr(request, 'url') else None
    }
    
    if response:
        error_details['response'] = {
            'status_code': response.status_code,
            'headers': dict(response.headers),
            'text': response.text
        }
        try:
            error_details['response']['json'] = response.json()
        except:
            pass
    
    if hasattr(error, 'response'):
        try:
            error_details['error_response'] = {
                'status_code': error.response.status_code,
                'headers': dict(error.response.headers),
                'text': error.response.text
            }
            error_details['error_response']['json'] = error.response.json()
        except:
            pass
    
    logger.error(f"OAuth Error: {json.dumps(error_details, indent=2)}")
    return error_details

client = WebApplicationClient(GOOGLE_CLIENT_ID)
google_auth = Blueprint("google_auth", __name__)

@google_auth.route("/google_login")
def login():
    try:
        logger.info("Initiating Google OAuth login process")
        request_details = log_request_details()
        logger.info(f"Using redirect URI: {REDIRECT_URL}")
        logger.debug(f"Requesting scopes: {', '.join(REQUIRED_SCOPES)}")

        google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
        authorization_endpoint = google_provider_cfg["authorization_endpoint"]

        request_uri = client.prepare_request_uri(
            authorization_endpoint,
            redirect_uri=REDIRECT_URL,
            scope=REQUIRED_SCOPES,
        )
        
        logger.info(f"Redirecting to Google authorization endpoint: {authorization_endpoint}")
        logger.info(f"Full authorization request URI: {request_uri}")
        
        return redirect(request_uri)

    except OAuth2Error as e:
        error_details = log_oauth_error(e, "OAuth configuration error during login")
        flash("Authentication configuration error. Please check the logs.", "error")
        if current_app.debug:
            flash(f"Debug - OAuth Error: {json.dumps(error_details, indent=2)}", "error")
        return redirect(url_for("index"))

    except Exception as e:
        error_details = log_oauth_error(e, "Unexpected error during login initiation")
        flash("An unexpected error occurred. Please check the logs.", "error")
        if current_app.debug:
            flash(f"Debug - Unexpected Error: {json.dumps(error_details, indent=2)}", "error")
        return redirect(url_for("index"))

@google_auth.route("/google_login/callback")
def callback():
    try:
        logger.info(f"Callback received at: {request.url}")
        logger.info(f"Using redirect URI: {REDIRECT_URL}")
        request_details = log_request_details()
        
        # Log comparison of URIs for debugging redirect_uri_mismatch errors
        actual_callback = strip_query_params(request.url)
        logger.info(f"Comparing URIs - Configured: {REDIRECT_URL} vs Actual: {actual_callback}")
        
        code = request.args.get("code")
        if not code:
            error = request.args.get("error")
            if error == "redirect_uri_mismatch":
                error_details = {
                    'error': error,
                    'configured_uri': REDIRECT_URL,
                    'actual_uri': actual_callback,
                    'request_details': request_details
                }
                logger.error(f"Redirect URI mismatch: {json.dumps(error_details, indent=2)}")
                flash("Authentication failed: Redirect URI mismatch. Please check the configuration.", "error")
                if current_app.debug:
                    flash(f"Debug - URI Mismatch: Expected {REDIRECT_URL}, got {actual_callback}", "error")
                return redirect(url_for("index"))
            
            error_details = {
                'error': error,
                'error_description': request.args.get("error_description"),
                'state': request.args.get("state"),
                'request_details': request_details
            }
            logger.error(f"Authorization error: {json.dumps(error_details, indent=2)}")
            flash(f"Authentication failed: {error_details.get('error_description', 'Unknown error')}", "error")
            return redirect(url_for("index"))

        logger.info("Fetching Google provider configuration")
        google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
        token_endpoint = google_provider_cfg["token_endpoint"]

        logger.info("Preparing token request")
        # Use the exact REDIRECT_URL for token request
        token_url, headers, body = client.prepare_token_request(
            token_endpoint,
            authorization_response=request.url,
            redirect_url=REDIRECT_URL,
            code=code
        )
        
        logger.debug(f"Token request details - URL: {token_url}")
        logger.debug(f"Token request headers: {headers}")
        logger.debug(f"Token request body: {body}")

        token_response = requests.post(
            token_url,
            headers=headers,
            data=body,
            auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
        )

        if not token_response.ok:
            error_details = log_oauth_error(
                Exception("Token request failed"),
                "Failed to obtain access token",
                token_response
            )
            flash(f"Authentication failed: {token_response.reason}", "error")
            if current_app.debug:
                flash(f"Debug - Token Error: {json.dumps(error_details, indent=2)}", "error")
            return redirect(url_for("index"))

        logger.info("Successfully received token response")
        client.parse_request_body_response(json.dumps(token_response.json()))

        logger.info("Fetching user information")
        userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
        uri, headers, body = client.add_token(userinfo_endpoint)
        userinfo_response = requests.get(uri, headers=headers)

        if not userinfo_response.ok:
            error_details = log_oauth_error(
                Exception("User info request failed"),
                "Failed to get user info",
                userinfo_response
            )
            flash("Failed to get user information", "error")
            if current_app.debug:
                flash(f"Debug - User Info Error: {json.dumps(error_details, indent=2)}", "error")
            return redirect(url_for("index"))

        userinfo = userinfo_response.json()
        if not userinfo.get("email_verified"):
            logger.error(f"Email not verified: {userinfo.get('email')}")
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
        flash("Authentication protocol error. Please check the logs.", "error")
        if current_app.debug:
            flash(f"Debug - OAuth Error: {json.dumps(error_details, indent=2)}", "error")
        return redirect(url_for("index"))

    except Exception as e:
        error_details = log_oauth_error(e, "Unexpected error during authentication")
        flash("An unexpected error occurred during authentication. Please check the logs.", "error")
        if current_app.debug:
            flash(f"Debug - Unexpected Error: {json.dumps(error_details, indent=2)}", "error")
        return redirect(url_for("index"))

@google_auth.route("/logout")
@login_required
def logout():
    logger.info(f"User logging out: {current_user.email if current_user else 'Unknown'}")
    logout_user()
    return redirect(url_for("index"))
