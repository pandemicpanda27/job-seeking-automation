# job_matcher.py
from typing import Dict, List
import re
from difflib import SequenceMatcher

class JobMatcher:
    def __init__(self, resume_data: Dict):
        self.resume_data = resume_data
        self.skills = set(s.lower() for s in resume_data.get('skills', []))
        self.category = resume_data.get('category', '').lower()
        
    def calculate_match_percentage(self, job: Dict) -> float:
        """Calculate how well job matches resume (0-100)"""
        score = 0
        
        # Title match (30%)
        title_match = self._match_title(job.get('title', ''))
        score += title_match * 0.30
        
        # Skills match (40%)
        description = job.get('description', '') + ' ' + job.get('title', '')
        skills_match = self._match_skills(description)
        score += skills_match * 0.40
        
        # Category match (20%)
        category_match = self._match_category(job.get('title', ''))
        score += category_match * 0.20
        
        # Location match (10%)
        location_match = self._match_location(job.get('location', ''))
        score += location_match * 0.10
        
        return min(100, max(0, score))
    
    def _match_title(self, job_title: str) -> float:
        """Match job title with resume category"""
        job_title_lower = job_title.lower()
        if self.category in job_title_lower:
            return 100
        
        # Partial matching
        ratio = SequenceMatcher(None, self.category, job_title_lower).ratio()
        return ratio * 100
    
    def _match_skills(self, text: str) -> float:
        """Match skills found in job description"""
        text_lower = text.lower()
        matched_skills = 0
        
        for skill in self.skills:
            if re.search(r'\b' + re.escape(skill) + r'\b', text_lower, re.IGNORECASE):
                matched_skills += 1
        
        if len(self.skills) == 0:
            return 0
        
        return (matched_skills / len(self.skills)) * 100
    
    def _match_category(self, job_title: str) -> float:
        """Match job category"""
        job_title_lower = job_title.lower()
        category_keywords = self.category.split()
        
        matched = sum(1 for kw in category_keywords if kw in job_title_lower)
        return (matched / len(category_keywords)) * 100 if category_keywords else 0
    
    def _match_location(self, job_location: str) -> float:
        """Simple location match"""
        resume_location = self.resume_data.get('location', '').lower()
        job_location_lower = job_location.lower()
        
        if resume_location in job_location_lower or job_location_lower in resume_location:
            return 100
        return 0
