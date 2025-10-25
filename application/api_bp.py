from flask import Blueprint, request, jsonify, session
from application.job_controller import fetch_all_jobs, job_cache
from werkzeug.utils import secure_filename
from application.resume_parser import ResumeParser, load_skills_from_excel
from application.job_matcher import match_jobs, matched_job_cache
import os
import uuid

api_bp = Blueprint('apis_bp', __name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
SKILLS_FILE = os.path.join(os.path.dirname(__file__), 'skills_dataset.xlsx')
ALLOWED_EXTENSIONS = {'pdf'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

print("Loading skills database...")
SKILLS_DB = load_skills_from_excel(SKILLS_FILE)
print(f"Loaded {len(SKILLS_DB)} skills")
resume_parser = ResumeParser(SKILLS_DB)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@api_bp.route('/api/job-search', methods=['GET'])
def search_jobs_api():
    try:
        query = request.args.get('query', default='Web Developer').strip()
        location = request.args.get('location', default='').strip()

        if not query:
            return jsonify({
                'success': False,
                'error': 'Job title is required',
                'message': 'Please enter a job title'
            }), 400

        last_query = session.get("last_query")
        last_location = session.get("last_location")
        if last_query == query and last_location == location:
            cache_key = session.get("job_cache_key")
            if cache_key and cache_key in job_cache:
                print("Using cached jobs")
                jobs = job_cache[cache_key]
                formatted_jobs = [{
                    'title': job.get('title', 'N/A'),
                    'company': job.get('company', 'N/A'),
                    'location': job.get('location', 'N/A'),
                    'url': job.get('link', '#'),
                    'portal': job.get('portal', 'Unknown'),
                    'description': f"Source: {job.get('portal', 'Unknown')}"
                } for job in jobs]

                return jsonify({
                    'success': True,
                    'jobs': formatted_jobs,
                    'count': len(formatted_jobs),
                    'message': f'Found {len(formatted_jobs)} cached jobs for {query}'
                })

        print(f"Searching for jobs: {query} in {location or 'Anywhere'}")
        jobs, cache_key = fetch_all_jobs(query, location)
        session["job_cache_key"] = cache_key
        session["last_query"] = query
        session["last_location"] = location

        formatted_jobs = [{
            'title': job.get('title', 'N/A'),
            'company': job.get('company', 'N/A'),
            'location': job.get('location', 'N/A'),
            'url': job.get('link', '#'),
            'portal': job.get('portal', 'Unknown'),
            'description': f"Source: {job.get('portal', 'Unknown')}"
        } for job in jobs]

        return jsonify({
            'success': True,
            'jobs': formatted_jobs,
            'count': len(formatted_jobs),
            'message': f'Found {len(formatted_jobs)} jobs for {query}'
        })
    except Exception as e:
        print(f"ERROR FETCHING JOBS: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to fetch jobs. Please try again later.'
        }), 500

@api_bp.route('/api/parse-resume', methods=['POST'])
def parse_resume():
    if 'resume' not in request.files:
        return jsonify({'success': False, 'error': 'No resume file provided'}), 400

    resume_file = request.files['resume']

    if not resume_file.filename:
        return jsonify({'success': False, 'error': 'No file selected'}), 400

    if not allowed_file(resume_file.filename):
        return jsonify({'success': False, 'error': 'Invalid file type. Please upload PDF files only.'}), 400

    filepath = None
    try:
        filename = f"{uuid.uuid4().hex}_{secure_filename(resume_file.filename)}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        resume_file.save(filepath)

        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Resume file was not saved: {filepath}")

        print(f"Parsing resume: {filename}")
        parsed_data = resume_parser.parse_resume(filepath)

        # Store resume text in session for semantic matching
        resume_text = resume_parser.extract_text_from_pdf(filepath)
        session["parsed_resume_text"] = resume_text

        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as delete_error:
                print(f"Failed to delete file: {delete_error}")

        return jsonify({
            'success': True,
            'data': {
                'email': parsed_data.get('Email'),
                'phone': parsed_data.get('Phone'),
                'skills': list(parsed_data.get('Skills', [])),
                'message': 'Resume parsed successfully'
            }
        })
    except Exception as e:
        print(f"Error parsing resume: {str(e)}")
        import traceback
        traceback.print_exc()

        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as delete_error:
                print(f"Cleanup failed: {delete_error}")

        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Error parsing resume'
        }), 500

@api_bp.route('/api/parse-resume/save-edits', methods=['POST'])
def save_resume_edits():
    data = request.get_json()
    email = data.get('email')
    phone = data.get('phone')
    skills = data.get('skills', [])

    print("Edited resume data received:")
    print("Email:", email)
    print("Phone:", phone)
    print("Skills:", skills)

    cache_key = session.get("job_cache_key")
    if not cache_key or cache_key not in job_cache:
        return jsonify({
            "error": "Job data not available",
            "message": "Job data not available. Please search for jobs before uploading your resume."
        }), 400

    all_jobs = job_cache[cache_key]
    resume_text = session.get("parsed_resume_text", "")

    matched_jobs = match_jobs(
        set(skills),
        all_jobs,
        matched_jobs_cache_key=cache_key,
        top_n=10,
        resume_text=resume_text
    )

    session["matched_job_cache_key"] = cache_key

    for job in matched_jobs:
        print(f"{job['title']} → Match Score: {job['match_score']}")

    return jsonify({
        'message': 'Edits saved and jobs matched successfully'
    }), 200
