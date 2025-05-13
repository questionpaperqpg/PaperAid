from dataclasses import dataclass
from typing import Optional, Tuple, List
import google.generativeai as genai
from firebase_admin import firestore
import time
import re
import threading
from sentence_transformers import SentenceTransformer
import torch
model = SentenceTransformer('all-mpnet-base-v2')
@dataclass
class Question:
    text: str
    marks: int
    bt_level: int
    question_type: str
    subject: str
    topic: str
    subtopic: str

class RateLimiter:
    def __init__(self, max_requests=50, time_window=60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
        self.lock = threading.Lock()

    def can_make_request(self):
        current_time = time.time()
        with self.lock:
            # Remove old requests
            self.requests = [req_time for req_time in self.requests 
                           if current_time - req_time < self.time_window]
            
            if len(self.requests) < self.max_requests:
                self.requests.append(current_time)
                return True
            return False

class HierarchicalQuestionClassifier:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash-lite-preview-02-05')
        self.rate_limiter = RateLimiter()

    def wait_for_rate_limit(self):
        while not self.rate_limiter.can_make_request():
            time.sleep(0.1)

    def estimate_marks(self, question_text: str) -> int:
        """Use LLM to estimate marks when not explicitly provided"""
        self.wait_for_rate_limit()
        
        estimation_prompt = f"""
        Analyze this exam question and estimate the appropriate marks (between 1-10) it should be worth.
        Consider:
        - Question complexity
        - Expected answer length
        - Number of parts/concepts
        - Type of question (MCQ=1-2 marks, short answer=2-5 marks, long answer=4-10 marks)
        
        Question: {question_text}
        
        Respond with ONLY a number between 1 and 10.
        """
        
        try:
            print(f"Estimating marks for question: {question_text[:50]}...")  # Print progress
            response = self.model.generate_content(estimation_prompt)
            marks_str = response.text.strip()
            estimated_marks = int(marks_str)
            print(f"Estimated marks: {estimated_marks}")  # Print result
            return min(max(estimated_marks, 1), 10)
        except Exception as e:
            print(f"Error estimating marks: {e}")
            return 2

    def extract_marks_from_text(self, text: str) -> Tuple[int, str]:
        patterns = [
            r'\[(\d+)\]$',
            r'\((\d+)\s*marks?\)',
            r'^\[(\d+)\]',
            r'\[(\d+)\s*marks?\]',
            r'\((\d+)\)$',
        ]
        
        cleaned_text = text.strip()
        
        for pattern in patterns:
            match = re.search(pattern, cleaned_text)
            if match:
                try:
                    marks = int(match.group(1))
                    cleaned_text = re.sub(pattern, '', cleaned_text).strip()
                    print(f"Extracted marks: {marks} from text: {cleaned_text[:50]}...")  # Print progress
                    return marks, cleaned_text
                except ValueError:
                    continue
        
        print(f"No marks found in text. Estimating marks for: {cleaned_text[:50]}...")  # Print progress
        estimated_marks = self.estimate_marks(cleaned_text)
        return estimated_marks, cleaned_text

    def get_structure_from_firestore(self, db: firestore.Client) -> dict:
        """Get hierarchical structure from Firestore"""
        print("Fetching hierarchical structure from Firestore...")  # Print progress
        structure = {}
        subjects_ref = db.collection('pyp_questions').get()
        
        for subject_doc in subjects_ref:
            subject_name = subject_doc.id
            structure[subject_name] = {'topics': {}}
            
            topics_ref = db.collection('pyp_questions').document(subject_name).collection('topics').get()
            for topic_doc in topics_ref:
                topic_name = topic_doc.id
                structure[subject_name]['topics'][topic_name] = {'subtopics': []}
                
                subtopics_ref = (db.collection('pyp_questions')
                               .document(subject_name)
                               .collection('topics')
                               .document(topic_name)
                               .collection('subtopics')
                               .get())
                
                structure[subject_name]['topics'][topic_name]['subtopics'] = [
                    subtopic.id for subtopic in subtopics_ref
                ]
        
        print("Hierarchical structure fetched successfully.")  # Print progress
        return structure

    def get_subject_topic_subtopic(self, text: str, db: firestore.Client) -> Tuple[str, str, str]:
        """Classify question into subject, topic, and subtopic"""
        self.wait_for_rate_limit()
        
        structure = self.get_structure_from_firestore(db)
        
        classification_prompt = f"""
        Given this question and the following hierarchical structure:
        {structure}
        
        Classify this question into the most appropriate subject, topic, and subtopic:
        Question: {text}
        
        Format response exactly as:
        Subject: [subject name]
        Topic: [topic name]
        Subtopic: [subtopic name]
        
        Only use names that exist in the structure provided.
        """
        
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                print(f"Classifying question: {text[:50]}...")  # Print progress
                response = self.model.generate_content(classification_prompt)
                lines = response.text.strip().split('\n')
                
                if len(lines) >= 3:
                    subject = lines[0].split(':')[1].strip()
                    topic = lines[1].split(':')[1].strip()
                    subtopic = lines[2].split(':')[1].strip()
                    print(f"Classification result - Subject: {subject}, Topic: {topic}, Subtopic: {subtopic}")  # Print result
                    return subject, topic, subtopic
                
            except Exception as e:
                print(f"Attempt {retry_count + 1} failed: {e}")
                retry_count += 1
                time.sleep(1 * retry_count)  # Progressive delay
        
        raise Exception("Failed to classify question after multiple attempts")

    def classify_question(self, text: str) -> dict:
        """Classify question type and Bloom's taxonomy level"""
        self.wait_for_rate_limit()
        
        classification_prompt = f"""
        Analyze this question and provide:
        1. Bloom's Taxonomy level (just the number 1-6)
        2. Question type (one of: MCQ, Fill-in-blanks, Short Answer, Long Answer, Programming, Numerical)
        
        Question: {text}
        
        Format response as:
        BT: [level]
        Type: [type]
        """
        
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                print(f"Classifying question type and Bloom's level for: {text[:50]}...")  # Print progress
                response = self.model.generate_content(classification_prompt)
                lines = response.text.strip().split('\n')
                
                if len(lines) >= 2:
                    bt_level = int(lines[0].split(':')[1].strip())
                    question_type = lines[1].split(':')[1].strip()
                    print(f"Classification result - BT Level: {bt_level}, Type: {question_type}")  # Print result
                    return {
                        'bt_level': bt_level,
                        'question_type': question_type
                    }
                
            except Exception as e:
                print(f"Attempt {retry_count + 1} failed: {e}")
                retry_count += 1
                time.sleep(1 * retry_count)
        
        raise Exception("Failed to classify question after multiple attempts")

def process_question(question_text, db, api_key, subject_from_user=None):
    classifier = HierarchicalQuestionClassifier(api_key)
    try:
        print(f"Processing question: {question_text[:50]}...")  # Print progress
        
        # Step 1: Extract marks from text (like [5])
        marks, cleaned_text = classifier.extract_marks_from_text(question_text)

        # Step 2: Set subject
        if subject_from_user:
            subject = subject_from_user
            print(f"Using user-selected subject: {subject}")
        else:
            # If somehow not provided, fallback to LLM classification
            subject, topic, subtopic = classifier.get_subject_topic_subtopic(cleaned_text, db)
            print(f"LLM classified subject as: {subject}")

        # Step 3: Only detect topic and subtopic (automatically by Gemini)
        _, topic, subtopic = classifier.get_subject_topic_subtopic(cleaned_text, db)
        print(f"Detected topic: {topic}, subtopic: {subtopic}")

        # Step 4: Classify BT level and question type
        classifications = classifier.classify_question(cleaned_text)

        print(f"Question processed successfully: {cleaned_text[:50]}...")  # Print progress
        
        return Question(
            text=cleaned_text,
            marks=marks,
            bt_level=classifications['bt_level'],
            question_type=classifications['question_type'],
            subject=subject,
            topic=topic,
            subtopic=subtopic
        )
    except Exception as e:
        print(f"Error processing question: {e}")
        return None

def process_questions(questions_text, db, api_key, subject_from_user=None):
    print("Starting to process questions...")  # Print progress
    raw_questions = [q.strip() for q in questions_text.split('###') if q.strip()]

    processed_questions = []
    for q in raw_questions:
        if q.lower().startswith("info") or "subject name" in q.lower():
            print(f"Skipping info block: {q[:30]}...")
            continue  # 🔥 Skip info fields
        
        question = process_question(q, db, api_key, subject_from_user=subject_from_user)
        if question:
            processed_questions.append(question)

    print(f"Processed {len(processed_questions)} valid questions.")  # Print progress
    return processed_questions



def save_questions_to_firestore(questions: List[Question], db: firestore.Client):
    """Save questions to Firestore with retry logic and generate + store embeddings"""
    print("Saving questions to Firestore with embeddings...")  # Print progress

    for question in questions:
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # 🔥 Generate embedding for the question text
                embedding = model.encode(question.text)

                # Prepare Firestore path
                question_ref = (db.collection('pyp_questions')
                               .document(question.subject)
                               .collection('topics')
                               .document(question.topic)
                               .collection('subtopics')
                               .document(question.subtopic)
                               .collection('questions')
                               .document())

                # Save question + embedding
                question_ref.set({
                    'text': question.text,
                    'marks': question.marks,
                    'bt_level': question.bt_level,
                    'question_type': question.question_type,
                    'embedding': embedding.tolist(),  # Save as list
                    'subject':  question.subject,
                    'timestamp': firestore.SERVER_TIMESTAMP
                   
                })

                print(f"Question saved with embedding: {question.text[:50]}...")  # Print progress
                break  # Success, exit retry loop

            except Exception as e:
                print(f"Attempt {retry_count + 1} failed: {e}")
                retry_count += 1
                time.sleep(1 * retry_count)
        
        if retry_count == max_retries:
            print(f"Failed to save question after {max_retries} attempts")