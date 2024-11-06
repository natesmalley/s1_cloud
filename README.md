# Cloud Security Roadmap Guide

A web application that helps organizations assess their cloud security maturity through a guided questionnaire system, generating personalized roadmaps based on strategic initiatives.

## Features

- Google OAuth authentication
- Multi-step questionnaire workflow
- Strategic initiative selection (1-3 choices)
- Progress tracking and answer validation
- Administrative interface for content management
- Dark theme UI with responsive design

## Prerequisites

- Python 3.11+
- PostgreSQL database
- Google Cloud Platform account with OAuth 2.0 credentials
- Google Drive API enabled

## Configuration

1. Set up environment variables:
```
GOOGLE_OAUTH_CLIENT_ID=your_client_id
GOOGLE_OAUTH_CLIENT_SECRET=your_client_secret
GOOGLE_CLOUD_PROJECT=your_project_id
DATABASE_URL=your_postgres_url
FLASK_SECRET_KEY=your_secret_key
```

2. Configure OAuth Redirect URI:
- Add `https://cloud-security-assessment.replit.app/google_login/callback` to your Google OAuth authorized redirect URIs

## Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```
3. Initialize the database:
```bash
python init_db.py
```
4. Start the application:
```bash
python app.py
```

## Admin Access

Admin access is granted to:
- @sentinelone.com email domains
- Specific authorized emails:
  - mpsmalls11@gmail.com
  - Jaldevi72@gmail.com
  - m_mcgrail@outlook.com
  - sentinelhowie@gmail.com
  - s1.slappey@gmail.com

## Deployment

The application is deployed on Replit:
- URL: https://cloud-security-assessment.replit.app
- Domain must be added to Google OAuth authorized domains
- Database initialization required on first deployment

## Usage

1. Sign in with Google account
2. Complete security advisor and leader information
3. Select 1-3 strategic initiatives
4. Answer questionnaire for each initiative
5. View assessment results and maturity scores

## License

Copyright (c) 2024 SentinelOne. All rights reserved.
