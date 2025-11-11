import os
from flask import Flask, render_template, jsonify, send_from_directory

def create_app():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    app = Flask(__name__,
                template_folder=os.path.join(base_dir, 'templates'),
                static_folder=os.path.join(base_dir, 'static'))

    @app.route('/')
    def home():
        # Point to pages/index.html since your index.html is inside pages/ folder
        return render_template('pages/index.html')

    @app.route('/api/jobs')
    def get_jobs():
        return jsonify({'jobs': []})
    
    @app.route('/style.css')
    def serve_style():
        return send_from_directory(os.path.join(base_dir, 'static'), 'style.css')

    @app.route('/script.js')
    def serve_script():
        return send_from_directory(os.path.join(base_dir, 'static'), 'script.js')

    return app
