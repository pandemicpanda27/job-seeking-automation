from flask import Blueprint, render_template, session
from application.job_matcher import matched_job_cache
import os

bp = Blueprint('pages', __name__, template_folder='templates/pages')

@bp.route('/')
def home():
    return render_template('jobs.html')

@bp.route('/filtered-jobs')
def show_filtered_jobs():
    cache_key = session.get("matched_job_cache_key")
    matched_jobs = matched_job_cache.get(cache_key, [])
    print("🔑 Cache key:", cache_key)
    print("🧠 Matched jobs found:", len(matched_jobs))
    return render_template('filtered_jobs.html', jobs=matched_jobs)