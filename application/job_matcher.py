# job_matcher.py
import copy
from typing import List, Dict, Set
from cachetools import TTLCache
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

matched_job_cache = TTLCache(maxsize=500, ttl=1200)  # store matched jobs

def match_jobs(parsed_skills: Set[str], jobs: List[Dict], matched_jobs_cache_key: str, top_n: int = 10, resume_text: str = "") -> List[Dict]:
    matched_jobs = []

    # If resume text is available, use semantic similarity
    if resume_text.strip():
        job_descriptions = [job.get("description", "") for job in jobs]
        all_texts = [resume_text] + job_descriptions

        vectorizer = TfidfVectorizer()
        vectors = vectorizer.fit_transform(all_texts)

        resume_vector = vectors[0]
        job_vectors = vectors[1:]

        similarities = cosine_similarity(resume_vector, job_vectors).flatten()

        for idx, job in enumerate(jobs):
            job_copy = copy.deepcopy(job)
            job_copy["match_score"] = round(similarities[idx], 4)
            matched_jobs.append(job_copy)

        matched_jobs.sort(key=lambda x: x["match_score"], reverse=True)

    else:
        # Fallback to keyword matching if resume text is missing
        for job in jobs:
            jd = job.get("description", "").lower()
            score = sum(1 for skill in parsed_skills if skill.lower() in jd)

            job_copy = copy.deepcopy(job)
            job_copy["match_score"] = score
            matched_jobs.append(job_copy)

        matched_jobs.sort(key=lambda x: x["match_score"], reverse=True)

    top_matches = matched_jobs[:top_n]
    matched_job_cache[matched_jobs_cache_key] = top_matches
    return top_matches
