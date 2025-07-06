from flask import Flask, jsonify, render_template, request, redirect, url_for, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex
from llama_cloud_services import LlamaParse
from langchain_google_genai import GoogleGenerativeAI
from fpdf import FPDF
from sentence_transformers import SentenceTransformer
import numpy as np
import os
import json
import pdfplumber
import webbrowser
from threading import Timer
import firebase_admin
from firebase_admin import credentials, auth, firestore
from functools import wraps
import requests
from datetime import datetime
import PyPDF2
import re
import pdf2image
import google.generativeai as genai
from PIL import ImageEnhance, ImageFilter
import pytesseract
import asyncio
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from concurrent.futures import ThreadPoolExecutor
import questorage
import torch


app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for session management

# ✅ Enable server-side sessions
from flask_session import Session
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)



# Load tokenizer
from transformers import DebertaV2Tokenizer
tokenizer = DebertaV2Tokenizer.from_pretrained("microsoft/deberta-v3-base")

# Register model class for safe unpickling
from transformers.models.deberta_v2.modeling_deberta_v2 import DebertaV2ForSequenceClassification
torch.serialization.add_safe_globals([DebertaV2ForSequenceClassification])

# Now load the saved model (full model)
model2 = torch.load(
    r"btech.pth",
    map_location=torch.device('cpu'),
    weights_only=False  # This is needed since you saved the full model
)







# from google.cloud import firestore

# Initialize Firebase
cred = credentials.Certificate(r"paperaid-51111-firebase-adminsdk-fbsvc-bc96955334.json")
firebase_admin.initialize_app(cred)

# Get Firestore client
db = firestore.client()

llm = GoogleGenerativeAI(model="gemini-1.5-flash", google_api_key="AIzaSyCjfoENTQBcOZsCAJSWAPCfdvx4_q58_Nk")
api_key = "AIzaSyCjfoENTQBcOZsCAJSWAPCfdvx4_q58_Nk"

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for session management

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Home page route
@app.route('/')
def home():
    return render_template('home.html')

# Sign-up route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Check for missing form data
        if not username or not email or not password or not confirm_password:
            return render_template('signup.html', error="All fields are required.")

        # Check if passwords match
        if password != confirm_password:
            return render_template('signup.html', error="Passwords do not match. Please try again.")

        # Validate email format (must contain '.com')
        if not email.endswith(".com"):
            return render_template('signup.html', error="Email must end with '.com'.")

        try:
            # Check if the email already exists in Firebase Authentication
            user_record = auth.get_user_by_email(email)
            if user_record:
                return render_template('signup.html', error="Email already exists. Please log in.")
        except auth.UserNotFoundError:
            pass  # Email does not exist, continue with signup

        try:
            # Create a new user in Firebase Authentication
            user = auth.create_user(
                email=email,
                password=password,
                display_name=username
            )

            # Add user to Firestore
            user_ref = db.collection('users').document(user.uid)
            user_ref.set({
                'username': username,
                'email': email,
                'uid': user.uid
            })

            # Redirect to login after successful signup
            return redirect(url_for('login'))
        except Exception as e:
            return render_template('signup.html', error=f"An error occurred: {e}")

    return render_template('signup.html')

# Login route
FIREBASE_API_KEY = "AIzaSyAmik-sSU3GE05E1fEoGbg5jBz6TjihsXU"  # Replace with your actual Firebase API key

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            return render_template('login.html', error="Please fill out all fields.")

        try:
            # Call Firebase REST API for email/password authentication
            url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
            payload = {
                "email": email,
                "password": password,
                "returnSecureToken": True
            }
            response = requests.post(url, json=payload)
            response_data = response.json()

            if response.status_code == 200:
                # Login successful
                session['user'] = response_data['localId']  # Store the user ID in session
                return redirect(url_for('zeropage'))
            else:
                # Extract the error message from the response
                error_message = response_data.get("error", {}).get("message", "Invalid credentials.")
                return render_template('login.html', error=error_message)
        
        except Exception as e:
            return render_template('login.html', error="An unexpected error occurred. Please try again.")

    return render_template('login.html')

GOOGLE_CLIENT_ID = "938424989902-ncngg9hstpkcddn3n7nu5g2he2dja1o4.apps.googleusercontent.com"  # Replace with your Google Client ID
GOOGLE_CLIENT_SECRET = "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"  # Replace with your Google Client Secret
GOOGLE_REDIRECT_URI = "http://127.0.0.1:5000/google/callback"  # Replace with your redirect URI

# Google Sign-In route
@app.route('/google/login')
def google_login():
    try:
        # Use url_for to generate the redirect URI
        redirect_uri = url_for('google_callback', _external=True)
        print(f"Redirect URI: {redirect_uri}")  # Debug print

        # Construct the Google OAuth URL
        auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={GOOGLE_CLIENT_ID}&"
            f"redirect_uri={GOOGLE_REDIRECT_URI}&"
            f"response_type=code&"
            f"scope=openid email profile&"
            f"access_type=offline"
        )
        print(f"Google Auth URL: {auth_url}")  # Debug print
        return redirect(auth_url)
    except Exception as e:
        print(f"Error in google_login: {e}")  # Error handling
        return f"An error occurred during Google login: {e}", 500


