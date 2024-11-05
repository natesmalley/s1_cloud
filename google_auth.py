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

def ensure_https_url(url):
    """Ensure URL uses HTTPS protocol"""
    return url.replace('http://', 'https://', 1)

def log_request_details():
    """Log detailed request information"""
    protocol = request.headers.get('X-Forwarded-Proto', 'unknown')
    details = {
        'url': request.url,
        'base_url': request.base_url,
        'path': request.path,
        'protocol': protocol,
        'args': dict(request.args),
        'headers': dict(request.headers),
        'method': request.method,
    }
    logger.info(f"Request details: {json.dumps(details, indent=2)}")
    return details

client = WebApplicationClient(GOOGLE_CLIENT_ID)
google_auth = Blueprint("google_auth", __name__)

@google_auth.route("/google_login")
def login():
    try:
        # Force HTTPS for the redirect URI
        if request.headers.get('X-Forwarded-Proto') == 'http':
            url = request.url.replace('http://', 'https://', 1)
            return redirect(url)
        
        logger.info("Initiating Google OAuth login process")
        logger.info(f"Protocol: {request.headers.get('X-Forwarded-Proto')}")
        request_details = log_request_details()
        
        google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
        authorization_endpoint = google_provider_cfg["authorization_endpoint"]
        
        request_uri = client.prepare_request_uri(
            authorization_endpoint,
            redirect_uri=REDIRECT_URL,
            scope=REQUIRED_SCOPES,
        )
        
        logger.info(f"Full authorization request URI: {request_uri}")
        return redirect(request_uri)

    except OAuth2Error as e:
        error_details = {
            'error_type': type(e).__name__,
            'error_message': str(e),
            'request_details': log_request_details()
        }
        logger.error(f"OAuth Error Details: {json.dumps(error_details, indent=2)}")
        flash("Authentication failed. Please try again.", "error")
        if current_app.debug:
            flash(f"Debug - OAuth Error: {json.dumps(error_details, indent=2)}", "error")
        return redirect(url_for("index"))

    except Exception as e:
        error_details = {
            'error_type': type(e).__name__,
            'error_message': str(e),
            'request_details': log_request_details()
        }
        logger.error(f"Unexpected Error: {json.dumps(error_details, indent=2)}")
        flash("An unexpected error occurred. Please try again.", "error")
        if current_app.debug:
            flash(f"Debug - Error: {json.dumps(error_details, indent=2)}", "error")
        return redirect(url_for("index"))

@google_auth.route("/google_login/callback")
def callback():
    try:
        # Get the full URL and ensure HTTPS
        callback_url = request.url.replace('http://', 'https://', 1)
        logger.info(f"Received callback at: {callback_url}")
        
        # Extract the code before any other processing
        code = request.args.get("code")
        if not code:
            raise OAuth2Error("Missing authorization code")
        
        # Log request details for debugging
        request_details = log_request_details()
        logger.info(f"Using redirect URI: {REDIRECT_URL}")
        
        # Prepare token request with the HTTPS URL
        google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
        token_endpoint = google_provider_cfg["token_endpoint"]
        
        token_url, headers, body = client.prepare_token_request(
            token_endpoint,
            authorization_response=callback_url,
            redirect_url=REDIRECT_URL,
            code=code
        )

        token_response = requests.post(
            token_url,
            headers=headers,
            data=body,
            auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
        )

        if not token_response.ok:
            error_details = {
                'error_type': 'TokenError',
                'error_message': token_response.text,
                'status_code': token_response.status_code,
                'callback_url': callback_url,
                'request_details': request_details
            }
            logger.error(f"Token Error: {json.dumps(error_details, indent=2)}")
            flash("Failed to obtain access token. Please try again.", "error")
            if current_app.debug:
                flash(f"Debug - Token Error: {json.dumps(error_details, indent=2)}", "error")
            return redirect(url_for("index"))

        client.parse_request_body_response(json.dumps(token_response.json()))
        
        userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
        uri, headers, body = client.add_token(userinfo_endpoint)
        userinfo_response = requests.get(uri, headers=headers)

        if not userinfo_response.ok:
            error_details = {
                'error_type': 'UserInfoError',
                'error_message': userinfo_response.text,
                'status_code': userinfo_response.status_code,
                'callback_url': callback_url,
                'request_details': request_details
            }
            logger.error(f"User Info Error: {json.dumps(error_details, indent=2)}")
            flash("Failed to get user information. Please try again.", "error")
            if current_app.debug:
                flash(f"Debug - User Info Error: {json.dumps(error_details, indent=2)}", "error")
            return redirect(url_for("index"))

        userinfo = userinfo_response.json()
        if not userinfo.get("email_verified"):
            error_details = {
                'error_type': 'EmailNotVerified',
                'email': userinfo.get('email'),
                'callback_url': callback_url,
                'request_details': request_details
            }
            logger.error(f"Email Not Verified: {json.dumps(error_details, indent=2)}")
            flash("Email not verified by Google. Please verify your email first.", "error")
            return redirect(url_for("index"))

        users_email = userinfo["email"]
        users_name = userinfo.get("given_name", users_email.split("@")[0])

        user = User.query.filter_by(email=users_email).first()
        if not user:
            user = User(username=users_name, email=users_email)
            db.session.add(user)
            db.session.commit()

        login_user(user)
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        return redirect(url_for("index"))

    except OAuth2Error as e:
        error_details = {
            'error_type': type(e).__name__,
            'error_message': str(e),
            'callback_url': request.url,
            'https_callback_url': request.url.replace('http://', 'https://', 1),
            'code_present': bool(request.args.get('code')),
            'request_args': dict(request.args)
        }
        logger.error(f"OAuth Error Details: {json.dumps(error_details, indent=2)}")
        flash("Authentication failed. Please try again.", "error")
        if current_app.debug:
            flash(f"Debug - OAuth Error: {json.dumps(error_details, indent=2)}", "error")
        return redirect(url_for("index"))

    except Exception as e:
        error_details = {
            'error_type': type(e).__name__,
            'error_message': str(e),
            'callback_url': request.url,
            'https_callback_url': request.url.replace('http://', 'https://', 1),
            'code_present': bool(request.args.get('code')),
            'request_args': dict(request.args)
        }
        logger.error(f"Unexpected Error: {json.dumps(error_details, indent=2)}")
        flash("An unexpected error occurred. Please try again.", "error")
        if current_app.debug:
            flash(f"Debug - Error: {json.dumps(error_details, indent=2)}", "error")
        return redirect(url_for("index"))

@google_auth.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))
