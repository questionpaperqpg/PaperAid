import os

class Config:
    SECRET_KEY = 'your_secret_key'
    UPLOAD_FOLDER = 'uploads'
    ALLOWED_EXTENSIONS = {'pdf'}
    GOOGLE_API_KEY = "AIzaSyALXXf6wDnSAQIfjKCArIV9BbYlPvqKPIA"
    FIREBASE_CRED_PATH = "/Users/yash/Documents/final year project/b tech project  1 feb/paperaid-6b470-firebase-adminsdk-fbsvc-7fb72c1732.json"
    OUTPUT_DIR = "/Users/yash/Documents/final year project/b tech project  1 feb/question paper"
    UPLOAD_FOLDER_PATH = r'/Users/yash/Documents/final year project/b tech project  1 feb/test'

# firebase_init.py
import firebase_admin
from firebase_admin import credentials, firestore

def initialize_firebase(cred_path):
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)
    return firestore.client()