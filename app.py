# from flask import Flask, request, jsonify, render_template
# from werkzeug.utils import secure_filename
# import os
# from pathlib import Path
# import PyPDF2
# import docx
# from typing import Dict, List, Optional
# import json

# app = Flask(__name__)
# app.config['UPLOAD_FOLDER'] = 'uploads/resumes'
# app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
# app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'docx', 'txt'}

# Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)

# def allowed_file(filename: str) -> bool:
#     return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# def extract_text_from_pdf(filepath: str) -> str:
#     text = ""
#     with open(filepath, 'rb') as file:
#         pdf_reader = PyPDF2.PdfReader(file)
#         for page in pdf_reader.pages:
#             text += page.extract_text()
#     return text

# def extract_text_from_docx(filepath: str) -> str:
#     doc = docx.Document(filepath)
#     return "\n".join([paragraph.text for paragraph in doc.paragraphs])

# def extract_text_from_txt(filepath: str) -> str:
#     with open(filepath, 'r', encoding='utf-8') as file:
#         return file.read()

# def parse_resume(filepath: str, file_extension: str) -> Dict:
#     if file_extension == 'pdf':
#         text = extract_text_from_pdf(filepath)
#     elif file_extension == 'docx':
#         text = extract_text_from_docx(filepath)
#     else:
#         text = extract_text_from_txt(filepath)
    
#     return {
#         'raw_text': text,
#         'filepath': filepath,
#         'filename': os.path.basename(filepath)
#     }

# @app.route('/')
# def index():
#     return render_template('index.html')

# @app.route('/upload_resume', methods=['POST'])
# def upload_resume():
#     if 'resume' not in request.files:
#         return jsonify({'error': 'No file provided'}), 400
    
#     file = request.files['resume']
    
#     if file.filename == '':
#         return jsonify({'error': 'No file selected'}), 400
    
#     if file and allowed_file(file.filename):
#         filename = secure_filename(file.filename)
#         filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
#         file.save(filepath)
        
#         file_extension = filename.rsplit('.', 1)[1].lower()
#         parsed_data = parse_resume(filepath, file_extension)
        
#         return jsonify({
#             'success': True,
#             'message': 'Resume uploaded successfully',
#             'data': parsed_data
#         }), 200
    
#     return jsonify({'error': 'Invalid file type'}), 400

# @app.route('/trigger_agent', methods=['POST'])
# def trigger_agent():
#     data = request.json
#     resume_path = data.get('resume_path')
#     job_preferences = data.get('preferences', {})
    
#     if not resume_path or not os.path.exists(resume_path):
#         return jsonify({'error': 'Invalid resume path'}), 400
    
#     return jsonify({
#         'success': True,
#         'message': 'Agent triggered successfully',
#         'job_id': 'agent_task_001'
#     }), 200

# if __name__ == '__main__':
#     app.run(debug=True, port=5000)