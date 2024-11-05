import os
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

class GoogleDriveService:
    def __init__(self):
        self.SCOPES = ['https://www.googleapis.com/auth/drive.file',
                      'https://www.googleapis.com/auth/documents']
        self.api_key = os.environ.get('GOOGLE_DRIVE_API_KEY')

    def get_service(self, credentials):
        try:
            drive_service = build('drive', 'v3', credentials=credentials)
            docs_service = build('docs', 'v1', credentials=credentials)
            return drive_service, docs_service
        except Exception as e:
            print(f"Error building service: {e}")
            return None, None

    def create_presentation(self, credentials, title, content):
        drive_service, docs_service = self.get_service(credentials)
        try:
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
        except HttpError as e:
            print(f"Error creating presentation: {e}")
            return None

    def get_template(self, credentials, template_id):
        _, docs_service = self.get_service(credentials)
        try:
            document = docs_service.documents().get(documentId=template_id).execute()
            return document
        except HttpError as e:
            print(f"Error getting template: {e}")
            return None
