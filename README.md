
# AI-Powered Question Paper Generation Based on Bloom’s Taxonomy

## 📌 Project Motivation

Manual question paper generation is:
- Time-consuming and repetitive.
- Hard to align with cognitive skill levels (Bloom’s Taxonomy).
- Prone to duplication and lacks standardization.

To address these issues, this project offers a **web-based AI-powered system** that:
- Automatically generates, classifies, and stores questions.
- Aligns them with Bloom’s Taxonomy levels.
- Provides customizable question papers.
- Supports reusability through a question bank.

> Designed by students of COEP Technological University under the guidance of Dr. Yashodhara V. Haribhakta.

---

## ✨ Features

### ✅ Core Functionalities
- **Question Generation**: Generate custom questions using **Google Gemini** LLM based on selected subject, topics, BT levels, and marks.
- **Bloom Level Prediction**: Predict cognitive level using a fine-tuned **DeBERTa-v3** model.
- **Hierarchical Storage**: Save questions to **Firestore** under Subject → Topic → Subtopic structure.
- **Similarity Detection**: Prevent duplicate questions using **SentenceTransformers (MPNet)** embeddings + **cosine similarity**.
- **PDF Upload & Extraction**: Upload previous year PDFs, extract and classify questions using **LlamaParse**.
- **Syllabus Management**: Upload syllabus and auto-extract topics & subtopics.
- **Export Formats**: Download generated papers in **PDF**, **DOCX**, or **TXT** formats.
- **Secure Login**: Supports **Firebase email/password** and **Google Sign-In**.

### 🧠 Advanced Capabilities
- Adaptive difficulty adjustment (easy/hard regeneration).
- Editable question list with inline Bloom level and similarity score preview.
- Question regeneration logic based on reuse, variation, or difficulty.
- REST-based Firestore integration with real-time sync.

---

## 🔧 Project Setup Instructions

### ⚙️ Prerequisites
- Python 3.10 (for compatibility with PyTorch/transformers)
- Git
- Chrome or any modern browser
- A Google account for Firebase

---

### 🧱 Step-by-Step Setup

#### 1. Clone the repository
```bash
git clone <your-repo-url>
cd <your-repo-folder>
```

#### 2. Create Virtual Environment
```bash
python -m venv venv
```

#### 3. Activate Virtual Environment

- **Windows CMD**
```bash
venv\Scripts\activate
```

- **PowerShell**
```bash
.\venv\Scripts\Activate.ps1
```

#### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

#### 5. 🔑 Download the DeBERTa Model
Download the pre-trained Bloom level classification model (`btech.pth`) from this Google Drive link and place it in the root directory:

👉 [Download Model from Google Drive](https://drive.google.com/your-model-link)

#### 6. 🔥 Create Firebase Project and Admin Key
1. Go to [Firebase Console](https://drive.google.com/drive/folders/1N6dMD3rkbqF1O5wOqF2GhCAzm0w_GDzV?usp=drive_link)
2. Create a new project.
3. Add a web app and enable **Authentication > Email/Password** and **Google Sign-In**.
4. Go to **Project Settings > Service Accounts**.
5. Click **Generate New Private Key**, download the `.json` file.


Update `app.py` to point to this key:
```python
cred = credentials.Certificate("firebase.json")
```

#### 7. Set API Key for Google Generative AI
Export your Gemini API key:
```bash
export GOOGLE_API_KEY=your_gemini_api_key
```

Or set it inside `app2.py`:
```python
api_key = "your_gemini_api_key"
```

---

## ▶️ Running the Project

```bash
python app2.py
```

Then open: [http://127.0.0.1:5000](http://127.0.0.1:5000)

---

## 📂 Module Breakdown

| Module | Description |
|--------|-------------|
| `app2.py` | Full Flask backend handling routes, PDF extraction, LLM logic, Firestore interactions, export, and session control |
| `questorage.py` | Handles classification, similarity scoring, mark estimation, and Firestore structure parsing |
| `templates/` | HTML templates for UI |
| `static/` | CSS, JS, and frontend assets |
| `fonts/` | Required TTF font files for PDF export |

---

## 📄 Key Functional Pages

| Page | Purpose |
|------|---------|
| `/login`, `/signup` | Secure user authentication |
| `/zeropage` | Dashboard (Upload PDF or Generate Paper) |
| `/datapage` | Upload & extract previous papers |
| `/secondpage` to `/thirdpage` | Configure paper generation |
| `/edit_questions` | Review, edit, and regenerate questions |
| `/download_page` | Export to PDF/DOCX/TXT |

---

## 🧪 Model Summary

| Model | Purpose | Framework |
|-------|---------|-----------|
| `DeBERTa-v3` | Bloom’s Taxonomy classification | PyTorch / HuggingFace |
| `Gemini 1.5 / 2.0` | Question generation & classification | Google Generative AI |
| `MPNet` | Semantic similarity | Sentence-Transformers |

---

## 📈 Future Enhancements

- AI-based answer key generation.
- Integration with LMS (e.g., Moodle).
- Visual analytics dashboard for BT-level distribution and PYP reuse.
- Support for diagram/code/math-based question types.

---

## 📬 Contact & Acknowledgement

This project is developed by:
- Yash Diwane (112103038)
- Yash Bongirwar (112103026)
- Devanshu Gupta (112103035)

Under the guidance of **Dr. Yashodhara V. Haribhakta**  
**COEP Technological University, Pune**
