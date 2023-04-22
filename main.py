import os
import json
import jinja2
from flask import Flask, request, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

app = Flask(__name__)

# Replace the following values with your own credentials and the desired folder ID
SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/documents']
SERVICE_ACCOUNT_FILE = 'path to credentials here.json'
FOLDER_ID = 'last string of folder url here'

# Authenticate using service account credentials
creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

drive_service = build('drive', 'v3', credentials=creds)

def process_text(text):
    tokens = text.split()
    command = tokens[0].lower()
    doc_name = tokens[1]
    text_to_add = " ".join(tokens[2:])
    return command, doc_name, text_to_add

# Add the get_items_in_folder function
def get_items_in_folder(folder_id):
    query = f"'{folder_id}' in parents"
    results = drive_service.files().list(q=query, fields="nextPageToken, files(id, name)").execute()
    items = results.get("files", [])
    return items

# Get items from the specified folder
items = get_items_in_folder(FOLDER_ID)

@app.route('/.well-known/ai-plugin.json')
def ai_plugin():
    return jsonify({
        "name": "DocsWriter",
        "description": "A ChatGPT plugin that allows you to create and edit Google Docs",
        "url": "https://docswriter.yourusername.repl.co",
        "endpoints": [
            {
                "name": "Modify Document",
                "url": "/modify",
                "method": "POST",
                "input": {"text": "string"},
                "output": {"message": "string"}
            }
        ]
    })

@app.route('/.well-known/openapi.yaml')
def openapi():
    return '''
openapi: 3.0.0
info:
  title: DocsWriter
  description: A ChatGPT plugin that allows you to create and edit Google Docs
  version: 1.0.0
servers:
  - url: https://docswriter.yourusername.repl.co
paths:
  /modify:
    post:
      description: Modify the specified document
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                text:
                  type: string
      responses:
        '200':
          description: Modification successful
          content:
            application/json:
              schema:
                type: object
                properties:
                  message:
                    type: string
'''


@app.route('/modify', methods=['POST'])
def modify_document():
    try:
        text = request.json['text']
        command, doc_name, text_to_add = process_text(text)

        if command == "create":
            doc_metadata = {'name': doc_name, 'parents': [FOLDER_ID],
                            'mimeType': 'application/vnd.google-apps.document'}
            doc = drive_service.files().create(body=doc_metadata).execute()
            doc_id = doc['id']
            return jsonify({"message": f"{doc_name} has been created in the specified folder."})

        elif command == "edit":
            doc_id = None
            for item in items:
                if item['name'] == doc_name:
                    doc_id = item['id']
                    break

            if doc_id:
                docs_service = build('docs', 'v1', credentials=creds)
                requests = [
                    {
                        'insertText': {
                            'location': {
                                'index': 1
                            },
                            'text': text_to_add
                        }
                    }
                ]
                result = docs_service.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute()
                return jsonify({"message": f"Added the text '{text_to_add}' to the document {doc_name}."})
            else:
                return jsonify({"message": f"Document {doc_name} not found in the specified folder."})

        else:
            return jsonify({
                               "message": "Invalid command. Please use 'Create a new document' or 'Edit' followed by the document name and the text to add."})

    except HttpError as error:
        print(f"An error occurred: {error}")
        return jsonify({"message": "An error occurred while processing your request. Please try again."})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)
