import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import logging

logger = logging.getLogger(__name__)

class GoogleDriveService:
    def __init__(self):
        self.SCOPES = ['https://www.googleapis.com/auth/drive.file',
                      'https://www.googleapis.com/auth/documents']

    def get_service(self, credentials):
        try:
            if not credentials:
                raise Exception("No credentials provided")

            # Create credentials object from the token
            creds = Credentials(
                token=credentials,
                scopes=self.SCOPES,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=os.environ.get('GOOGLE_OAUTH_CLIENT_ID'),
                client_secret=os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET')
            )
            
            # Build services with explicit project ID
            project_id = os.environ.get('GOOGLE_CLOUD_PROJECT')
            if not project_id:
                raise Exception("GOOGLE_CLOUD_PROJECT environment variable not set")
                
            drive_service = build('drive', 'v3', credentials=creds, 
                                quota_project_id=project_id)
            docs_service = build('docs', 'v1', credentials=creds,
                               quota_project_id=project_id)
            return drive_service, docs_service
            
        except Exception as e:
            logger.error(f"Error building service: {e}")
            return None, None

    def create_presentation(self, credentials, title, content):
        try:
            if not credentials:
                logger.error("No credentials provided")
                return None
                
            drive_service, docs_service = self.get_service(credentials)
            if not drive_service or not docs_service:
                logger.error("Failed to initialize Google services")
                return None

            # Create a new Google Doc
            doc_metadata = {
                'title': title,
                'mimeType': 'application/vnd.google-apps.document'
            }
            doc = drive_service.files().create(body=doc_metadata).execute()
            
            # Update the document content
            requests = [
                {
                    'insertText': {
                        'location': {
                            'index': 1
                        },
                        'text': content
                    }
                }
            ]
            
            docs_service.documents().batchUpdate(
                documentId=doc['id'],
                body={'requests': requests}
            ).execute()
            
            return doc['id']
            
        except Exception as e:
            logger.error(f"Error creating presentation: {str(e)}")
            return None

    def get_template(self, credentials, template_id):
        try:
            if not credentials:
                logger.error("No credentials provided")
                return None
                
            _, docs_service = self.get_service(credentials)
            if not docs_service:
                logger.error("Failed to initialize Google services")
                return None
                
            document = docs_service.documents().get(documentId=template_id).execute()
            return document
            
        except Exception as e:
            logger.error(f"Error getting template: {str(e)}")
            return None
