# real_job_scraper.py
import asyncio
import aiohttp
import logging
from typing import List, Dict
from datetime import datetime
from bs4 import BeautifulSoup
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RealJobScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.jobs = []
        
    async def scrape_indeed(self, job_title: str, location: str) -> List[Dict]:
        """Scrape jobs from Indeed"""
        jobs = []
        try:
            url = f"https://www.indeed.com/jobs?q={job_title}&l={location}&sort=date"
            response = requests.get(url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            for job_card in soup.find_all('div', class_='job_seen_beacon'):
                try:
                    title = job_card.find('h2', class_='jobTitle').get_text(strip=True)
                    company = job_card.find('span', {'data-testid': 'company-name'})
                    company_name = company.get_text(strip=True) if company else 'Unknown'
                    
                    loc = job_card.find('div', {'data-testid': 'text-location'})
                    job_location = loc.get_text(strip=True) if loc else location
                    
                    link_tag = job_card.find('h2', class_='jobTitle').find('a')
                    job_url = link_tag.get('href', '') if link_tag else ''
                    if job_url and not job_url.startswith('http'):
                        job_url = f"https://www.indeed.com{job_url}"
                    
                    posted_time = job_card.find('span', class_='date')
                    posted = posted_time.get_text(strip=True) if posted_time else 'Unknown'
                    
                    salary_elem = job_card.find('span', class_='salary-snippet')
                    salary = salary_elem.get_text(strip=True) if salary_elem else 'Not specified'
                    
                    jobs.append({
                        'title': title,
                        'company': company_name,
                        'location': job_location,
                        'url': job_url,
                        'posted': posted,
                        'salary': salary,
                        'source': 'Indeed',
                        'description': '',
                        'timestamp': datetime.now().isoformat()
                    })
                except Exception as e:
                    logger.debug(f"Error parsing Indeed job: {e}")
                    continue
            
            logger.info(f"Found {len(jobs)} jobs on Indeed")
        except Exception as e:
            logger.error(f"Error scraping Indeed: {e}")
        
        return jobs
    
    async def scrape_linkedin(self, job_title: str, location: str) -> List[Dict]:
        """Scrape jobs from LinkedIn"""
        jobs = []
        try:
            url = f"https://www.linkedin.com/jobs/search/?keywords={job_title}&location={location}&f_TPR=r604800&sortBy=DD"
            response = requests.get(url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            job_cards = soup.find_all('div', class_='base-card')
            for card in job_cards[:20]:
                try:
                    title_elem = card.find('h3', class_='base-search-card__title')
                    title = title_elem.get_text(strip=True) if title_elem else 'Unknown'
                    
                    company_elem = card.find('h4', class_='base-search-card__subtitle')
                    company = company_elem.get_text(strip=True) if company_elem else 'Unknown'
                    
                    location_elem = card.find('span', class_='job-search-card__location')
                    job_location = location_elem.get_text(strip=True) if location_elem else location
                    
                    link_elem = card.find('a', class_='base-card__full-link')
                    job_url = link_elem.get('href', '') if link_elem else ''
                    
                    jobs.append({
                        'title': title,
                        'company': company,
                        'location': job_location,
                        'url': job_url,
                        'posted': 'Unknown',
                        'salary': 'Not specified',
                        'source': 'LinkedIn',
                        'description': '',
                        'timestamp': datetime.now().isoformat()
                    })
                except Exception as e:
                    logger.debug(f"Error parsing LinkedIn job: {e}")
                    continue
            
            logger.info(f"Found {len(jobs)} jobs on LinkedIn")
        except Exception as e:
            logger.error(f"Error scraping LinkedIn: {e}")
        
        return jobs
    
    async def scrape_naukri(self, job_title: str, location: str) -> List[Dict]:
        """Scrape jobs from Naukri (India)"""
        jobs = []
        try:
            url = f"https://www.naukri.com/jobs-{job_title.replace(' ', '-')}-{location.replace(' ', '-')}"
            response = requests.get(url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            for job_card in soup.find_all('article', class_='jobTuple'):
                try:
                    title = job_card.find('a', class_='jobTitle').get_text(strip=True)
                    company = job_card.find('a', class_='companyName').get_text(strip=True)
                    job_location = job_card.find('span', class_='locWd').get_text(strip=True)
                    job_url = job_card.find('a', class_='jobTitle').get('href', '')
                    posted = job_card.find('span', class_='postDate').get_text(strip=True) if job_card.find('span', class_='postDate') else 'Unknown'
                    
                    jobs.append({
                        'title': title,
                        'company': company,
                        'location': job_location,
                        'url': job_url,
                        'posted': posted,
                        'salary': 'Not specified',
                        'source': 'Naukri',
                        'description': '',
                        'timestamp': datetime.now().isoformat()
                    })
                except Exception as e:
                    logger.debug(f"Error parsing Naukri job: {e}")
                    continue
            
            logger.info(f"Found {len(jobs)} jobs on Naukri")
        except Exception as e:
            logger.error(f"Error scraping Naukri: {e}")
        
        return jobs
    
    async def scrape_glassdoor(self, job_title: str, location: str) -> List[Dict]:
        """Scrape jobs from Glassdoor"""
        jobs = []
        try:
            url = f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={job_title}&locT=C&locId=1&jobType=all"
            response = requests.get(url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            for job_card in soup.find_all('li', class_='jl'):
                try:
                    title = job_card.find('a', class_='jobLink').get_text(strip=True)
                    company = job_card.find('a', class_='employerLink').get_text(strip=True)
                    job_url = job_card.find('a', class_='jobLink').get('href', '')
                    
                    jobs.append({
                        'title': title,
                        'company': company,
                        'location': location,
                        'url': job_url,
                        'posted': 'Unknown',
                        'salary': 'Not specified',
                        'source': 'Glassdoor',
                        'description': '',
                        'timestamp': datetime.now().isoformat()
                    })
                except Exception as e:
                    logger.debug(f"Error parsing Glassdoor job: {e}")
                    continue
            
            logger.info(f"Found {len(jobs)} jobs on Glassdoor")
        except Exception as e:
            logger.error(f"Error scraping Glassdoor: {e}")
        
        return jobs
    
    async def scrape_all_sources(self, job_title: str, location: str) -> List[Dict]:
        """Scrape from all sources concurrently"""
        tasks = [
            self.scrape_indeed(job_title, location),
            self.scrape_linkedin(job_title, location),
            self.scrape_naukri(job_title, location),
            self.scrape_glassdoor(job_title, location),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_jobs = []
        for result in results:
            if isinstance(result, list):
                all_jobs.extend(result)
        
        # Remove duplicates
        unique_jobs = {job['url']: job for job in all_jobs if job['url']}.values()
        
        logger.info(f"Total unique jobs found: {len(unique_jobs)}")
        return list(unique_jobs)
