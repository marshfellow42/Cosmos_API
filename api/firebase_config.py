import os
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, db

# Load environment variables from .env
load_dotenv()

# Setup Firebase credentials
cred_info = {
    "type": os.getenv("TYPE"),
    "project_id": os.getenv("PROJECT_ID"),
    "private_key_id": os.getenv("PRIVATE_KEY_ID"),
    "private_key": os.getenv("PRIVATE_KEY").replace("\\n", "\n"),
    "client_email": os.getenv("CLIENT_EMAIL"),
    "client_id": os.getenv("CLIENT_ID"),
    "auth_uri": os.getenv("AUTH_URI"),
    "token_uri": os.getenv("TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("AUTH_PROVIDER_CERT_URL"),
    "client_x509_cert_url": os.getenv("CLIENT_CERT_URL"),
}

# Initialize Firebase app only once
if not firebase_admin._apps:
    cred = credentials.Certificate(cred_info)
    firebase_admin.initialize_app(cred, {"databaseURL": os.getenv("DATABASE_URL")})

# Create database references
ref = db.reference("/")
agenda_ref = ref.child("agendas")
agenda_membros_ref = ref.child("agenda_membros")