# Google Sign-In callback route
@app.route('/google/callback')
def google_callback():
    print("Google callback triggered.")
    print(f"Request URL: {request.url}") 

    try:
        # Get the authorization code from the query parameters
        code = request.args.get('code')
        print(f"Authorization Code: {code}")
        if not code:
            print("Authorization code not found.")  # Debug print
            return "Authorization code not found.", 400

        print(f"Authorization Code: {code}")  # Debug print

        # Exchange the authorization code for an access token
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }
        print("Requesting access token...")  # Debug print
        token_response = requests.post(token_url, data=token_data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        token_response.raise_for_status()
        token_json = token_response.json()
        print(f"Access Token Response: {token_json}")  # Debug print

        # Use the access token to get user info
        userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
        headers = {"Authorization": f"Bearer {token_json['access_token']}"}
        userinfo_response = requests.get(userinfo_url, headers=headers)
        userinfo_response.raise_for_status()
        userinfo_json = userinfo_response.json()
        print(f"User Info: {userinfo_json}")  # Debug print

        # Create or sign in the user with Firebase Authentication
        email = userinfo_json.get('email')
        display_name = userinfo_json.get('name')
        print(f"Email: {email}, Display Name: {display_name}")  # Debug print

        try:
            user = auth.get_user_by_email(email)
            print(f"User found: {user.uid}")  # Debug print
        except auth.UserNotFoundError:
            # Create a new user if they don't exist
            print("User not found. Creating a new user.")  # Debug print
            user = auth.create_user(
                email=email,
                display_name=display_name,
            )

        # Add user to Firestore
        user_ref = db.collection('users').document(user.uid)
        user_ref.set({
            'username': display_name,
            'email': email,
            'uid': user.uid
        })
        print(f"User added to Firestore: {user.uid}")  # Debug print

        # Store user ID in session
        session['user'] = user.uid
        print("User logged in successfully.")  # Debug print
        return redirect(url_for('zeropage'))

    except Exception as e:
        print(f"Error in google_callback: {e}")  # Debug print
        return f"An error occurred: {e}", 500


# Zero page route (protected)
@app.route('/zeropage', methods=['GET', 'POST'])
@login_required
def zeropage():
    if request.method == 'POST':
        action = request.form['action']
        if action == "generate_question_paper":
            return render_template('firstpage.html')
        elif action == "insert_into_db":
            return render_template('datapage.html')
        
        elif action == 'predict_bt_level':
            return redirect(url_for('render_bt_level_ui'))
            
    return render_template('zeropage.html')




# Logout route
@app.route('/logout')
@login_required
def logout():
    session.pop('user', None)
    return redirect(url_for('home'))

        
@app.route('/view_syllabus', methods=['POST'])
@login_required
def view_syllabus():
    # Get the subject, year, and department from the form data
    subject = request.form.get('subject')
    year = request.form.get('year')
    department = request.form.get('branch')

    if not subject or not year or not department:
        return "Subject, year, or department not provided.", 400

    try:
        # Save form values in session for reuse when returning to secondpage
        session['form_data'] = {
            'subject': subject,
            'year': year,
            'branch': department
        }

        # Query Firestore
        syllabus_ref = db.collection('syllabus').document(year).collection('departments').document(department).collection('subjects').document(subject)
        syllabus_doc = syllabus_ref.get()

        if not syllabus_doc.exists:
            return f"No syllabus found for subject: {subject}", 404

        syllabus_text = syllabus_doc.to_dict().get('syllabus', '')

        # Extract topics and subtopics
        topics_dict = extract_topics_and_subtopics(syllabus_text, subject)

        # Render syllabus view
        return render_template('view_syllabus.html', 
                              subject=subject, 
                              year=year, 
                              department=department, 
                              topics_dict=topics_dict)
    except Exception as e:
        return f"An error occurred: {e}", 500


@app.route('/secondpage', methods=['GET', 'POST'])
@login_required
def secondpage():
    if request.method == 'POST':
        # Save form data to session
        session['form_data'] = {
            'year': request.form.get('year'),
            'branch': request.form.get('branch'),
            'subject': request.form.get('subject')
        }
    else:
        # Read from URL query params or fallback to session
        year = request.args.get('year')
        branch = request.args.get('branch')
        subject = request.args.get('subject')
        
        if not year or not branch or not subject:
            form_data = session.get('form_data')
            if form_data:
                year = form_data.get('year')
                branch = form_data.get('branch')
                subject = form_data.get('subject')

    return render_template('secondpage.html', year=year, branch=branch, subject=subject)



@app.route('/thirdpage', methods=['GET', 'POST'])
@login_required
def thirdpage():
    if request.method == 'POST':
        # Get form data
        year = request.form.get('year')
        subject = request.form.get('subject')
        # Get topics and marks
        topics = request.form.getlist('topic[]')
        marks = list(map(int, request.form.getlist('marks[]')))
        total_marks = sum(marks)
        
        # Get the topic-subtopic mapping from the form
        topic_subtopic_map_json = request.form.get('topic_subtopic_map')
        # Parse the JSON string to get the topic-subtopic map
        topic_subtopic_map = {}
        if topic_subtopic_map_json and topic_subtopic_map_json.strip():
            try:
                topic_subtopic_map = json.loads(topic_subtopic_map_json)
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                print("Error parsing topic_subtopic_map JSON")
                # Process subtopics the old way as fallback
                checked_subtopics = request.form.getlist('subtopics[]')
                subtopics = checked_subtopics if checked_subtopics else []
                # Create a simple mapping using the old data structure
                for topic in topics:
                    topic_subtopic_map[topic] = subtopics
        
        # If the map is empty but we have topics and subtopics, build a simple map
        if not topic_subtopic_map and topics:
            checked_subtopics = request.form.getlist('subtopics[]')
            subtopics = checked_subtopics if checked_subtopics else []
            # Create a simple mapping (all subtopics associated with all topics)
            for topic in topics:
                topic_subtopic_map[topic] = subtopics
        
        # Convert the topic_subtopic_map to a JSON string to safely pass to the template
        topic_subtopic_map_json = json.dumps(topic_subtopic_map)
        
        # Pass data to the third page
        # Convert the topic_subtopic_map to a JSON string to safely pass to the template
        topic_subtopic_map_json = json.dumps(topic_subtopic_map)

        # Store full marking scheme in session
        marking_scheme = list(zip(topics, marks))  # Example: [('Unit 1', 5), ('Unit 2', 10)]
        session['marking_scheme'] = marking_scheme

        # Pass data to the third page
        return render_template('thirdpage.html',
                            year=year,
                            subject=subject,
                            topics=topics,
                            topic_subtopic_map=topic_subtopic_map_json,
                            total_marks=total_marks)

    return redirect(url_for('home'))

    
# Add these helper functions before the generate route

def ensure_collections_exist(subject):
    """Ensure required collections and documents exist in Firebase"""
    print(f"\n=== Starting collection verification for subject: {subject} ===")
    try:
        # Check if llm_questions collection exists and create if not
        llm_questions_ref = db.collection('llm_questions')
        print("✓ Accessed llm_questions collection")
        
        # Check if subject document exists and create if not
        subject_ref = llm_questions_ref.document(subject)
        if not subject_ref.get().exists:
            subject_ref.set({
                'name': subject,
                'created_at': firestore.SERVER_TIMESTAMP
            })
            print(f"✓ Created new subject document: {subject}")
        else:
            print(f"✓ Subject document already exists: {subject}")
        
        return True
    except Exception as e:
        print(f"❌ Error ensuring collections exist: {e}")
        print(f"❌ Failed to verify/create collections for subject: {subject}")
        return False

def get_subject_topics(subject):
    """Get all topics for a given subject from Firebase"""
    print(f"\n=== Retrieving topics for subject: {subject} ===")
    try:
        # Get the topics collection for this subject
        topics_ref = db.collection('llm_questions').document(subject).collections()
        topics = [topic.id for topic in topics_ref]
        
        if topics:
            print(f"✓ Successfully retrieved {len(topics)} topics:")
            for topic in topics:
                print(f"  - {topic}")
        else:
            print("! No existing topics found for this subject")
            
        return topics
    except Exception as e:
        print(f"❌ Error retrieving topics: {e}")
        print("❌ Failed to get topics from Firebase")
        return []

def assign_topic_to_question(question, subject, available_topics):
    """Ask LLM to assign a topic to the question from available topics"""
    print(f"\n=== Assigning topic to question ===")
    print(f"Question: {question[:100]}...")  # Print first 100 chars of question
    print(f"Available topics: {', '.join(available_topics)}")
    
    try:
        prompt = (
            f"Given the following question:\n{question}\n\n"
            f"And these available topics for the subject {subject}:\n{', '.join(available_topics)}\n\n"
            f"Which single topic from the list best matches this question? "
            f"Respond with only the topic name, exactly as it appears in the list."
        )
        
        print("Querying LLM for topic assignment...")
        response = llm.invoke(prompt)
        assigned_topic = response.strip()
        
        if assigned_topic in available_topics:
            print(f"✓ Successfully assigned topic: {assigned_topic}")
            return assigned_topic
        else:
            print(f"! Warning: LLM assigned invalid topic: {assigned_topic}")
            print(f"! Defaulting to first available topic: {available_topics[0]}")
            return available_topics[0]
    except Exception as e:
        print(f"❌ Error during topic assignment: {e}")
        print(f"! Defaulting to first available topic: {available_topics[0]}")
        return available_topics[0]

def store_question_in_firebase(question, subject, topic, subtopic, question_type, bt_level, marks, collection='llm_questions'):
    """
    Store a question in Firebase under the appropriate topic and subtopic.
    """
    print(f"\n=== Storing question in Firebase ({collection}) ===")
    print(f"Subject: {subject}")
    print(f"Topic: {topic}")
    print(f"Subtopic: {subtopic}")
    print(f"Question Type: {question_type}")
    print(f"Bloom's Taxonomy Level: {bt_level}")
    print(f"Marks: {marks}")
    
    try:
        # Create reference path: collection/subject/topics/topic/subtopics/subtopic/questions
        question_ref = (db.collection(collection)
                       .document(subject)
                       .collection('topics')
                       .document(topic)
                       .collection('subtopics')
                       .document(subtopic)
                       .collection('questions')
                       .document())
        
        question_ref.set({
            'text': question,
            'marks': marks,
            
            'bt_level': bt_level,
            'question_type': question_type,
            
            'timestamp': firestore.SERVER_TIMESTAMP
        })
        
        print(f"✓ Successfully stored question in Firebase")
        print(f"✓ Storage location:")
        print(f"  - Collection: {collection}")
        print(f"  - Subject: {subject}")
        print(f"  - Topic: {topic}")
        print(f"  - Subtopic: {subtopic}")
        print(f"  - Document ID: {question_ref.id}")
        return True
    except Exception as e:
        print(f"❌ Error storing question: {e}")
        return False
    

@app.route('/get_topics')
@login_required
def get_topics():
    subject = request.args.get('subject')
    if not subject:
        return jsonify([])
    
    try:
        # Get reference to the subject's topics collection
        topics_ref = db.collection('llm_questions').document(subject).collection('topics')
        topics = [doc.id for doc in topics_ref.stream()]
        return jsonify(sorted(topics))
    except Exception as e:
        print(f"Error retrieving topics: {e}")
        return jsonify([])
device = torch.device("cpu")


@app.route('/predict_bt_level', methods=['POST'])
@login_required
def predict_bt_level_route():
    try:
        # Get the question from the request
        data = request.get_json()
        if not data or 'question' not in data:
            return jsonify({'success': False, 'message': 'No question provided'}), 400

        question = data['question'].strip()
        prompt = (
            f"Convert this type of question\n{question} to short question\n\n"
           
        )
        
        
        question = llm.invoke(prompt)
        if not question:
            return jsonify({'success': False, 'message': 'Question cannot be empty'}), 400

        # Tokenize the question
        inputs = tokenizer(question, return_tensors="pt", truncation=True, padding=True, max_length=64)
        inputs = {key: val.to(device) for key, val in inputs.items()}

        # Predict BT level
        with torch.no_grad():
            outputs = model2(**inputs)
            prediction = torch.argmax(outputs.logits, dim=1).item()

        bt_levels = {0: "BT1", 1: "BT2", 2: "BT3", 3: "BT4", 4: "BT5", 5: "BT6"}
        bt_level = bt_levels.get(prediction, "Unknown")

        return jsonify({'success': True, 'bt_level': bt_level}), 200

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    
@app.route('/get_subtopics')
@login_required
def get_subtopics():
    subject = request.args.get('subject')
    topic = request.args.get('topic')
    if not subject or not topic:
        return jsonify([])
    
    try:
        # Get reference to the topic's subtopics collection
        subtopics_ref = (db.collection('llm_questions')
                        .document(subject)
                        .collection('topics')
                        .document(topic)
                        .collection('subtopics'))
        subtopics = [doc.id for doc in subtopics_ref.stream()]
        return jsonify(sorted(subtopics))
    except Exception as e:
        print(f"Error retrieving subtopics: {e}")
        return jsonify([])
    
@app.route('/save_questions_to_db', methods=['POST'])
@login_required
def save_questions_to_db():
    try:
        # Retrieve the questions data from the session
        questions_data = session.get('questions_data', [])
        
        if not questions_data:
            return jsonify({'success': False, 'message': 'No questions data found in session.'}), 400

        # Get the subject name from the session
        subject = session.get('subject', '')
        if not subject:
            return jsonify({'success': False, 'message': 'Subject not found in session.'}), 400

        # Iterate through each question and save it to Firebase
        for question in questions_data:
            topic = question.get('topic', '')
            subtopic = question.get('subtopic', '')
            question_text = question.get('text', '')
            question_type = question.get('section_info', {}).get('type', '')
            bt_level = question.get('section_info', {}).get('bloom_level', '')
            marks = question.get('marks', 0)

            if not all([topic, subtopic, question_text, question_type, bt_level, marks]):
                print(f"⚠️ Skipping incomplete question: {question}")
                continue

            # Store the question in Firebase under the appropriate topic and subtopic
            success = store_question_in_firebase(
                question=question_text,
                subject=subject,
                topic=topic,
                subtopic=subtopic,
                question_type=question_type,
                bt_level=bt_level,
                marks=marks,
                collection='llm_questions'
            )

            if success:
                print(f"✓ Successfully stored question in Firebase: Topic={topic}, Subtopic={subtopic}")
            else:
                print(f"❌ Failed to store question in Firebase: Topic={topic}, Subtopic={subtopic}")

        return jsonify({'success': True, 'message': 'Questions saved to database successfully!'}), 200

    except Exception as e:
        print(f"❌ Error in save_questions_to_db: {e}")
        return jsonify({'success': False, 'message': f'An error occurred: {str(e)}'}), 500
def fetch_question_from_firebase(subject, topic, subtopic, counter):
    try:
        # Replace spaces with underscores in subject, topic, and subtopic
        

        # Construct the Firestore collection path
        collection_path = f"pyp_questions/{subject}/topics/{topic}/subtopics/{subtopic}/questions"
        print(f"Firestore Collection Path: {collection_path}")

        # Query Firestore for all documents in the collection
        # questions_ref = db.collection(collection_path)
        questions_ref = (
        db.collection('pyp_questions')
       .document(subject)
       .collection('topics')
       .document(topic)
       .collection('subtopics')
       .document(subtopic)
       .collection('questions')
         )

        questions = questions_ref.stream()

        # Convert questions to a list of dictionaries
        question_list = [doc.to_dict() for doc in questions]

        if not question_list:
            print("No questions found in Firestore.")
            return None, counter  # No questions found

        # Check if the counter is within the range of available questions
        if counter < len(question_list):
            # Fetch the question at the counter index
            question_text = question_list[counter].get("text", "No question text found.")
            print(f"Fetched question: {question_text}")
            return question_text, counter + 1  # Increment the counter
        else:
            # No more questions available
            print("Counter exceeded the number of available questions.")
            return None, counter

    except Exception as e:
        print(f"Error fetching question from Firestore: {e}")
        return None, counter
    
@app.route('/regenerate_question', methods=['POST'])
@login_required
def regenerate_question():
    try:
        # Track regeneration count for this question
        regeneration_count = session.get('regeneration_counts', {})
        # Ensure all keys in regeneration_count are strings
        regeneration_count = {str(k): v for k, v in regeneration_count.items()}

        # Get request data
        data = request.get_json()
        question_id = data.get('question_id')
        difficulty = data.get('difficulty')  # Get the difficulty parameter

        # Convert question_id to string to ensure consistent key type in dictionaries
        question_id = str(question_id)

        topic = data.get('topic')
        subtopic = data.get('subtopic')
        marks = data.get('marks')
        question_type = data.get('question_type')
        bloom_level = data.get('bloom_level')
        year = data.get('year')
        subject = data.get('subject')

        # Update regeneration count
        current_count = regeneration_count.get(question_id, 0) + 1
        regeneration_count[question_id] = current_count
        session['regeneration_counts'] = regeneration_count

        if difficulty == 'easy':
            difficulty_adjectives = ["easier", "simpler", "more straightforward", "less challenging"]
            creativity_adjectives = ["", "with a familiar context", "using basic concepts", "with a straightforward scenario"]
            difficulty_index = (current_count - 1) % len(difficulty_adjectives)
            creativity_index = (current_count + 1) % len(creativity_adjectives)
            difficulty_adj = difficulty_adjectives[difficulty_index]
            creativity_adj = creativity_adjectives[creativity_index]

            prompt = (
                f"Generate a single {difficulty_adj} question for the topic '{topic}' and subtopic '{subtopic}' "
                f"in the subject '{subject}' for the year '{year}'. "
                f"The question should be worth {marks} marks. "
                f"Bloom's Taxonomy Level: {bloom_level}. "
                f"Question Type: {question_type}. "
                f"Create a question {creativity_adj} than standard questions. "
                f"IMPORTANT: This is regeneration attempt #{current_count}, so make sure the question is "
                f"COMPLETELY DIFFERENT from previous attempts. "
                f"Question Type: {question_type}. IMPORTANT: The question MUST strictly follow this question type. "
                f"Use different wording, context, scenarios, or application examples. "
                f"Format the question as a complete, well-formed question suitable for an exam. " 
                f"Generate only ONE question. Do not number it or include any additional text."
            )

            print(f"Prompt for easy difficulty: {prompt}")

            # Call LLM with the prompt
            response = llm.invoke(prompt)
            question = response.strip()

        elif difficulty == 'hard':
            difficulty_adjectives = ["harder", "more challenging", "more complex", "significantly more difficult"]
            creativity_adjectives = ["", "more creative", "using a different approach", "with a novel scenario"]
            difficulty_index = (current_count - 1) % len(difficulty_adjectives)
            creativity_index = (current_count + 1) % len(creativity_adjectives)
            difficulty_adj = difficulty_adjectives[difficulty_index]
            creativity_adj = creativity_adjectives[creativity_index]

            prompt = (
                f"Generate a single {difficulty_adj} question for the topic '{topic}' and subtopic '{subtopic}' "
                f"in the subject '{subject}' for the year '{year}'. "
                f"The question should be worth {marks} marks. "
                f"Bloom's Taxonomy Level: {bloom_level}. "
                f"Question Type: {question_type}. "
                f"Create a question {creativity_adj} than standard questions. "
                f"IMPORTANT: This is regeneration attempt #{current_count}, so make sure the question is "
                f"COMPLETELY DIFFERENT from previous attempts. "
                f"Question Type: {question_type}. IMPORTANT: The question MUST strictly follow this question type. "
                f"Use different wording, context, scenarios, or application examples. "
                f"Format the question as a complete, well-formed question suitable for an exam. " 
                f"Generate only ONE question. Do not number it or include any additional text."
            )

            print(f"Prompt for hard difficulty: {prompt}")

            # Call LLM with the prompt
            response = llm.invoke(prompt)
            question = response.strip()

        elif difficulty == 'database':
            # Get the current counter for this question from the session
            question_counter = session.get('question_counter', {}).get(question_id, 0)

            # Fetch the next question from Firebase
            question, new_counter = fetch_question_from_firebase(subject, topic, subtopic, 0)

            if not question:
                # If no question is found, return a placeholder message
                question = "No questions in database."

            # Update the counter in the session
            session.setdefault('question_counter', {})
            session['question_counter'][question_id] = new_counter

            print(f"Fetched question from Firebase: {question[:100]}...")

        # Update the question in the session
        questions_data = session.get('questions_data', [])
        for q in questions_data:
            # Convert q['id'] to string for comparison if needed
            q_id = str(q['id']) if not isinstance(q['id'], str) else q['id']
            if q_id == question_id:
                q['text'] = question
                break

        # Save updated questions back to session
        session['questions_data'] = questions_data

        return jsonify({'success': True, 'new_question': question})
    except Exception as e:
        print(f"Error in regenerate_question: {e}")
        return jsonify({'success': False, 'error': str(e)})
        

@app.route('/generate', methods=['POST'])
@login_required
def generate():
    print("\n====== Starting Question Paper Generation ======")
    
    try:
        # Extract form data
        year = request.form['year']
        subject = request.form['subject']
        branch = request.form.get('branch', '')
        question_types = request.form.getlist('question_type[]')
        no_of_questions = list(map(int, request.form.getlist('no_of_questions[]')))
        marks_per_question = list(map(int, request.form.getlist('marks_per_question[]')))
        bloom_levels = request.form.getlist('bloom_level[]')
        
        print(f"\nRequest Parameters:")
        print(f"Year: {year}")
        print(f"Subject: {subject}")
        print(f"Branch: {branch}")
        print(f"Question Types: {question_types}")
        print(f"Number of Questions: {no_of_questions}")
        print(f"Marks per Question: {marks_per_question}")
        print(f"Bloom's Taxonomy Levels: {bloom_levels}")

        # Extract topics and subtopics from the form
        topic_subtopic_map_json = request.form.get('topic_subtopic_map')
        topic_subtopic_map = json.loads(topic_subtopic_map_json) if topic_subtopic_map_json else {}
        
        print(f"\nTopic-Subtopic Map: {topic_subtopic_map}")

        # Extract topics selected for each section
        section_topics = []
        for i in range(len(question_types)):
            section_topic_list = request.form.getlist(f'topic_{i}[]')
            section_topics.append(section_topic_list)
            print(f"Section {i+1} Topics: {section_topic_list}")
        
        # Generate question paper
        final_questions = ""
        print("\n=== Starting Question Generation ===")
        
        # Add header for the question paper
        final_questions += f"{'='*50}\n"
        final_questions += f"{year} {subject} Question Paper\n"
        if branch:
            final_questions += f"Branch: {branch}\n"
        final_questions += f"{'='*50}\n\n"
        
        # Create a list to store each individual question with its section info
        questions_data = []
        # Counter for question numbering
        question_counter = 1

        for i in range(len(question_types)):
            print(f"\nGenerating Section {i+1}")
            print(f"Question Type: {question_types[i]}")
            print(f"Number of Questions: {no_of_questions[i]}")
            print(f"Marks per Question: {marks_per_question[i]}")
            print(f"Bloom's Taxonomy Level: {bloom_levels[i]}")

            # Get topics for this section
            section_topic_list = section_topics[i]
            if not section_topic_list:
                print(f"⚠ Warning: No topics selected for section {i+1}, using all topics")
                section_topic_list = list(topic_subtopic_map.keys())
            
            print(f"Topics for Section {i+1}: {section_topic_list}")

            # Calculate questions per topic for this section
            num_topics = len(section_topic_list)
            questions_per_topic = no_of_questions[i] // num_topics  # Questions per topic
            remaining_questions = no_of_questions[i] % num_topics   # Remaining questions to distribute

            section_text = f"\nSECTION {i + 1}: {question_types[i].upper()} ({no_of_questions[i]} Questions, {marks_per_question[i]} Marks each)\n"
            section_text += f"Bloom's Taxonomy Level: {bloom_levels[i]}\n"
            section_text += f"{'-'*50}\n\n"
            
            # Add section header to final_questions
            final_questions += section_text
            
            # Store section info
            section_info = {
                'number': i + 1,
                'type': question_types[i].upper(),
                'marks': marks_per_question[i],
                'bloom_level': bloom_levels[i]
            }
            
            # Track how many questions we've added to this section
            section_question_count = 0
            
            # Generate questions for each topic in this section
            for j, topic in enumerate(section_topic_list):
                # Calculate the number of questions for this topic
                num_questions_for_topic = questions_per_topic + (1 if j < remaining_questions else 0)
                
                if num_questions_for_topic <= 0:
                    continue  # Skip if no questions are assigned to this topic

                print(f"\nGenerating {num_questions_for_topic} questions for topic: {topic}")
                
                # Get relevant subtopics for this topic
                topic_subtopics = topic_subtopic_map.get(topic, [])
                
                # If no specific subtopics match, use generic ones
                if not topic_subtopics:
                    topic_subtopics = ["General concepts"]
                
                print(f"Subtopics for {topic}: {topic_subtopics}")
                
                # Add topic header to final_questions
                topic_header = f"Topic: {topic}\n"
                final_questions += topic_header
                
                # Distribute questions among subtopics for this topic
                questions_per_subtopic = distribute_questions(num_questions_for_topic, len(topic_subtopics))
                
                print(f"Distribution of {num_questions_for_topic} questions among {len(topic_subtopics)} subtopics: {questions_per_subtopic}")
                
                # Generate questions for each subtopic
                for k, subtopic in enumerate(topic_subtopics):
                    if k < len(questions_per_subtopic) and questions_per_subtopic[k] > 0:
                        num_questions_for_subtopic = questions_per_subtopic[k]
                        
                        # Only add subtopic header if there are questions for it
                        subtopic_header = f"  Subtopic: {subtopic}\n"
                        final_questions += subtopic_header
                        
                        # Fetch marking scheme from session
                        marking_scheme = session.get('marking_scheme', [])
                        marking_line = ""
                        if marking_scheme:
                            scheme_str = ", ".join([f"{t}: {m} marks" for t, m in marking_scheme])
                            marking_line = f"Try to align the generated questions with the following marking scheme: {scheme_str}. "

                        # Construct the prompt
                        prompt = (
                            f"{marking_line}"
                            f"Generate {num_questions_for_subtopic} questions for the topic '{topic}' and subtopic '{subtopic}' "
                            f"in the subject '{subject}' for the year '{year}'. "
                            f"Each question should be worth {marks_per_question[i]} marks. "
                            f"Bloom's Taxonomy Level: {bloom_levels[i]}. "
                            f"Question Type: {question_types[i]}. "
                            f"Format each question as a complete, well-formed question suitable for an exam."
                        )
                        
                        print(f"Querying LLM for {num_questions_for_subtopic} questions...")
                        print(f"Prompt: {prompt}")
                        
                        try:
                            response = llm.invoke(prompt)
                            print(f"LLM Response received ({len(response)} chars)")
                            
                            # Extract questions from response
                            questions = extract_questions(response)
                            if not questions and response:
                                # If extraction failed but we have a response, use the whole text
                                questions = [response]
                                
                            print(f"✓ Generated {len(questions)} questions")
                            
                            # Add generated questions to section text, limited to the number we need
                            added_questions = 0
                            for q_idx, question in enumerate(questions):
                                if q_idx < num_questions_for_subtopic and section_question_count < no_of_questions[i]:
                                    question_text = question.strip()
                                    formatted_question = f"Q{question_counter}: {question_text} ({marks_per_question[i]} Marks)\n\n"
                                    final_questions += formatted_question
                                    
                                    # Store question data
                                    questions_data.append({
                                        'id': question_counter,
                                        'text': question_text,
                                        'marks': marks_per_question[i],
                                        'section': section_info['number'],
                                        'topic': topic,
                                        'subtopic': subtopic,
                                        'section_info': section_info
                                    })
                                    
                                    question_counter += 1
                                    section_question_count += 1
                                    added_questions += 1
                                    
                                    # Stop if we've reached the total number of questions for this section
                                    if section_question_count >= no_of_questions[i]:
                                        break
                            
                            print(f"Added {added_questions} questions from subtopic {subtopic}")
                            
                        except Exception as e:
                            print(f"Error generating questions: {e}")
                            error_msg = f"  [Error generating questions: {e}]\n\n"
                            final_questions += error_msg
                
                # If we've reached the total number of questions for this section, break out of the topic loop
                if section_question_count >= no_of_questions[i]:
                    print(f"Reached the required {no_of_questions[i]} questions for section {i+1}, stopping generation.")
                    break
            
            # Check if we have the right number of questions for this section
            if section_question_count < no_of_questions[i]:
                print(f"⚠ Warning: Generated only {section_question_count} out of {no_of_questions[i]} questions for section {i+1}")
        
        # Store data in session for the edit page
        session['questions_data'] = questions_data
        session['question_paper_header'] = f"{year} {subject} Question Paper" + (f"\nBranch: {branch}" if branch else "")
        session['year'] = year
        session['subject'] = subject
        session['branch'] = branch

        # Redirect to the edit page
        return redirect(url_for('edit_questions'))

    except Exception as e:
        print(f"❌ Error in generate route: {e}")
        return f"An error occurred: {e}", 500


@app.route('/edit_questions', methods=['GET'])
@login_required
def edit_questions():
    questions_data = session.get('questions_data', [])
    question_paper_header = session.get('question_paper_header', '')
    year = session.get('year', '')
    subject = session.get('subject', '')
    branch = session.get('branch', '')
    
    # Group questions by section
    sections = {}
    for q in questions_data:
        section_num = q['section']
        if section_num not in sections:
            sections[section_num] = {
                'info': q['section_info'],
                'questions': []
            }
        sections[section_num]['questions'].append(q)
    
    return render_template('edit_questions.html', 
                           sections=sections,
                           question_paper_header=question_paper_header,
                           year=year,
                           subject=subject,
                           branch=branch)




app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

@app.route('/save_questions', methods=['POST'])
@login_required
def save_questions():
    try:
        # Extract edited questions from form
        edited_questions = {}
        for key, value in request.form.items():
            if key.startswith('question_'):
                question_id = int(key.split('_')[1])
                edited_questions[question_id] = value.strip()

        # Get original questions from session
        questions_data = session.get('questions_data', [])

        # Update questions
        for q in questions_data:
            if q['id'] in edited_questions:
                q['text'] = edited_questions[q['id']]

        # Paper details
        year = session.get('year', '')
        subject = session.get('subject', '')
        branch = session.get('branch', '')

        # Generate final text
        final_questions = generate_question_paper_text(questions_data, year, subject, branch)

        # Store only the final output path in session (reduce size)
        print("\n=== Generating PDF ===")
        output_dir = r"question paper"
        if not os.path.exists(output_dir):
            print(f"Creating output directory: {output_dir}")
            os.makedirs(output_dir)

        pdf_output = os.path.join(output_dir, f"{subject}_{year}.pdf")
        print(f"Creating PDF: {pdf_output}")

        try:
            pdf = FPDF()
            pdf.add_page()

            # Register all DejaVu font variants
            font_dir = os.path.abspath("Fonts1")
            pdf.add_font('DejaVu', '', os.path.join(font_dir, 'DejaVuSans.ttf'), uni=True)
            pdf.add_font('DejaVu', 'B', os.path.join(font_dir, 'dejavu-sans-bold.ttf'), uni=True)
            pdf.add_font('DejaVu', 'I', os.path.join(font_dir, 'dejavuserif-italic.ttf'), uni=True)

            pdf.set_font("DejaVu", size=12)

            # Add content
            lines = final_questions.split('\n')
            for line in lines:
                if line.startswith('SECTION') or line.startswith('==='):
                    pdf.set_font("DejaVu", 'B', size=14)
                    pdf.cell(0, 10, line, ln=True)
                    pdf.set_font("DejaVu", size=12)
                elif line.startswith('Topic:'):
                    pdf.set_font("DejaVu", 'B', size=12)
                    pdf.cell(0, 8, line, ln=True)
                    pdf.set_font("DejaVu", size=12)
                elif line.startswith('  Subtopic:'):
                    pdf.set_font("DejaVu", 'I', size=12)
                    pdf.cell(0, 8, line, ln=True)
                    pdf.set_font("DejaVu", size=12)
                elif line.startswith('Q'):
                    pdf.multi_cell(0, 8, line)
                    pdf.ln(4)
                else:
                    if line.strip():
                        pdf.cell(0, 8, line, ln=True)

            pdf.output(pdf_output)
            print("✓ PDF generated successfully")

            # Save only path in session
            session['pdf_path'] = pdf_output

            return redirect(url_for('download_page'))

        except Exception as e:
            print(f"❌ Error generating PDF: {e}")
            return f"Error generating PDF: {e}", 500

    except Exception as e:
        print(f"❌ Error in save_questions route: {e}")
        return f"An error occurred: {e}", 500


        

@app.route('/download_page')
@login_required
def download_page():
    pdf_path = session.get('pdf_path', '')
    subject = session.get('subject', '')
    year = session.get('year', '')
    
    if not pdf_path:
        return "No PDF found to download. Please generate a question paper first.", 404
    
    filename = f"{subject}_{year}"
    
    return render_template('download_page.html', filename=filename)



@app.route('/download_document')
@login_required
def download_document():
    # Get the file type from query parameter
    file_type = request.args.get('type', 'pdf')
    
    pdf_path = session.get('pdf_path', '')
    subject = session.get('subject', '')
    year = session.get('year', '')
    
    if not pdf_path or not os.path.exists(pdf_path):
        return "Document file not found", 404
    
    # Get the final_questions content from session or regenerate it
    final_questions = session.get('final_questions', '')
    
    if not final_questions:
        # If not available in session, we need to regenerate the content
        questions_data = session.get('questions_data', [])
        if not questions_data:
            return "Question data not found", 404
            
        # Regenerate the text content
        final_questions = generate_question_paper_text(
            questions_data, 
            session.get('year', ''), 
            session.get('subject', ''),
            session.get('branch', '')
        )
    
    # If docx file is requested
    if file_type == 'docx':
        # Create a temporary docx file
        docx_output = os.path.join(os.path.dirname(pdf_path), f"{subject}_{year}.docx")
        
        # Create a new Document
        doc = Document()
        
        # Split the text into lines
        lines = final_questions.split('\n')
        
        for line in lines:
            if line.startswith('='):
                # Horizontal line
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(4)
            elif line.startswith(f"{year} {subject}"):
                # Title
                p = doc.add_paragraph(line)
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_after = Pt(6)
                for run in p.runs:
                    run.bold = True
                    run.font.size = Pt(16)
            elif line.startswith('Branch:'):
                # Branch info
                p = doc.add_paragraph(line)
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_after = Pt(10)
                for run in p.runs:
                    run.font.size = Pt(14)
            elif line.startswith('SECTION'):
                # Section header
                p = doc.add_paragraph(line)
                p.paragraph_format.space_before = Pt(12)
                p.paragraph_format.space_after = Pt(4)
                for run in p.runs:
                    run.bold = True
                    run.font.size = Pt(14)
            elif line.startswith("Bloom's Taxonomy"):
                # Bloom's taxonomy info
                p = doc.add_paragraph(line)
                p.paragraph_format.space_after = Pt(4)
                for run in p.runs:
                    run.italic = True
            elif line.startswith('-'):
                # Separator line
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(6)
            elif line.startswith('Topic:'):
                # Topic header
                p = doc.add_paragraph(line)
                p.paragraph_format.space_before = Pt(10)
                p.paragraph_format.space_after = Pt(4)
                for run in p.runs:
                    run.bold = True
            elif line.startswith('  Subtopic:'):
                # Subtopic header
                p = doc.add_paragraph(line)
                p.paragraph_format.space_after = Pt(4)
                for run in p.runs:
                    run.italic = True
            elif line.startswith('Q'):
                # Question text
                p = doc.add_paragraph(line)
                p.paragraph_format.space_after = Pt(10)
                # Make just the question number part bold (e.g., "Q1:")
                if ':' in line:
                    q_number_end = line.find(':') + 1
                    q_text = line[q_number_end:].strip()
                    
                    p.text = ""
                    q_num = p.add_run(line[:q_number_end] + " ")
                    q_num.bold = True
                    p.add_run(q_text)
            elif line.strip():
                # Regular paragraph
                p = doc.add_paragraph(line)
                p.paragraph_format.space_after = Pt(4)
        
        # Save the document
        doc.save(docx_output)
        
        return send_file(docx_output, as_attachment=True, download_name=f"{subject}_{year}.docx")
    
    # If text file is requested
    elif file_type == 'text':
        # Create a temporary text file
        text_output = os.path.join(os.path.dirname(pdf_path), f"{subject}_{year}.txt")
        with open(text_output, 'w') as f:
            f.write(final_questions)
            
        return send_file(text_output, as_attachment=True, download_name=f"{subject}_{year}.txt")
    
    # Default: return PDF
    return send_file(pdf_path, as_attachment=True, download_name=f"{subject}_{year}.pdf")


# Helper function to generate question paper text
def generate_question_paper_text(questions_data, year, subject, branch):
    # Generate the final question paper text
    final_questions = f"{'='*50}\n"
    final_questions += f"{year} {subject} Question Paper\n"
    if branch:
        final_questions += f"Branch: {branch}\n"
    final_questions += f"{'='*50}\n\n"
    
    # Group questions by section
    sections = {}
    for q in questions_data:
        section_num = q['section']
        if section_num not in sections:
            sections[section_num] = {
                'info': q['section_info'],
                'questions': []
            }
        sections[section_num]['questions'].append(q)
    
    # Build the question paper text
    question_counter = 1  # Initialize a sequential counter for questions
    
    for section_num in sorted(sections.keys()):
        section = sections[section_num]
        
        # Add section header
        section_text = f"\nSECTION {section_num}: {section['info']['type']} "
        section_text += f"({len(section['questions'])} Questions, {section['info']['marks']} Marks each)\n"
        section_text += f"Bloom's Taxonomy Level: {section['info']['bloom_level']}\n"
        section_text += f"{'-'*50}\n\n"
        
        final_questions += section_text
        
        # Group questions by topic and subtopic
        topics = {}
        for q in section['questions']:
            topic = q['topic']
            subtopic = q['subtopic']
            
            if topic not in topics:
                topics[topic] = {}
            
            if subtopic not in topics[topic]:
                topics[topic][subtopic] = []
            
            topics[topic][subtopic].append(q)
        
        # Add questions by topic and subtopic
        for topic in topics:
            final_questions += f"Topic: {topic}\n"
            
            for subtopic in topics[topic]:
                final_questions += f"  Subtopic: {subtopic}\n"
                
                for q in topics[topic][subtopic]:
                    # Use sequential question number instead of ID
                    final_questions += f"Q{question_counter}: {q['text']} ({q['marks']} Marks)\n\n"
                    question_counter += 1  # Increment counter after each question
    
    return final_questions



@app.route('/download_pdf')
@login_required
def download_pdf():
    pdf_path = session.get('pdf_path', '')
    
    if not pdf_path or not os.path.exists(pdf_path):
        return "PDF file not found", 404
    
    return send_file(pdf_path, as_attachment=True)


def distribute_questions(total_questions, num_subtopics):
    """Distribute questions as evenly as possible among subtopics"""
    if num_subtopics == 0:
        return []
        
    base_count = total_questions // num_subtopics
    remainder = total_questions % num_subtopics
    
    distribution = []
    for i in range(num_subtopics):
        distribution.append(base_count + (1 if i < remainder else 0))
    
    return distribution


def extract_questions(response_text):
    """Extract individual questions from the LLM response"""
    # Try to split by common question markers
    questions = []
    
    # Method 1: Look for numbered questions (1., 2., etc.)
    numbered_pattern = re.compile(r'(?:\d+\.\s*)([^\d].*?)(?=\n\d+\.|\Z)', re.DOTALL)
    numbered_matches = numbered_pattern.findall(response_text)
    if numbered_matches:
        return numbered_matches
    
    # Method 2: Look for "Question:" or "Q:" markers
    q_pattern = re.compile(r'(?:Question|Q):\s*(.*?)(?=\n(?:Question|Q):|$)', re.DOTALL)
    q_matches = q_pattern.findall(response_text)
    if q_matches:
        return q_matches
    
    # Method 3: Split by double newlines (assuming each question is a paragraph)
    paragraphs = [p.strip() for p in response_text.split('\n\n') if p.strip()]
    if paragraphs:
        return paragraphs
    
    # If all methods fail, return the entire text as a single question
    return [response_text] if response_text.strip() else []


def create_syllabus_structure(year, department, subject_name, subject_code, syllabus_text):
    """
    Creates the hierarchical syllabus structure in Firebase and stores the syllabus text.
    Structure: syllabus -> year -> department -> subject -> syllabus
    """
    print(f"\n=== Creating syllabus structure for {subject_name} ===")
    try:
        # Create base syllabus reference
        syllabus_ref = db.collection('syllabus')

        # Create/get year document
        year_ref = syllabus_ref.document(year)
        if not year_ref.get().exists:
            year_ref.set({'created_at': firestore.SERVER_TIMESTAMP})
            print(f"✓ Created year document: {year}")

        # Create/get department document under year
        dept_ref = year_ref.collection('departments').document(department)
        if not dept_ref.get().exists:
            dept_ref.set({'created_at': firestore.SERVER_TIMESTAMP})
            print(f"✓ Created department document: {department}")

        # Create subject document under department with subject code
        subject_ref = dept_ref.collection('subjects').document(subject_name)

        # Store subject data including syllabus text and subject code
        subject_ref.set({
            'name': subject_name,
            'code': subject_code,
            'syllabus': syllabus_text,
            'created_at': firestore.SERVER_TIMESTAMP
        })
        print(f"✓ Created subject document: {subject_name} with code: {subject_code}")

        return True, "Subject and syllabus added successfully"
    except Exception as e:
        print(f"❌ Error in create_syllabus_structure: {e}")
        return False, str(e)
    
def extract_topics_and_subtopics(syllabus_text, subject):
    """
    Use LLM to extract topics and their subtopics from the syllabus text.
    Returns a dictionary with topics as keys and lists of subtopics as values.
    """
    print(f"\n=== Extracting topics and subtopics from syllabus for subject: {subject} ===")
    try:
        prompt = (
            f"Analyze the following syllabus text for the subject '{subject}' and extract the main topics "
            f"and their subtopics. Format the response as follows:\n"
            f"TOPIC: [Main Topic Name]\n"
            f"SUBTOPICS:\n"
            f"- [Subtopic 1]\n"
            f"- [Subtopic 2]\n"
            f"[Repeat for each main topic]\n\n"
            f"Syllabus text:\n{syllabus_text}"
        )
        
        print("Querying LLM to extract topics and subtopics...")
        response = llm.invoke(prompt)
        
        # Parse the response
        topics_dict = {}
        current_topic = None
        
        for line in response.split('\n'):
            line = line.strip()
            if line.startswith('TOPIC:'):
                current_topic = line.replace('TOPIC:', '').strip()
                topics_dict[current_topic] = []
            elif line.startswith('-') and current_topic:
                subtopic = line.replace('-', '').strip()
                topics_dict[current_topic].append(subtopic)
        
        print(f"✓ Extracted {len(topics_dict)} topics with subtopics:")
        for topic, subtopics in topics_dict.items():
            print(f"  Topic: {topic}")
            for subtopic in subtopics:
                print(f"    - {subtopic}")
            
        return topics_dict
    except Exception as e:
        print(f"❌ Error extracting topics and subtopics: {e}")
        return {}
    

def get_subjects_for_year_department(year, department):
    """
    Retrieves subjects for a specific year and department from Firebase
    """
    try:
        # Navigate through the hierarchy to get subjects
        subjects_ref = (db.collection('syllabus')
                       .document(year)
                       .collection('departments')
                       .document(department)
                       .collection('subjects')
                       .stream())
        
        # Extract subject names from documents
        subjects = [doc.id for doc in subjects_ref]
        return sorted(subjects)  # Return sorted list of subject names
    except Exception as e:
        print(f"Error retrieving subjects: {e}")
        return []

def get_syllabus_for_subject(year, department, subject):
    """
    Retrieves syllabus text for a specific subject
    """
    try:
        subject_doc = (db.collection('syllabus')
                      .document(year)
                      .collection('departments')
                      .document(department)
                      .collection('subjects')
                      .document(subject)
                      .get())
        
        if subject_doc.exists:
            return subject_doc.to_dict().get('syllabus', '')
        return ''
    except Exception as e:
        print(f"Error retrieving syllabus: {e}")
        return ''
    

@app.route('/get_subjects')
@login_required
def get_subjects():
    year = request.args.get('year')
    department = request.args.get('department')
    
    if not year or not department:
        return jsonify([])
    
    subjects = get_subjects_for_year_department(year, department)
    return jsonify(subjects)

@app.route('/add_subject', methods=['POST'])
@login_required
def add_subject():
    try:
        # Get form data
        year = request.form.get('year')
        department = request.form.get('department')
        subject_name = request.form.get('subject_name')
        subject_code = request.form.get('subject_code')
        syllabus_text = request.form.get('syllabus_text')
        
        # Validate required fields
        if not all([year, department, subject_name, subject_code, syllabus_text]):
            return jsonify({
                'success': False,
                'message': "All fields are required"
            })
        
        print("\n=== Step 1: Extracting topics and subtopics from syllabus ===")
        topics_dict = extract_topics_and_subtopics(syllabus_text, subject_name)
        
        if not topics_dict:
            return jsonify({
                'success': False,
                'message': "Failed to extract topics and subtopics from syllabus"
            })
        
        print("\n=== Step 2: Creating question collection structures ===")
        success, message, subject_refs = create_question_structure(subject_name, subject_code, topics_dict)
        
        if not success:
            return jsonify({
                'success': False,
                'message': f"Failed to create question structures: {message}"
            })
        
        print("\n=== Step 3: Storing syllabus text ===")
        success, message = create_syllabus_structure(year, department, subject_name, subject_code, syllabus_text)
        
        return jsonify({
            'success': success,
            'message': message,
            'year': year,
            'department': department,
            'subject': subject_name,
            'subject_code': subject_code,
            'topics': topics_dict
        })
            
    except Exception as e:
        print(f"❌ Error in add_subject: {e}")
        return jsonify({
            'success': False,
            'message': f"An error occurred: {str(e)}"
        })
    

def ensure_collection_structure(collection_name, subject_name, subject_code):
    """
    Ensures the collection and subject document exist.
    Returns a DocumentReference to the subject.
    """
    print(f"\n=== Ensuring {collection_name} structure for {subject_name} ===")
    try:
        collection_ref = db.collection(collection_name)
        subject_ref = collection_ref.document(subject_name)  # Correct: Collection > Document

        if not subject_ref.get().exists:
            print(f"✓ Creating new subject document: {subject_name}")
            subject_ref.set({
                'name': subject_name,
                'code': subject_code,
                'created_at': firestore.SERVER_TIMESTAMP
            })
        else:
            print(f"✓ Subject {subject_name} already exists. Updating metadata.")
            subject_ref.update({
                'code': subject_code,
                'updated_at': firestore.SERVER_TIMESTAMP
            })

        return subject_ref
    except Exception as e:
        print(f"❌ Error in ensure_collection_structure: {e}")
        raise e
    
def sanitize_for_firestore_id(name):
    """
    Sanitize Firestore document IDs by removing problematic characters.
    Firestore document IDs must not contain '/' and are best kept simple.
    """
    name = name.strip()
    # Remove characters that can interfere with path parsing
    name = re.sub(r'[\/#\[\]%]', '', name)
    name = name.replace('(', '').replace(')', '')
    name = name.replace(':', '-').replace(',', '').replace(';', '')
    return name


def ensure_topic_structure(subject_ref, topic_name):
    try:
        safe_topic_name = sanitize_for_firestore_id(topic_name)
        topics_collection_ref = subject_ref.collection('topics')
        topic_ref = topics_collection_ref.document(safe_topic_name)

        if not topic_ref.get().exists:
            print(f"✓ Creating new topic: {safe_topic_name}")
            topic_ref.set({
                'name': topic_name,  # original name for display
                'created_at': firestore.SERVER_TIMESTAMP
            })
        else:
            print(f"✓ Topic already exists: {safe_topic_name}")

        return topic_ref
    except Exception as e:
        print(f"❌ Error in ensure_topic_structure: {e}")
        raise e


def ensure_subtopic_structure(topic_ref, subtopic_name):
    try:
        safe_subtopic_name = sanitize_for_firestore_id(subtopic_name)
        subtopics_collection_ref = topic_ref.collection('subtopics')
        subtopic_ref = subtopics_collection_ref.document(safe_subtopic_name)

        if not subtopic_ref.get().exists:
            print(f"✓ Creating new subtopic: {safe_subtopic_name}")
            subtopic_ref.set({
                'name': subtopic_name,  # original name for display
                'created_at': firestore.SERVER_TIMESTAMP
            })
        else:
            print(f"✓ Subtopic already exists: {safe_subtopic_name}")

        return subtopic_ref
    except Exception as e:
        print(f"❌ Error in ensure_subtopic_structure: {e}")
        raise e

    

def extract_topics_from_syllabus(syllabus_text, subject):
    """
    Use LLM to extract topics from the syllabus text.
    """
    print(f"\n=== Extracting topics from syllabus for subject: {subject} ===")
    try:
        prompt = (
            f"Extract the main topics or chapters from the following syllabus text for the subject '{subject}'. "
            f"Return each topic on a new line, exactly as it appears in the text. "
            f"Do not include any additional text or explanations:\n\n"
            f"{syllabus_text}"
        )
        
        print("Querying LLM to extract topics...")
        response = llm.invoke(prompt)
        topics = [topic.strip() for topic in response.split('\n') if topic.strip()]
        
        print(f"✓ Extracted {len(topics)} topics:")
        for topic in topics:
            print(f"  - {topic}")
            
        return topics
    except Exception as e:
        print(f"❌ Error extracting topics: {e}")
        return []
    

def create_question_structure(subject_name, subject_code, topics_dict):
    """
    Creates identical structure in both llm_questions and pyp_questions collections.
    """
    print("\n=== Creating question structures ===")
    collections = ['llm_questions', 'pyp_questions']
    subject_refs = {}

    try:
        for collection_name in collections:
            print(f"\n--- Processing {collection_name} collection ---")

            # Ensure subject document exists in the collection
            subject_ref = ensure_collection_structure(collection_name, subject_name, subject_code)

            assert isinstance(subject_ref, firestore.DocumentReference), "Invalid subject_ref"
            subject_refs[collection_name] = subject_ref

            for topic, subtopics in topics_dict.items():
                topic_ref = ensure_topic_structure(subject_ref, topic)
                assert isinstance(topic_ref, firestore.DocumentReference), f"Invalid topic_ref for topic: {topic}"

                for subtopic in subtopics:
                    subtopic_ref = ensure_subtopic_structure(topic_ref, subtopic)
                    assert isinstance(subtopic_ref, firestore.DocumentReference), f"Invalid subtopic_ref for subtopic: {subtopic}"
                    print(f"✓ Completed structure for {collection_name}: topic: {topic}, subtopic: {subtopic}")

        return True, "Question structures created successfully", subject_refs

    except Exception as e:
        print(f"❌ Error creating question structures: {e}")
        return False, str(e), None


    
    
def check_subject_exists(subject, existing_subjects):
    """
    Use LLM to check if the subject exists in the database by comparing with existing subjects.
    """
    print(f"\n=== Checking if subject exists: {subject} ===")
    try:
        prompt = (
            f"Given the following list of existing subjects:\n{', '.join(existing_subjects)}\n\n"
            f"Is the subject '{subject}' similar to any of the existing subjects? "
            f"Respond with only the most similar subject name from the list if it exists, "
            f"or 'None' if no similar subject exists."
        )
        
        print("Querying LLM to check subject similarity...")
        response = llm.invoke(prompt)
        similar_subject = response.strip()
        
        if similar_subject == 'None':
            print(f"✓ No similar subject found. '{subject}' is a new subject.")
            return None
        else:
            print(f"✓ Similar subject found: {similar_subject}")
            return similar_subject
    except Exception as e:
        print(f"❌ Error checking subject existence: {e}")
        return None

model = SentenceTransformer('all-mpnet-base-v2') 
@app.route('/get_subject_embeddings', methods=['GET'])
@login_required
def get_subject_embeddings():
    subject = request.args.get('subject')
    if not subject:
        return jsonify({"success": False, "message": "No subject provided."})

    subject = subject.strip()
    all_embeddings = []

    # 🚀 Query across all subcollections named 'questions'!
    questions_query = db.collection_group('questions').where('subject', '==', subject).stream()

    for q in questions_query:
        data = q.to_dict()
        print(f"📄 Found question: {data.get('text', 'No text found')}")
        if 'embedding' in data:
            all_embeddings.append({
                'text': data.get('text', ''),
                'embedding': data['embedding']
            })

    print(f"✅ Retrieved {len(all_embeddings)} embeddings for subject '{subject}'.")
    return jsonify({"success": True, "embeddings": all_embeddings})

@app.route('/compare_embeddings', methods=['POST'])
@login_required
def compare_embeddings():
    data = request.get_json()
    current_question = data.get('current_question')
    stored_embeddings = data.get('stored_embeddings')

    if not current_question or not stored_embeddings:
        print("❌ Invalid input received in compare_embeddings!")
        return jsonify({"success": False, "message": "Invalid input."})

    print(f"🔵 Comparing embeddings for question: {current_question[:50]}...")  # Print first 50 chars

    # Generate embedding for current question
    current_emb = model.encode(current_question).tolist()  # 🔥 very important .tolist()

    import numpy as np
    def compute_cosine_similarity(vec1, vec2):
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        dot = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    # Find highest similarity
    max_similarity = 0
    for stored_emb in stored_embeddings:
        sim = compute_cosine_similarity(current_emb, stored_emb['embedding'])  # 🔥 FIXED
        if sim > max_similarity:
            max_similarity = sim

    print(f"✅ Max similarity found: {max_similarity:.4f}")

    return jsonify({"success": True, "similarity": max_similarity})



############################################# insert to db functionality start #############################################

# Initialize imports and configuration
import os
from flask import request, session, redirect, url_for, render_template
from werkzeug.utils import secure_filename
from llama_parse import LlamaParse
import google.generativeai as genai
import pytesseract
from pdf2image import convert_from_path
import io
from PIL import Image
import re
import fitz  # PyMuPDF

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}

