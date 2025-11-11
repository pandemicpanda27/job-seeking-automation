import os
from flask import Flask, render_template, jsonify, send_from_directory

def create_app():
    base_dir = os.path.dirname(os.path.abspath(__file__))  # Points to 'application/' dir
    
    app = Flask(__name__,
                template_folder=os.path.join(base_dir, 'templates'),
                static_folder=os.path.join(base_dir, 'static'))

    @app.route('/')
    def home():
        return render_template('index.html')

    @app.route('/api/jobs')
    def get_jobs():
        return jsonify({'jobs': []})
    
    # Serve CSS and JS without changing HTML, mapping /style.css and /script.js
    @app.route('/style.css')
    def serve_style():
        return send_from_directory(os.path.join(base_dir, 'static'), 'style.css')

    @app.route('/script.js')
    def serve_script():
        return send_from_directory(os.path.join(base_dir, 'static'), 'script.js')

    return app
