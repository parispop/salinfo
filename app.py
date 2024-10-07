import os
import requests
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import PyPDF2
from docx import Document
from bs4 import BeautifulSoup
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

# Initialize Flask app and CORS
app = Flask(__name__)
CORS(app)

# SQLite Database setup
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
db = SQLAlchemy(app)

# Directory to temporarily save uploaded files
UPLOAD_FOLDER = '/tmp'
ALLOWED_EXTENSIONS = {'pdf', 'docx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Database Model
class UserData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    stored_url = db.Column(db.String(300), nullable=False)

# Create database tables before request
@app.before_request
def create_tables():
    db.create_all()

# Allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Extract text from PDF or DOCX file
def extract_text(file_path):
    file_extension = os.path.splitext(file_path)[1].lower()
    if file_extension == '.pdf':
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = "".join(page.extract_text() for page in reader.pages)
    elif file_extension == '.docx':
        doc = Document(file_path)
        text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
    else:
        raise ValueError("Unsupported file format")
    return text

# API to extract text from a file URL
@app.route('/extract', methods=['POST'])
def extract_text_from_url():
    url = request.json.get('url')
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    try:
        response = requests.get(url)
        response.raise_for_status()

        filename = secure_filename(os.path.basename(url))
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        with open(file_path, 'wb') as file:
            file.write(response.content)

        if not allowed_file(filename):
            os.remove(file_path)
            return jsonify({"error": "Unsupported file format"}), 400

        extracted_text = extract_text(file_path)
        os.remove(file_path)
        return jsonify({"text": extracted_text})

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Error downloading file: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": f"Error processing file: {str(e)}"}), 500

# API to extract and return HTML content from a URL
@app.route('/htmlextract', methods=['GET', 'POST'])
def extract_content():
    if request.method == 'POST':
        url = request.json.get('url')
    else:  # GET method
        url = request.args.get('url')
    
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        html_content = str(soup)
        return jsonify({"page_content": html_content})

    except requests.RequestException as e:
        return jsonify({"error": f"Error fetching URL: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": f"Error processing request: {str(e)}"}), 500

# API to store user data with ChatID, Name, Email, and storedURL
@app.route('/api/store', methods=['POST'])
def store_data():
    data = request.json
    user = UserData(chat_id=data['ChatID'], name=data['Name'], email=data['Email'], stored_url=data['storedURL'])
    db.session.add(user)
    db.session.commit()
    return jsonify({'message': 'Data stored successfully'}), 201

# API to retrieve stored URL by email
@app.route('/api/retrieve', methods=['GET'])
def retrieve_url():
    email = request.args.get('email')
    user = UserData.query.filter_by(email=email).first()
    if user:
        return jsonify({'storedURL': user.stored_url}), 200
    return jsonify({'error': 'User not found'}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=True)