# Configure app settings
def configure_app(app):
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB max upload size
    
    # Create upload folder if it doesn't exist
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

# Set up API keys
def setup_api_keys():
    # Set LlamaParse API key - this needs to be called before using LlamaParse
    os.environ["LLAMA_CLOUD_API_KEY"] = "llx-D7yfJC7bCTTg3K7RfauK1K5fR9xwltZBlWonFjloFF9CZfD9"
    # Add Gemini API key setup here if needed
    # genai.configure(api_key="your-gemini-api-key")

# Make sure to call this function at application startup
setup_api_keys()

def allowed_file(filename):
    """Check if the file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(pdf_path, use_ocr=True):
    """
    Extract text from a PDF using multiple methods for better coverage:
    1. PyMuPDF for text extraction
    2. OCR for image-based content
    3. LlamaParse as a fallback if available
    """
    combined_text = ""
    
    try:
        # Method 1: PyMuPDF extraction (most reliable for text-based PDFs)
        try:
            pdf_document = fitz.open(pdf_path)
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                text = page.get_text("text")
                combined_text += text + "\n"
            pdf_document.close()
        except Exception as e:
            print(f"PyMuPDF extraction failed: {e}")
            
        # Method 2: OCR if needed and use_ocr is True (best for image-based content)
        if use_ocr:
            try:
                # For Windows, you might need to set the path to Tesseract
                # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
                
                images = convert_from_path(pdf_path)
                for i, image in enumerate(images):
                    text = pytesseract.image_to_string(image, lang='eng', config='--psm 6')
                    combined_text += text + "\n"
            except Exception as e:
                print(f"OCR extraction failed: {e}")
        
        # Method 3: Try LlamaParse if other methods didn't produce enough text
        if len(combined_text.strip()) < 500:  # If we don't have much text yet
            try:
                # Ensure API key is set
                if os.environ.get("LLAMA_CLOUD_API_KEY"):
                    parser = LlamaParse(api_key=os.environ["LLAMA_CLOUD_API_KEY"], result_type="markdown")
                    result = parser.load_data(pdf_path)
                    if isinstance(result, str):
                        combined_text += result + "\n"
                    else:
                        # Handle other return types if any
                        combined_text += str(result) + "\n"
                else:
                    print("LlamaParse API key not found in environment")
            except Exception as e:
                print(f"LlamaParse extraction failed: {e}")
        
        # Remove duplicate content by splitting into paragraphs and using a set
        paragraphs = set(p.strip() for p in combined_text.split('\n') if p.strip())
        combined_text = '\n'.join(paragraphs)
        
        if not combined_text.strip():
            raise ValueError("No text extracted from any method")
            
        return combined_text
            
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return ""  # Return empty string instead of None for easier handling

def extract_questions_from_text(text):
    """
    Extract questions from text using Gemini AI with robust prompting.
    """
    try:
        model = genai.GenerativeModel('gemini-2.0-flash-lite-preview-02-05')
        
        # First extract metadata
        metadata_prompt = (
            f"Analyze this text from a question paper and extract ONLY the following metadata in JSON format:\n"
            f"- Subject name\n"
            f"- Subject code\n"
            f"- Year\n"
            f"- Branch or department\n"
            f"- Total marks\n"
            f"- Time duration\n"
            f"- Any other critical exam metadata\n\n"
            f"Format as a JSON object with these fields. If any field is not found, use null for its value.\n\n"
            f"Here is the text:\n{text[:5000]}"  # First 5000 chars should contain metadata
        )
        
        # Then extract questions with careful instructions
        questions_prompt = (
            f"You are a specialized AI for extracting questions from exam papers. Analyze this question paper carefully.\n\n"
            f"TASK: Extract ALL questions including their sub-parts completely. Don't miss any questions or cut any off.\n\n"
            f"INSTRUCTIONS:\n"
            f"1. Include the question number exactly as shown in the paper\n"
            f"2. Include all parts and subparts of each question\n"
            f"3. Include the marks allocated for each question in [x marks] format\n"
            f"4. Start each question with '###' as a separator\n"
            f"5. Do not truncate long questions - include them completely\n"
            f"6. Include any diagrams or figures as [DIAGRAM/FIGURE]\n"
            f"7. Total questions found should match the question paper's total\n\n"
            f"Here is the question paper text:\n\n{text}"
        )
        
        # Use higher temperature for better extraction and increase max tokens
        generation_config = {
            "temperature": 0.2,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 8000,  # Use maximum allowed
        }
        
        # Send requests to Gemini
        metadata_response = model.generate_content(
            metadata_prompt,
            generation_config=generation_config
        )
        
        questions_response = model.generate_content(
            questions_prompt,
            generation_config=generation_config
        )
        
        # Process responses
        metadata_text = metadata_response.text.strip()
        questions_text = questions_response.text.strip()
        
        # Verify question count if possible
        question_count = len(re.findall(r'###', questions_text))
        
        # Add question count info
        final_text = (
            f"INFO: Extracted {question_count} questions from the document.\n\n"
            f"{metadata_text}\n\n"
            f"{questions_text}"
        )
        
        return final_text
        
    except Exception as e:
        print(f"An error occurred while extracting questions: {e}")
        # Try a simpler extraction as fallback
        try:
            return simple_question_extraction(text)
        except:
            return ""

def simple_question_extraction(text):
    """Simple fallback for question extraction when Gemini fails"""
    # Basic pattern matching for questions
    questions = []
    
    # Try to find question patterns like "1.", "Question 1:", etc.
    patterns = [
        r'Q\.?\s*\d+\.?\s*[A-Z]',  # Q1. What
        r'Question\s+\d+\.?\s*[A-Z]',  # Question 1. What
        r'\d+\.\s+[A-Z]',  # 1. What
        r'\(\d+\)\s+[A-Z]'  # (1) What
    ]
    
    current_text = text
    for pattern in patterns:
        matches = re.finditer(pattern, current_text)
        positions = [match.start() for match in matches]
        
        if positions:
            for i in range(len(positions)):
                start = positions[i]
                end = positions[i+1] if i+1 < len(positions) else len(current_text)
                questions.append(current_text[start:end].strip())
    
    if not questions:
        # If no structured questions found, split by newlines and look for question-like content
        lines = text.split('\n')
        current_question = ""
        
        for line in lines:
            if re.match(r'^[0-9]+[\.\)]', line.strip()):
                if current_question:
                    questions.append(current_question.strip())
                current_question = line
            elif current_question:
                current_question += "\n" + line
        
        if current_question:
            questions.append(current_question.strip())
    
    return "\n###\n".join(questions)

@app.route('/upload_pdf', methods=['POST', 'GET'])
@login_required
def upload_pdf():
    # Make sure API keys are set
    setup_api_keys()
    
    if request.method == 'GET':
        return render_template('datapage.html')
        
    upload_folder = r'test'
    
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    
    # Validate request
    if 'pdf_file' not in request.files:
        return render_template('datapage.html', message="No file selected", message_type="error")
        
    if 'subject' not in request.form:
        return render_template('datapage.html', message="Please select a subject", message_type="error")
    
    file = request.files['pdf_file']
    subject_selected = request.form['subject']
    
    # Check for empty file submission
    if file.filename == '':
        return render_template('datapage.html', message="No file selected", message_type="error")
    
    if file and allowed_file(file.filename):
        try:
            # Save the file
            filename = secure_filename(file.filename)
            filepath = os.path.join(upload_folder, filename)
            file.save(filepath)
            
            # Debug information
            print(f"Processing PDF: {filepath}")
            print(f"LlamaParse API Key present: {'Yes' if os.environ.get('LLAMA_CLOUD_API_KEY') else 'No'}")
            
            # Extract text with progress tracking
            combined_text = extract_text_from_pdf(filepath)
            if not combined_text or len(combined_text) < 100:  # Basic validation
                print(f"Extraction failed or insufficient content: {len(combined_text) if combined_text else 0} characters")
                return render_template('datapage.html', 
                                      message="Text extraction failed or insufficient content extracted.", 
                                      message_type="error")
            
            print(f"Successfully extracted {len(combined_text)} characters")
            
            # Extract questions - try with OCR if regular extraction doesn't get all questions
            questions_text = extract_questions_from_text(combined_text)
            
            # Count questions
            question_count = questions_text.count('###')
            print(f"Extracted {question_count} questions")
            
            if not questions_text or '###' not in questions_text:
                print("No questions found in extracted text")
                return render_template('datapage.html', 
                                      message="No questions could be extracted. Please check the PDF format.", 
                                      message_type="error")
            
            # Store in session
            session['extracted_questions'] = questions_text
            session['selected_subject'] = subject_selected
            session['original_filename'] = filename
            
            # Redirect to confirmation
            return redirect(url_for('confirm_questions'))
            
        except Exception as e:
            print(f"Exception during processing: {str(e)}")
            return render_template('datapage.html', 
                                  message=f"An error occurred: {str(e)}", 
                                  message_type="error")
    else:
        return render_template('datapage.html', 
                              message="Invalid file format. Only PDF files are allowed.", 
                              message_type="error")

@app.route('/confirm_questions', methods=['GET', 'POST'])
@login_required
def confirm_questions():
    if request.method == 'POST':
        try:
            # Validate session data
            if 'extracted_questions' not in session or 'selected_subject' not in session:
                return render_template(
                    'confirm_questions.html',
                    error="Session expired. Please upload again."
                )

            edited_questions = request.form['questions']
            subject_selected = session['selected_subject']
            
            # Count questions for verification
            question_count = len([q for q in edited_questions.split('###') if q.strip()])
            
            # Process questions with improved error handling
            try:
                processed_questions = questorage.process_questions(
                    edited_questions,
                    db,
                    api_key,
                    subject_from_user=subject_selected
                )
            except Exception as process_error:
                return render_template(
                    'confirm_questions.html',
                    error=f"Error processing questions: {str(process_error)}",
                    questions=[q.strip() for q in edited_questions.split('###') if q.strip()],
                    subject=subject_selected
                )

            if not processed_questions:
                return render_template(
                    'confirm_questions.html',
                    error="No questions were processed successfully.",
                    questions=[q.strip() for q in edited_questions.split('###') if q.strip()],
                    subject=subject_selected
                )

            # Save to Firestore
            try:
                questorage.save_questions_to_firestore(processed_questions, db)
            except Exception as save_error:
                return render_template(
                    'confirm_questions.html',
                    error=f"Error saving to database: {str(save_error)}",
                    questions=[q.strip() for q in edited_questions.split('###') if q.strip()],
                    subject=subject_selected
                )

            # Clear session after successful save
            session.pop('extracted_questions', None)
            session.pop('selected_subject', None)
            session.pop('original_filename', None)

            # Re-render page with success message and redirect button
            questions_list = [q.strip() for q in edited_questions.split('###') if q.strip()]
            return render_template(
                'confirm_questions.html',
                questions=questions_list,
                subject=subject_selected,
                success=True,
                uploaded_count=len(processed_questions)
            )

        except Exception as e:
            return render_template(
                'confirm_questions.html',
                error=f"Error: {str(e)}"
            )

    else:  # GET request
        questions_text = session.get('extracted_questions', None)
        subject_selected = session.get('selected_subject', None)
        
        if not questions_text or not subject_selected:
            return redirect(url_for('upload_pdf'))
        
        # Split by ### and ensure we don't have empty entries
        questions_list = [q.strip() for q in questions_text.split('###') if q.strip()]
        
        return render_template(
            'confirm_questions.html',
            questions=questions_list,
            subject=subject_selected
        )


@app.route('/bt_level_ui')
@login_required
def render_bt_level_ui():
    """
    Renders the BT level prediction HTML page
    This is the page that displays the form for users to input questions
    """
    return render_template('bt_level_prediction.html')

@app.route('/api/predict_bt_level', methods=['POST'])
@login_required
def api_predict_bt_level():
    """
    API endpoint to receive a question and return the predicted BT level
    This is separate from your existing predict_bt_level_route function
    """
    try:
        # Get the question from the request
        data = request.get_json()
        if not data or 'question' not in data:
            return jsonify({'success': False, 'message': 'No question provided'}), 400

        question = data['question'].strip()
        prompt = (
            f"Convert this type of question\n{question} to short question\n\n"
        )
        
        question = llm.invoke(prompt)
        if not question:
            return jsonify({'success': False, 'message': 'Question cannot be empty'}), 400

        # Tokenize the question
        inputs = tokenizer(question, return_tensors="pt", truncation=True, padding=True, max_length=64)
        inputs = {key: val.to(device) for key, val in inputs.items()}

        # Predict BT level
        with torch.no_grad():
            outputs = model2(**inputs)
            prediction = torch.argmax(outputs.logits, dim=1).item()

        bt_levels = {0: "BT1", 1: "BT2", 2: "BT3", 3: "BT4", 4: "BT5", 5: "BT6"}
        bt_level = bt_levels.get(prediction, "Unknown")

        return jsonify({'success': True, 'bt_level': bt_level}), 200

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Update your zeropage route to handle the new action



############################################# insert to db functionality end #############################################
        
def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000/")

if __name__== "__main__":
    Timer(1, open_browser).start()  # Open the browser after 1 second
    app.run(debug=True)
