import os
from flask import Flask, render_template, jsonify, send_from_directory, request
from application.resume_parser import ResumeParser

def create_app():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(root_dir)
    
    app = Flask(__name__,
                template_folder=os.path.join(parent_dir, 'templates'),
                static_folder=os.path.join(parent_dir, 'static'))
    
    @app.route('/')
    def home():
        return render_template('index.html')
    
    @app.route('/api/jobs')
    def get_jobs():
        return jsonify({'jobs': []})
    
    # Serve CSS and JS from static folder without modifying HTML
    @app.route('/style.css')
    def serve_style():
        return send_from_directory(os.path.join(os.path.dirname(__file__), '..', 'static'), 'style.css')
    
    @app.route('/script.js')
    def serve_script():
        return send_from_directory(os.path.join(os.path.dirname(__file__), '..', 'static'), 'script.js')
    
    # Resume parsing endpoint
    @app.route('/api/parse-resume', methods=['POST'])
    def parse_resume():
        try:
            if 'file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            # Save file temporarily
            temp_path = os.path.join('/tmp', file.filename)
            file.save(temp_path)
            
            # Parse resume
            parser = ResumeParser()
            result = parser.parse(temp_path)
            
            # Clean up
            os.remove(temp_path)
            
            return jsonify(result)
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return app
