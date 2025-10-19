from flask import Blueprint, request, jsonify
from application.job_controller import fetch_all_jobs

jobs_bp = Blueprint('jobs_bp', __name__)

@jobs_bp.route('/api/search-jobs', methods=['POST'])
def search_jobs():
    data = request.get_json()
    job_title = data.get('job_title', '').strip()
    location = data.get('location', '').strip()
    
    if not job_title:
        return jsonify({
            'success': False,
            'error': 'Job title is required',
            'message': 'Please enter a job title'
        }), 400
    
    try:
        print(f"Searching for jobs: {job_title} in {location}")
        jobs = fetch_all_jobs(job_title, location)
        
        formatted_jobs = []
        for job in jobs:
            formatted_jobs.append({
                'title': job.get('title', 'N/A'),
                'company': job.get('company', 'N/A'),
                'location': job.get('location', 'N/A'),
                'url': job.get('link', '#'),
                'portal': job.get('portal', 'Unknown'),
                'description': f"Source: {job.get('portal', 'Unknown')}"
            })
        
        return jsonify({
            'success': True,
            'jobs': formatted_jobs,
            'count': len(formatted_jobs),
            'message': f'Found {len(formatted_jobs)} jobs for {job_title}'
        })
    except Exception as e:
        print(f"Error searching for jobs: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Error searching for jobs. The scrapers may require browser drivers to be installed.'
        }), 500