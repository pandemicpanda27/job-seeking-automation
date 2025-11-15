from fastapi import FastAPI, File, UploadFile, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from PyPDF2 import PdfReader
import re
import pickle
import nltk
from nltk import word_tokenize, pos_tag, ne_chunk
from nltk.tree import Tree

# Miscellaneous imports
import unicodedata
from typing import Optional, List
import asyncio
from datetime import datetime
import json
from pathlib import Path
import logging
import sys

#Selenium imports
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException,
    ElementClickInterceptedException,
    StaleElementReferenceException
)
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import time
import os

# If first run, uncomment and run once
# nltk.download('punkt')
# nltk.download('averaged_perceptron_tagger')
# nltk.download('maxent_ne_chunker')
# nltk.download('words')

# ===================== JOB AGENT CONFIGURATION ==========================
class JobAgentConfig:
    """Configuration for job application agent"""
    BASE_DIR = Path(__file__).parent
    LOGS_DIR = BASE_DIR / "logs" / "applications"
    RESUME_STORAGE = BASE_DIR / "resumes"
    
    DEFAULT_DELAY = 10
    MAX_APPLICATIONS_PER_SESSION = 20
    TIMEOUT = 15
    
    # Create directories
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    RESUME_STORAGE.mkdir(parents=True, exist_ok=True)

# Setup logging for job agent
job_agent_logger = logging.getLogger('job_agent')
job_agent_logger.setLevel(logging.INFO)

handler = logging.FileHandler(JobAgentConfig.LOGS_DIR / 'agent.log', encoding='utf-8')
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
job_agent_logger.addHandler(handler)

# Fix console encoding for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

app = FastAPI()

templates = Jinja2Templates(directory="templates")

# ===================== MODEL LOAD ==========================
rf_classifier_categorization = pickle.load(open('model/rf_classifier_categorization.pkl', 'rb'))
tfidf_vectorizer_categorization = pickle.load(open('model/tfidf_vectorizer_categorization.pkl', 'rb'))

# ===================== FORM FILLER UTILITY ==========================
class FormFiller:
    """Smart form filling utility"""
    
    FIELD_PATTERNS = {
        'full_name': [
            'name', 'full-name', 'fullname', 'full_name', 
            'applicant-name', 'applicantname', 'your-name'
        ],
        'first_name': [
            'first-name', 'firstname', 'first_name', 
            'fname', 'given-name', 'givenname'
        ],
        'last_name': [
            'last-name', 'lastname', 'last_name', 
            'lname', 'surname', 'family-name'
        ],
        'email': [
            'email', 'e-mail', 'email-address', 
            'emailaddress', 'mail', 'your-email'
        ],
        'phone': [
            'phone', 'telephone', 'mobile', 'contact',
            'phone-number', 'phonenumber', 'tel', 'cell'
        ],
        'resume': [
            'resume', 'cv', 'upload-resume', 'file', 
            'attachment', 'document'
        ],
    }
    
    @staticmethod
    def find_field(driver, field_type, timeout=5):
        """Find form field by multiple strategies"""
        patterns = FormFiller.FIELD_PATTERNS.get(field_type, [])
        
        for pattern in patterns:
            # Try by ID
            try:
                return driver.find_element(By.ID, pattern)
            except NoSuchElementException:
                pass
            
            # Try by name
            try:
                return driver.find_element(By.NAME, pattern)
            except NoSuchElementException:
                pass
            
            # Try by placeholder
            try:
                return driver.find_element(By.XPATH, f"//*[contains(@placeholder, '{pattern}')]")
            except NoSuchElementException:
                pass
            
            # Try partial match
            try:
                return driver.find_element(By.XPATH, f"//*[contains(@id, '{pattern}') or contains(@name, '{pattern}')]")
            except NoSuchElementException:
                pass
        
        return None
    
    @staticmethod
    def fill_field(element, value, clear_first=True):
        """Safely fill a form field"""
        try:
            if clear_first:
                element.clear()
            element.send_keys(value)
            return True
        except Exception as e:
            job_agent_logger.warning(f"Could not fill field: {str(e)}")
            return False
    
    @staticmethod
    def upload_file(element, file_path):
        """Upload file to input element"""
        try:
            abs_path = os.path.abspath(file_path)
            if not os.path.exists(abs_path):
                job_agent_logger.error(f"File not found: {abs_path}")
                return False
            element.send_keys(abs_path)
            return True
        except Exception as e:
            job_agent_logger.error(f"Could not upload file: {str(e)}")
            return False

# ===================== JOB APPLICATION AGENT ==========================
class JobApplicationAgent:
    """Main job application agent"""
    
    def __init__(self, candidate_data, resume_path, config=None):
        self.config = config or JobAgentConfig()
        self.candidate_data = candidate_data
        self.resume_path = Path(resume_path)
        self.driver = None
        self.applications_log = []
        self.form_filler = FormFiller()
        
    def setup_driver(self, headless=False):
        """Setup Chrome WebDriver"""
        options = webdriver.ChromeOptions()
        
        if headless:
            options.add_argument('--headless')
        
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.maximize_window()
        
        job_agent_logger.info("WebDriver initialized")
        
    def search_jobs_indeed(self, job_title=None, location=None, num_jobs=10):
        """Search for jobs on Indeed"""
        job_title = job_title or self.candidate_data.get('category', 'Teacher')
        location = location or 'United States'
        
        try:
            base_url = "https://www.indeed.com/jobs"
            params = {
                'q': job_title,
                'l': location,
                'fromage': '7',
                'sort': 'date'
            }
            
            query_string = '&'.join([f"{k}={v.replace(' ', '+')}" for k, v in params.items()])
            search_url = f"{base_url}?{query_string}"
            
            job_agent_logger.info(f"Searching Indeed: {job_title} in {location}")
            self.driver.get(search_url)
            time.sleep(3)
            
            wait = WebDriverWait(self.driver, self.config.TIMEOUT)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.job_seen_beacon")))
            
            job_listings = []
            job_cards = self.driver.find_elements(By.CSS_SELECTOR, "div.job_seen_beacon")
            
            for card in job_cards[:num_jobs]:
                try:
                    title_elem = card.find_element(By.CSS_SELECTOR, "h2.jobTitle a")
                    job_url = title_elem.get_attribute('href')
                    job_title_text = title_elem.text
                    
                    try:
                        company = card.find_element(By.CSS_SELECTOR, "span[data-testid='company-name']").text
                    except:
                        company = "Unknown"
                    
                    try:
                        loc = card.find_element(By.CSS_SELECTOR, "div[data-testid='text-location']").text
                    except:
                        loc = location
                    
                    job_listings.append({
                        'title': job_title_text,
                        'company': company,
                        'location': loc,
                        'url': job_url,
                        'platform': 'indeed'
                    })
                    
                except Exception as e:
                    continue
            
            job_agent_logger.info(f"Found {len(job_listings)} jobs on Indeed")
            return job_listings
            
        except Exception as e:
            job_agent_logger.error(f"Error searching Indeed: {str(e)}")
            return []
    
    def search_jobs_linkedin(self, job_title=None, location=None, num_jobs=10):
        """Search for jobs on LinkedIn"""
        job_title = job_title or self.candidate_data.get('category', 'Teacher')
        location = location or 'United States'
        
        try:
            base_url = "https://www.linkedin.com/jobs/search/"
            search_url = f"{base_url}?keywords={job_title.replace(' ', '%20')}&location={location.replace(' ', '%20')}&f_TPR=r604800&sortBy=DD"
            
            job_agent_logger.info(f"Searching LinkedIn: {job_title} in {location}")
            self.driver.get(search_url)
            time.sleep(4)
            
            for _ in range(3):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
            
            job_listings = []
            job_cards = self.driver.find_elements(By.CSS_SELECTOR, "div.base-card")
            
            for card in job_cards[:num_jobs]:
                try:
                    title_elem = None
                    title_selectors = [
                        "h3.base-search-card__title",
                        "h3.job-card-list__title",
                        "a.job-card-container__link"
                    ]
                    
                    for selector in title_selectors:
                        try:
                            title_elem = card.find_element(By.CSS_SELECTOR, selector)
                            if title_elem and title_elem.text.strip():
                                break
                        except:
                            continue
                    
                    if not title_elem or not title_elem.text.strip():
                        continue
                    
                    link_elem = None
                    link_selectors = [
                        "a.base-card__full-link",
                        "a.job-card-container__link"
                    ]
                    
                    for selector in link_selectors:
                        try:
                            link_elem = card.find_element(By.CSS_SELECTOR, selector)
                            if link_elem:
                                break
                        except:
                            continue
                    
                    if not link_elem:
                        continue
                    
                    job_url = link_elem.get_attribute('href')
                    job_title_text = title_elem.text
                    
                    company = "Unknown"
                    company_selectors = [
                        "h4.base-search-card__subtitle",
                        "a.job-card-container__company-name"
                    ]
                    for selector in company_selectors:
                        try:
                            comp_elem = card.find_element(By.CSS_SELECTOR, selector)
                            if comp_elem and comp_elem.text.strip():
                                company = comp_elem.text.strip()
                                break
                        except:
                            continue
                    
                    loc = location
                    location_selectors = [
                        "span.job-search-card__location",
                        ".job-card-container__metadata-item"
                    ]
                    for selector in location_selectors:
                        try:
                            loc_elem = card.find_element(By.CSS_SELECTOR, selector)
                            if loc_elem and loc_elem.text.strip():
                                loc = loc_elem.text.strip()
                                break
                        except:
                            continue
                    
                    job_listings.append({
                        'title': job_title_text,
                        'company': company,
                        'location': loc,
                        'url': job_url,
                        'platform': 'linkedin'
                    })
                    
                except Exception as e:
                    continue
            
            job_agent_logger.info(f"Found {len(job_listings)} jobs on LinkedIn")
            return job_listings
            
        except Exception as e:
            job_agent_logger.error(f"Error searching LinkedIn: {str(e)}")
            return []
    
    def fill_application_form(self):
        """Fill out job application form"""
        try:
            name = self.candidate_data.get('name', '')
            name_parts = name.split() if name else []
            first_name = name_parts[0] if name_parts else ''
            last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
            
            filled_fields = []
            
            # Try full name
            full_name_field = self.form_filler.find_field(self.driver, 'full_name')
            if full_name_field:
                if self.form_filler.fill_field(full_name_field, name):
                    filled_fields.append('full_name')
            else:
                # Try first/last separately
                first_name_field = self.form_filler.find_field(self.driver, 'first_name')
                if first_name_field and self.form_filler.fill_field(first_name_field, first_name):
                    filled_fields.append('first_name')
                
                last_name_field = self.form_filler.find_field(self.driver, 'last_name')
                if last_name_field and self.form_filler.fill_field(last_name_field, last_name):
                    filled_fields.append('last_name')
            
            # Fill email
            email_field = self.form_filler.find_field(self.driver, 'email')
            if email_field:
                email = self.candidate_data.get('email', '')
                if self.form_filler.fill_field(email_field, email):
                    filled_fields.append('email')
            
            # Fill phone
            phone_field = self.form_filler.find_field(self.driver, 'phone')
            if phone_field:
                phone = self.candidate_data.get('phone', '')
                if self.form_filler.fill_field(phone_field, phone):
                    filled_fields.append('phone')
            
            # Upload resume
            resume_field = self.form_filler.find_field(self.driver, 'resume')
            if resume_field:
                if self.form_filler.upload_file(resume_field, str(self.resume_path)):
                    filled_fields.append('resume')
            
            job_agent_logger.info(f"Filled fields: {', '.join(filled_fields)}")
            return len(filled_fields) > 0
            
        except Exception as e:
            job_agent_logger.error(f"Error filling form: {str(e)}")
            return False
    
    def handle_external_application(self, job_info):
        """Handle 'Apply on company site' redirects"""
        try:
            job_agent_logger.info("Detected external application - following redirect...")
            time.sleep(2)
            
            main_window = self.driver.current_window_handle
            
            if len(self.driver.window_handles) > 1:
                for handle in self.driver.window_handles:
                    if handle != main_window:
                        self.driver.switch_to.window(handle)
                        break
                
                job_agent_logger.info(f"Redirected to: {self.driver.current_url}")
                time.sleep(3)
                
                form_filled = self.fill_application_form()
                
                if form_filled:
                    submit_selectors = [
                        "//button[contains(text(), 'Submit')]",
                        "//button[contains(text(), 'Send')]",
                        "//input[@type='submit']",
                        "//button[@type='submit']",
                    ]
                    
                    for selector in submit_selectors:
                        try:
                            submit_btn = self.driver.find_element(By.XPATH, selector)
                            job_agent_logger.info("Ready to submit on external site")
                            
                            self.applications_log.append({
                                **job_info,
                                'timestamp': datetime.now().isoformat(),
                                'status': 'ready_to_submit_external',
                                'form_filled': True,
                                'external_url': self.driver.current_url
                            })
                            
                            self.driver.close()
                            self.driver.switch_to.window(main_window)
                            return True
                        except NoSuchElementException:
                            continue
                
                self.driver.close()
                self.driver.switch_to.window(main_window)
                return False
            else:
                job_agent_logger.info(f"Redirected to: {self.driver.current_url}")
                time.sleep(3)
                return self.fill_application_form()
                
        except Exception as e:
            job_agent_logger.error(f"Error handling external application: {str(e)}")
            try:
                self.driver.switch_to.window(main_window)
            except:
                pass
            return False
    
    def apply_to_job(self, job_info):
        """Apply to a specific job"""
        try:
            job_url = job_info['url']
            
            job_agent_logger.info(f"Applying to: {job_info['title']} at {job_info['company']}")
            
            self.driver.get(job_url)
            time.sleep(3)
            
            # Look for apply button with comprehensive selectors
            apply_button = None
            apply_selectors = [
                # Indeed-specific
                "//button[contains(text(), 'Apply now')]",
                "//a[contains(text(), 'Apply now')]",
                "//div[contains(@class, 'jobsearch-IndeedApplyButton')]//button",
                "//button[contains(@class, 'indeed-apply-button')]",
                
                # "Apply on company site"
                "//button[contains(text(), 'Apply on company site')]",
                "//a[contains(text(), 'Apply on company site')]",
                "//a[contains(@class, 'jobsearch-IndeedApplyButton')]",
                
                # Generic
                "//button[contains(translate(text(), 'APPLY', 'apply'), 'apply')]",
                "//a[contains(translate(text(), 'APPLY', 'apply'), 'apply')]",
                "//button[contains(@class, 'apply')]",
                "//button[contains(@id, 'apply')]",
                
                # Fallback
                "//*[@role='button' and contains(text(), 'pply')]",
                "//span[contains(text(), 'Apply')]/parent::button",
                "//span[contains(text(), 'Apply')]/parent::a",
            ]
            
            for selector in apply_selectors:
                try:
                    apply_button = self.driver.find_element(By.XPATH, selector)
                    break
                except NoSuchElementException:
                    continue
            
            if not apply_button:
                job_agent_logger.warning("No apply button found")
                job_agent_logger.debug(f"Current URL: {self.driver.current_url}")
                return False
            
            # Check if external application
            button_text = apply_button.text.lower()
            is_external = 'company site' in button_text or 'employer site' in button_text
            
            # Click apply button
            try:
                apply_button.click()
            except ElementClickInterceptedException:
                self.driver.execute_script("arguments[0].click();", apply_button)
            
            time.sleep(2)
            
            # Handle external vs internal
            if is_external:
                form_filled = self.handle_external_application(job_info)
            else:
                form_filled = self.fill_application_form()
            
            if not form_filled:
                job_agent_logger.warning("Could not fill form fields")
                return False
            
            # Look for submit button (DON'T click)
            submit_selectors = [
                "//button[contains(translate(text(), 'SUBMIT', 'submit'), 'submit')]",
                "//button[@type='submit']",
                "//input[@type='submit']",
                "//button[contains(text(), 'Send application')]",
            ]
            
            for selector in submit_selectors:
                try:
                    submit_btn = self.driver.find_element(By.XPATH, selector)
                    job_agent_logger.info("Application ready to submit (auto-submit disabled)")
                    
                    self.applications_log.append({
                        **job_info,
                        'timestamp': datetime.now().isoformat(),
                        'status': 'ready_to_submit',
                        'form_filled': True
                    })
                    
                    # UNCOMMENT TO AUTO-SUBMIT:
                    # submit_btn.click()
                    # job_agent_logger.info("Application submitted!")
                    
                    return True
                except NoSuchElementException:
                    continue
            
            job_agent_logger.warning("Could not find submit button")
            return False
            
        except Exception as e:
            job_agent_logger.error(f"Error applying to job: {str(e)}")
            return False
    
    def apply_to_jobs_batch(self, job_listings, delay=None):
        """Apply to multiple jobs"""
        delay = delay or self.config.DEFAULT_DELAY
        
        successful = 0
        failed = 0
        
        for i, job in enumerate(job_listings, 1):
            job_agent_logger.info(f"Processing job {i}/{len(job_listings)}")
            
            if self.apply_to_job(job):
                successful += 1
            else:
                failed += 1
                self.applications_log.append({
                    **job,
                    'timestamp': datetime.now().isoformat(),
                    'status': 'failed',
                    'form_filled': False
                })
            
            if i < len(job_listings):
                time.sleep(delay)
        
        job_agent_logger.info(f"Batch complete: {successful} ready, {failed} failed")
        return successful, failed
    
    def save_log(self):
        """Save application log"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.config.LOGS_DIR / f"applications_{timestamp}.json"
        
        with open(log_file, 'w') as f:
            json.dump({
                'candidate': self.candidate_data,
                'applications': self.applications_log,
                'summary': {
                    'total': len(self.applications_log),
                    'ready': sum(1 for a in self.applications_log if a.get('status') == 'ready_to_submit'),
                    'failed': sum(1 for a in self.applications_log if a.get('status') == 'failed')
                }
            }, f, indent=2)
        
        job_agent_logger.info(f"Log saved to: {log_file}")
        return str(log_file)
    
    def close(self):
        """Cleanup"""
        if self.driver:
            self.driver.quit()
            job_agent_logger.info("WebDriver closed")

# ===================== UTILITIES ===========================
def cleanResume(txt):
    cleanText = re.sub(r'http\S+\s', ' ', txt)
    cleanText = re.sub(r'RT|cc', ' ', cleanText)
    cleanText = re.sub(r'#\S+\s', ' ', cleanText)
    cleanText = re.sub(r'@\S+', ' ', cleanText)
    cleanText = re.sub(r'[%s]' % re.escape("""!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~"""), ' ', cleanText)
    cleanText = re.sub(r'[^\x00-\x7f]', ' ', cleanText)
    cleanText = re.sub(r'\s+', ' ', cleanText)
    return cleanText.strip()



def pdf_to_text(file):
    reader = PdfReader(file)
    text = ''
    for page in range(len(reader.pages)):
        content = reader.pages[page].extract_text()
        if content:
            text += content + '\n'
    return text


# ===================== MODEL PREDICTIONS ===========================
def predict_category(resume_text):
    resume_text = cleanResume(resume_text)
    resume_tfidf = tfidf_vectorizer_categorization.transform([resume_text])
    return rf_classifier_categorization.predict(resume_tfidf)[0]


# ===================== PARSING HELPERS ===========================
def extract_name_from_resume(text):
    """
    Smart name extraction that works for:
    - two-column resumes
    - resumes where contact info is on same line as name
    - uppercase or mixed-case names
    - resumes where the name line contains noise
    """

    # Normalize lines
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # Only look at first ~8 lines (where names usually are)
    top = lines[:8]

    # Remove lines that contain non-name stuff
    filtered = []
    for line in top:
        l = line.lower()
        if any(x in l for x in ["@", "email", "github", "linkedin", "phone", "+91", "contact", ".com"]):
            continue
        if re.search(r"\d", l):  # remove lines with digits
            continue
        filtered.append(line)

    # If filtering removed everything, use fallback
    if not filtered:
        filtered = top

    # Strategy 1 — Look for lines that look like names (2–4 alphabetic words)
    for line in filtered:
        words = line.split()
        if 2 <= len(words) <= 4 and all(re.match(r"^[A-Za-z][A-Za-z\.\-']*$", w) for w in words):
            return " ".join(w.capitalize() for w in words)

    # Strategy 2 — Find longest alphabetic-only line
    alphabetic_lines = []
    for line in filtered:
        if re.match(r"^[A-Za-z \-\.']+$", line):
            alphabetic_lines.append(line)

    if alphabetic_lines:
        best = max(alphabetic_lines, key=len)
        words = best.split()
        if 1 <= len(words) <= 5:
            return " ".join(w.capitalize() for w in words)

    # Strategy 3 — Take first 2 alphabetic words from the very first line
    words = re.findall(r"[A-Za-z]+", lines[0])
    if len(words) >= 2:
        return words[0].capitalize() + " " + words[1].capitalize()

    # Strategy 4 — As last fallback, return first non-empty line
    return lines[0]

def extract_email_from_resume(text):
    match = re.search(r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b', text)
    return match.group().strip() if match else None

def extract_contact_number_from_resume(text):
    """More permissive phone extraction:
       - Looks for lines with 'phone', 'tel', or common number formats
       - Returns cleaned version preserving country code if present
    """
    # Search for label-based phone first
    phone_label = re.search(r'(phone|tel|mobile|contact)[:\s]*([+\d\(\)\-\s\.]{7,})', text, re.I)
    if phone_label:
        candidate = phone_label.group(2)
        digits = re.sub(r'\D', '', candidate)
        if 7 <= len(digits) <= 15:
            # Return in readable format: original (trimmed)
            return candidate.strip()

    # Generic patterns
    patterns = [
        r'(\+?\d{1,3}[-\s\.]?\(?\d{2,4}\)?[-\s\.]?\d{3,4}[-\s\.]?\d{3,4})',  # flexible groups
        r'(\(?\d{3}\)?[-\s\.]?\d{3}[-\s\.]?\d{4})',  # (555) 345-6789 etc
        r'(\b\d{10}\b)',  # 10-digit
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            candidate = m.group(1)
            digits = re.sub(r'\D', '', candidate)
            if 7 <= len(digits) <= 15:
                return candidate.strip()
    return None

def get_section_text(text, header_names, stop_headers=None, window_chars=1500):
    if stop_headers is None:
        stop_headers = ['experience','work experience','skills','projects','certifications','publications']

    text_lower = text.lower()

    for header in header_names:
        idx = text_lower.find(header.lower())
        if idx != -1:
            start = idx + len(header)

            # Find nearest stop header
            stop_idx = len(text)
            for sh in stop_headers:
                sidx = text_lower.find(sh.lower(), start)
                if sidx != -1 and sidx < stop_idx:
                    stop_idx = sidx

            return text[start:stop_idx].strip()

    return None


# Full skill list (kept intact/expanded). If you want to keep the original huge list, paste it here.
FULL_SKILLS_LIST = [
        'Python', 'Data Analysis', 'Machine Learning', 'Communication', 'Project Management', 'Deep Learning', 'SQL',
        'Tableau',
        'Java', 'C++', 'JavaScript', 'HTML', 'CSS', 'React', 'Angular', 'Node.js', 'MongoDB', 'Express.js', 'Git',
        'Research', 'Statistics', 'Quantitative Analysis', 'Qualitative Analysis', 'SPSS', 'R', 'Data Visualization',
        'Matplotlib',
        'Seaborn', 'Plotly', 'Pandas', 'Numpy', 'Scikit-learn', 'TensorFlow', 'Keras', 'PyTorch', 'NLTK', 'Text Mining',
        'Natural Language Processing', 'Computer Vision', 'Image Processing', 'OCR', 'Speech Recognition',
        'Recommendation Systems',
        'Collaborative Filtering', 'Content-Based Filtering', 'Reinforcement Learning', 'Neural Networks',
        'Convolutional Neural Networks',
        'Recurrent Neural Networks', 'Generative Adversarial Networks', 'XGBoost', 'Random Forest', 'Decision Trees',
        'Support Vector Machines',
        'Linear Regression', 'Logistic Regression', 'K-Means Clustering', 'Hierarchical Clustering', 'DBSCAN',
        'Association Rule Learning',
        'Apache Hadoop', 'Apache Spark', 'MapReduce', 'Hive', 'HBase', 'Apache Kafka', 'Data Warehousing', 'ETL',
        'Big Data Analytics',
        'Cloud Computing', 'Amazon Web Services (AWS)', 'Microsoft Azure', 'Google Cloud Platform (GCP)', 'Docker',
        'Kubernetes', 'Linux',
        'Shell Scripting', 'Cybersecurity', 'Network Security', 'Penetration Testing', 'Firewalls', 'Encryption',
        'Malware Analysis',
        'Digital Forensics', 'CI/CD', 'DevOps', 'Agile Methodology', 'Scrum', 'Kanban', 'Continuous Integration',
        'Continuous Deployment',
        'Software Development', 'Web Development', 'Mobile Development', 'Backend Development', 'Frontend Development',
        'Full-Stack Development',
        'UI/UX Design', 'Responsive Design', 'Wireframing', 'Prototyping', 'User Testing', 'Adobe Creative Suite',
        'Photoshop', 'Illustrator',
        'InDesign', 'Figma', 'Sketch', 'Zeplin', 'InVision', 'Product Management', 'Market Research',
        'Customer Development', 'Lean Startup',
        'Business Development', 'Sales', 'Marketing', 'Content Marketing', 'Social Media Marketing', 'Email Marketing',
        'SEO', 'SEM', 'PPC',
        'Google Analytics', 'Facebook Ads', 'LinkedIn Ads', 'Lead Generation', 'Customer Relationship Management (CRM)',
        'Salesforce',
        'HubSpot', 'Zendesk', 'Intercom', 'Customer Support', 'Technical Support', 'Troubleshooting',
        'Ticketing Systems', 'ServiceNow',
        'ITIL', 'Quality Assurance', 'Manual Testing', 'Automated Testing', 'Selenium', 'JUnit', 'Load Testing',
        'Performance Testing',
        'Regression Testing', 'Black Box Testing', 'White Box Testing', 'API Testing', 'Mobile Testing',
        'Usability Testing', 'Accessibility Testing',
        'Cross-Browser Testing', 'Agile Testing', 'User Acceptance Testing', 'Software Documentation',
        'Technical Writing', 'Copywriting',
        'Editing', 'Proofreading', 'Content Management Systems (CMS)', 'WordPress', 'Joomla', 'Drupal', 'Magento',
        'Shopify', 'E-commerce',
        'Payment Gateways', 'Inventory Management', 'Supply Chain Management', 'Logistics', 'Procurement',
        'ERP Systems', 'SAP', 'Oracle',
        'Microsoft Dynamics', 'Tableau', 'Power BI', 'QlikView', 'Looker', 'Data Warehousing', 'ETL',
        'Data Engineering', 'Data Governance',
        'Data Quality', 'Master Data Management', 'Predictive Analytics', 'Prescriptive Analytics',
        'Descriptive Analytics', 'Business Intelligence',
        'Dashboarding', 'Reporting', 'Data Mining', 'Web Scraping', 'API Integration', 'RESTful APIs', 'GraphQL',
        'SOAP', 'Microservices',
        'Serverless Architecture', 'Lambda Functions', 'Event-Driven Architecture', 'Message Queues', 'GraphQL',
        'Socket.io', 'WebSockets'
                     'Ruby', 'Ruby on Rails', 'PHP', 'Symfony', 'Laravel', 'CakePHP', 'Zend Framework', 'ASP.NET', 'C#',
        'VB.NET', 'ASP.NET MVC', 'Entity Framework',
        'Spring', 'Hibernate', 'Struts', 'Kotlin', 'Swift', 'Objective-C', 'iOS Development', 'Android Development',
        'Flutter', 'React Native', 'Ionic',
        'Mobile UI/UX Design', 'Material Design', 'SwiftUI', 'RxJava', 'RxSwift', 'Django', 'Flask', 'FastAPI',
        'Falcon', 'Tornado', 'WebSockets',
        'GraphQL', 'RESTful Web Services', 'SOAP', 'Microservices Architecture', 'Serverless Computing', 'AWS Lambda',
        'Google Cloud Functions',
        'Azure Functions', 'Server Administration', 'System Administration', 'Network Administration',
        'Database Administration', 'MySQL', 'PostgreSQL',
        'SQLite', 'Microsoft SQL Server', 'Oracle Database', 'NoSQL', 'MongoDB', 'Cassandra', 'Redis', 'Elasticsearch',
        'Firebase', 'Google Analytics',
        'Google Tag Manager', 'Adobe Analytics', 'Marketing Automation', 'Customer Data Platforms', 'Segment',
        'Salesforce Marketing Cloud', 'HubSpot CRM',
        'Zapier', 'IFTTT', 'Workflow Automation', 'Robotic Process Automation (RPA)', 'UI Automation',
        'Natural Language Generation (NLG)',
        'Virtual Reality (VR)', 'Augmented Reality (AR)', 'Mixed Reality (MR)', 'Unity', 'Unreal Engine', '3D Modeling',
        'Animation', 'Motion Graphics',
        'Game Design', 'Game Development', 'Level Design', 'Unity3D', 'Unreal Engine 4', 'Blender', 'Maya',
        'Adobe After Effects', 'Adobe Premiere Pro',
        'Final Cut Pro', 'Video Editing', 'Audio Editing', 'Sound Design', 'Music Production', 'Digital Marketing',
        'Content Strategy', 'Conversion Rate Optimization (CRO)',
        'A/B Testing', 'Customer Experience (CX)', 'User Experience (UX)', 'User Interface (UI)', 'Persona Development',
        'User Journey Mapping', 'Information Architecture (IA)',
        'Wireframing', 'Prototyping', 'Usability Testing', 'Accessibility Compliance', 'Internationalization (I18n)',
        'Localization (L10n)', 'Voice User Interface (VUI)',
        'Chatbots', 'Natural Language Understanding (NLU)', 'Speech Synthesis', 'Emotion Detection',
        'Sentiment Analysis', 'Image Recognition', 'Object Detection',
        'Facial Recognition', 'Gesture Recognition', 'Document Recognition', 'Fraud Detection',
        'Cyber Threat Intelligence', 'Security Information and Event Management (SIEM)',
        'Vulnerability Assessment', 'Incident Response', 'Forensic Analysis', 'Security Operations Center (SOC)',
        'Identity and Access Management (IAM)', 'Single Sign-On (SSO)',
        'Multi-Factor Authentication (MFA)', 'Blockchain', 'Cryptocurrency', 'Decentralized Finance (DeFi)',
        'Smart Contracts', 'Web3', 'Non-Fungible Tokens (NFTs)',
        # Culinary Chef
    "Cooking", "Food Preparation", "Menu Planning", "Food Safety", "Hygiene",
    "Baking", "Knife Skills", "Inventory Management", "Plating", "Presentation",
    "Recipe Development", "Team Leadership",
    
    # Elementary School Teacher
    "Lesson Planning", "Classroom Management", "Curriculum Development", "Student Assessment",
    "Communication Skills", "Educational Technology", "Creativity", "Storytelling",
    "Conflict Resolution", "Child Engagement",
    
    # Executive Assistant
    "Calendar Management", "Scheduling", "Email Management", "Travel Planning",
    "Communication Skills", "Report Preparation", "Event Coordination", "Organization",
    "MS Office", "Google Suite", "Multitasking",
    
    # Registered Nurse
    "Patient Care", "Vital Signs Monitoring", "Medication Administration", "Emergency Response",
    "Wound Care", "Health Assessment", "Medical Documentation", "Communication Skills",
    "Teamwork", "Clinical Procedures"
]

def extract_skills_from_resume(text, name=None):
    """
    Extract skills but ignore the top header where name/contact typically appears,
    and also remove any skills that accidentally match the candidate's name.
    """
    lines = text.strip().split('\n')
    # ignore top lines (first 6) to avoid name leaking in skills
    body = '\n'.join(lines[6:]) if len(lines) > 6 else text

    found = []
    for skill in FULL_SKILLS_LIST:
        # use word boundary match to reduce partial matches
        if re.search(r'\b' + re.escape(skill) + r'\b', body, re.IGNORECASE):
            found.append(skill)

    # Remove any found that are part of the candidate name
    if name:
        for token in name.split():
            found = [s for s in found if token.lower() not in s.lower()]

    # Final cleaning: unique, preserve original casing from list
    unique_found = []
    for s in FULL_SKILLS_LIST:
        if s in found and s not in unique_found:
            unique_found.append(s)
    return unique_found

# ===================== EDUCATION EXTRACTION ===========================
# Degree normalization map (regex pattern -> normalized label)
DEGREE_PATTERNS = {
    r'\bbachelor of technology\b': 'B.Tech',
    r'\bb\.?\s*tech\b': 'B.Tech',
    r'\bbachelor of engineering\b': 'B.E',
    r'\bb\.?\s*e\b': 'B.E',
    r'\bbachelor of science\b': 'B.Sc',
    r'\bb\.?\s*sc\b': 'B.Sc',
    r'\bbachelor of arts\b': 'B.A',
    r'\bb\.?\s*a\b': 'B.A',
    r'\bbachelor of commerce\b': 'B.Com',
    r'\bb\.?\s*com\b': 'B.Com',
    r'\bbachelor of computer applications\b': 'BCA',
    r'\bb\.?\s*c\.?a\b': 'BCA',
    r'\bbachelor of business administration\b': 'BBA',
    r'\bb\.?\s*b\.?\s*a\b': 'BBA',

    # Masters
    r'\bmaster of technology\b': 'M.Tech',
    r'\bm\.?\s*tech\b': 'M.Tech',
    r'\bmaster of science\b': 'M.Sc',
    r'\bm\.?\s*sc\b': 'M.Sc',
    r'\bmaster of business administration\b': 'MBA',
    r'\bm\.?\s*b\.?\s*a\b': 'MBA',
    r'\bmaster of engineering\b': 'M.E',
    r'\bm\.?\s*e\b': 'M.E',
    r'\bmaster of computer applications\b': 'MCA',
    r'\bm\.?\s*c\.?\s*a\b': 'MCA',

    # Diplomas
    r'\bpg diploma\b': 'PG Diploma',
    r'\bpost[- ]graduate diploma\b': 'PG Diploma',
    r'\bdiploma\b': 'Diploma',

    # Doctorate
    r'\bph\.?\s*d\b': 'Ph.D',
    r'\bp\.?\s*hd\b': 'Ph.D',

    # Medical
    r'\bmbbs\b': 'MBBS',
}

# fields list (common fields)
FIELD_KEYWORDS = [
    # 🧑‍💻 Computer Science & IT
    'Computer Science', 'Information Technology', 'Software Engineering', 'Computer Engineering',
    'Artificial Intelligence', 'Machine Learning', 'Deep Learning', 'Data Science', 'Data Analytics',
    'Data Engineering', 'Big Data Analytics', 'Cloud Computing', 'Cybersecurity', 'Information Security',
    'Network Security', 'Blockchain Technology', 'Internet of Things (IoT)', 'Web Development',
    'Mobile App Development', 'Game Development', 'Virtual Reality', 'Augmented Reality',
    'Human-Computer Interaction', 'Digital Forensics', 'Robotics', 'Automation',

    # ⚙️ Engineering & Technology
    'Electrical Engineering', 'Electronics Engineering', 'Electronics and Communication Engineering',
    'Mechanical Engineering', 'Civil Engineering', 'Chemical Engineering', 'Aerospace Engineering',
    'Automotive Engineering', 'Industrial Engineering', 'Instrumentation Engineering', 'Mechatronics Engineering',
    'Systems Engineering', 'Environmental Engineering', 'Biomedical Engineering', 'Marine Engineering',
    'Petroleum Engineering', 'Structural Engineering', 'Metallurgical Engineering', 'Textile Engineering',
    'Production Engineering', 'Power Engineering', 'Nanotechnology',

    # 📊 Business, Management & Finance
    'Business Administration', 'Management', 'Finance', 'Accounting', 'Banking', 'Economics', 'Commerce',
    'Marketing', 'Human Resource Management', 'Supply Chain Management', 'Logistics', 'Operations Management',
    'Project Management', 'International Business', 'Entrepreneurship', 'Business Analytics',
    'Investment Management', 'Risk Management', 'Corporate Finance', 'Taxation', 'Actuarial Science',

    # 🧠 Science & Mathematics
    'Physics', 'Chemistry', 'Mathematics', 'Statistics', 'Applied Mathematics', 'Environmental Science',
    'Earth Science', 'Geology', 'Oceanography', 'Meteorology', 'Astronomy', 'Biophysics', 'Biochemistry',
    'Microbiology', 'Molecular Biology', 'Biotechnology', 'Zoology', 'Botany', 'Genetics', 'Life Sciences',
    'Nanoscience', 'Forensic Science', 'Agricultural Science', 'Food Technology', 'Horticulture', 'Forestry',

    # 🩺 Medical & Health Sciences
    'Medicine', 'Dentistry', 'Pharmacy', 'Nursing', 'Physiotherapy', 'Public Health', 'Biomedical Science',
    'Veterinary Science', 'Nutrition and Dietetics', 'Occupational Therapy', 'Radiology', 'Pathology',
    'Anatomy', 'Physiology', 'Medical Microbiology', 'Epidemiology', 'Paramedical Science', 'Ayurveda',
    'Homeopathy', 'Medical Technology',

    # 🧬 Life Sciences & Biological Sciences
    'Biology', 'Biotechnology', 'Bioinformatics', 'Biostatistics', 'Marine Biology', 'Ecology',
    'Environmental Biology', 'Genetics', 'Immunology', 'Molecular Biology', 'Neuroscience', 'Pharmacology',
    'Toxicology',

    # 🧑‍🏫 Education, Arts & Humanities
    'Education', 'Teaching', 'Psychology', 'Sociology', 'Political Science', 'Public Administration',
    'History', 'Geography', 'Philosophy', 'Anthropology', 'Archaeology', 'Library Science', 'Linguistics',
    'English Literature', 'Foreign Languages', 'Journalism', 'Mass Communication', 'Fine Arts',
    'Performing Arts', 'Visual Arts', 'Graphic Design', 'Animation', 'Film Studies', 'Music', 'Theatre',
    'Creative Writing', 'Cultural Studies',

    # 🧱 Architecture, Design & Planning
    'Architecture', 'Interior Design', 'Urban Planning', 'Landscape Architecture', 'Construction Management',
    'Structural Design', 'Industrial Design', 'Product Design', 'Fashion Design', 'Textile Design',
    'User Experience Design', 'User Interface Design',

    # ⚖️ Law, Policy & Governance
    'Law', 'Constitutional Law', 'International Law', 'Corporate Law', 'Criminal Law', 'Human Rights Law',
    'Political Science', 'Public Policy', 'Governance', 'Criminology', 'Forensic Investigation',
    'Defense Studies', 'Security Studies',

    # 🌍 Social Sciences & Development Studies
    'Economics', 'Development Studies', 'Social Work', 'Gender Studies', 'International Relations',
    'Rural Development', 'Urban Studies', 'Demography', 'Peace and Conflict Studies',

    # 💼 Emerging & Interdisciplinary Fields
    'Artificial Intelligence and Robotics', 'Cognitive Science', 'Sustainability Studies', 'Climate Science',
    'Renewable Energy', 'Disaster Management', 'Energy Systems', 'Human Factors Engineering',
    'Digital Transformation', 'Industrial Automation', 'FinTech', 'Health Informatics', 'Sports Science',
    'Behavioral Economics'
    
    # Culinary Chef
    "Culinary Arts", "Professional Cooking", "Gastronomy", "Food Science",
    "Baking and Pastry", "Hospitality Management", "Chef Certification",
    
    # Elementary School Teacher
    "Bachelor of Education", "B.Ed", "Elementary Education", "Early Childhood Education",
    "Teaching Certification", "Child Development",
    
    # Executive Assistant
    "Business Administration", "Office Management", "Secretarial Studies",
    "Management Studies", "Administrative Studies", "Certified Administrative Professional", "CAP",
    
    # Registered Nurse
    "Nursing", "Bachelor of Science in Nursing", "B.Sc Nursing", "Associate Degree in Nursing", "ADN",
    "Diploma in Nursing", "RN License", "Registered Nurse", "Nursing Certification", "BLS", "ACLS"
]

INSTITUTION_PATTERNS = [r'\bUniversity\b', r'\bInstitute\b', r'\bCollege\b', r'\bSchool\b', r'\bInstitute of\b', r'\bUniversity of\b']

def clean_pdf_text(text):
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\xa0", " ").replace("\u200b", "")
    text = re.sub(r"[ ]{2,}", " ", text)
    return text.strip()
# ----------------------------
# Fuzzy header detection
# ----------------------------
def fuzzy_header_regex(header):
    return r"\s*".join(list(header.strip()))

def get_section_text(text, header_names, stop_headers=None, window_chars=900):
    if stop_headers is None:
        stop_headers = [
            'experience', 'work experience', 'professional experience',
            'skills', 'projects', 'certifications', 'achievements',
            'publications', 'internships'
        ]

    text_clean = clean_pdf_text(text.lower())

    # Try to locate header using fuzzy search
    for header in header_names:
        pattern = r"\b" + fuzzy_header_regex(header.lower()) + r"\b"
        match = re.search(pattern, text_clean, re.I)
        if match:
            start = match.end()

            stop_pos = len(text_clean)
            for sh in stop_headers:
                sh_pat = r"\b" + fuzzy_header_regex(sh.lower()) + r"\b"
                m2 = re.search(sh_pat, text_clean[start:], re.I)
                if m2:
                    pos = start + m2.start()
                    if pos < stop_pos:
                        stop_pos = pos

            slice_end = min(stop_pos, start + window_chars)
            return text[start:slice_end]

    return None

# ----------------------------
# Normalize Degree
# ----------------------------
def normalize_degree_from_text(s):
    s_lower = s.lower()
    for pat, label in DEGREE_PATTERNS.items():
        if re.search(pat, s_lower, re.I):
            return label
    return None

# ----------------------------
# Extract Institution
# ----------------------------
def extract_institution(entry_clean):
    """
    Extract academic institutions reliably from education blocks.
    Works for long names, multi-word names, and names before OR after degree.
    """

    patterns = [
        r"[A-Z][A-Za-z0-9&\.,\-\s]{4,}College of [A-Za-z\s]+",
        r"[A-Z][A-Za-z0-9&\.,\-\s]{4,}Institute of [A-Za-z\s]+",
        r"[A-Z][A-Za-z0-9&\.,\-\s]{4,}University of [A-Za-z\s]+",
        r"[A-Z][A-Za-z0-9&\.,\-\s]{4,}University\b",
        r"[A-Z][A-Za-z0-9&\.,\-\s]{4,}College\b",
        r"[A-Z][A-Za-z0-9&\.,\-\s]{4,}Institute\b",
        r"IIT [A-Za-z]+",
        r"NIT [A-Za-z]+",
        r"BITS [A-Za-z]+",
    ]

    # First, search for full institution name patterns
    for pat in patterns:
        m = re.search(pat, entry_clean, re.I)
        if m:
            return m.group(0).strip(" ,.-")

    # SECOND PASS → handle cases where the institution is BEFORE the degree block
    words = entry_clean.split()
    for i in range(len(words) - 2):
        chunk = " ".join(words[i:i+5])
        if any(kw in chunk.lower() for kw in ["college", "university", "institute", "school"]):
            return chunk.strip(" ,.-")

    return None


def fix_broken_pdf_lines(text):
    """
    PDFs sometimes break every word into its own line.
    This fixes that by joining short lines into full sentences.
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    combined = []
    buffer = ""

    for line in lines:
        # If the line is very short (1–2 words), append to buffer
        if len(line.split()) <= 2:
            buffer += " " + line
        else:
            # If buffer has content, flush it
            if buffer.strip():
                combined.append(buffer.strip())
                buffer = ""
            combined.append(line)

    # Flush remaining buffer
    if buffer.strip():
        combined.append(buffer.strip())

    return "\n".join(combined)


# ----------------------------
# MAIN FUNCTION: extract_education_from_resume()
# ----------------------------
def extract_education_from_resume(text):

    # Get education section
    section = get_section_text(text, ['education', 'educational qualification', 'academic qualification'])

    if not section:
        section = text

    # Split into degree-based chunks
    chunks = re.split(r'(?<!\w)(Bachelor|Master|B\.|M\.)', section, flags=re.I)
    merged = []
    for i in range(1, len(chunks), 2):
        merged.append(chunks[i] + chunks[i+1])

    if not merged:
        merged = [section]

    results = []
    seen = set()

    for entry in merged:

        # Clean entry
        entry_clean = " ".join(entry.split())

        # -------- Fix broken PDF words --------
        entry_clean = re.sub(r"Machine\s+Le(?!arning)", "Machine Learning", entry_clean, flags=re.I)
        entry_clean = re.sub(
            r"Artificial\s+Intelligence\s*(?:&|and)?\s*Machine",
            "Artificial Intelligence and Machine",
            entry_clean,
            flags=re.I
        )

        # -------- Detect degree --------
        degree = normalize_degree_from_text(entry_clean)
        if not degree:
            continue

        # -------- Detect field --------
        invalid_field_words = ["technology"]   # avoid picking "Technology" from "Bachelor of Technology"
        field = None

        # CASE 1 — explicit "in field"
        m_field = re.search(r'\b(?:in|of)\s+([A-Za-z &\.\-\/]{2,60})', entry_clean, re.I)
        if m_field:
            field_candidate = m_field.group(1).strip(" ,.")
            field = field_candidate

        else:
            # CASE 2 — match keywords
            for fk in FIELD_KEYWORDS:
                fk_low = fk.lower()
                if fk_low in entry_clean.lower() and fk_low not in invalid_field_words:
                    field = fk.title()
                    break

        # -------- Detect institution --------
        inst = extract_institution(entry_clean)

        # If institution TEXT appears BEFORE the degree text, discard it
        # (It likely belongs to 12th/10th qualification)
        if inst:
            degree_pos = entry_clean.lower().find(degree.lower())
            inst_pos = entry_clean.lower().find(inst.lower())
            if inst_pos < degree_pos:
                inst = None

        # -------- Detect year --------
        year = None
        y = re.search(r'(19|20)\d{2}', entry_clean)
        if y:
            year = y.group()

        # -------- Build final string --------
        final = degree
        if field:
            final += f" in {field}"
        if inst:
            final += f" | {inst}"
        if year:
            final += f" ({year})"

        # -------- Deduplicate --------
        key = final.lower()
        if key not in seen:
            seen.add(key)
            results.append(final)

    return results if results else None

# ===================== FASTAPI ROUTES ===========================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("resumes.html", {"request": request})


@app.post("/pred", response_class=HTMLResponse)
async def pred(request: Request, resume: UploadFile = File(...)):
    filename = resume.filename

    if filename.lower().endswith(".pdf"):
        text = pdf_to_text(resume.file)
    elif filename.lower().endswith(".txt"):
        text = (await resume.read()).decode("utf-8")
    else:
        return templates.TemplateResponse("resumes.html", {
            "request": request,
            "message": "Invalid file format. Please upload PDF or TXT."
        })

    predicted_category = predict_category(text)

    name = extract_name_from_resume(text)
    email = extract_email_from_resume(text)
    phone = extract_contact_number_from_resume(text)
    extracted_education = extract_education_from_resume(text)
    extracted_skills = extract_skills_from_resume(text, name=name)

    return templates.TemplateResponse("resumes.html", {
        "request": request,
        "predicted_category": predicted_category,
        "name": name,
        "email": email,
        "phone": phone,
        "extracted_skills": extracted_skills,
        "extracted_education": extracted_education
    })


@app.post("/api/parse")
async def api_parse(resume: UploadFile = File(...)):
    filename = resume.filename

    if filename.lower().endswith(".pdf"):
        text = pdf_to_text(resume.file)
    elif filename.lower().endswith(".txt"):
        text = (await resume.read()).decode("utf-8")
    else:
        return JSONResponse({"error": "Invalid file format. Upload PDF or TXT."})

    predicted_category = predict_category(text)

    name = extract_name_from_resume(text)
    email = extract_email_from_resume(text)
    phone = extract_contact_number_from_resume(text)
    extracted_education = extract_education_from_resume(text)
    extracted_skills = extract_skills_from_resume(text, name=name)

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "category": predicted_category,
        "skills": extracted_skills,
        "education": extracted_education
    }

# ===================== JOB AGENT API ENDPOINTS ==========================

@app.post("/api/search-jobs")
async def search_jobs(
    resume: UploadFile = File(...),
    job_title: Optional[str] = Form(None),
    location: Optional[str] = Form("United States"),
    num_jobs: int = Form(10),
    platforms: str = Form("indeed")  # comma-separated: "indeed,linkedin"
):
    """Search for jobs based on resume"""
    try:
        # Parse resume
        filename = resume.filename
        if filename.lower().endswith(".pdf"):
            text = pdf_to_text(resume.file)
        elif filename.lower().endswith(".txt"):
            text = (await resume.read()).decode("utf-8")
        else:
            return JSONResponse({"error": "Invalid file format"}, status_code=400)
        
        # Extract candidate data
        candidate_data = {
            'name': extract_name_from_resume(text),
            'email': extract_email_from_resume(text),
            'phone': extract_contact_number_from_resume(text),
            'category': predict_category(text),
            'skills': extract_skills_from_resume(text),
            'education': extract_education_from_resume(text)
        }
        
        # Save resume temporarily
        resume_filename = f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        resume_path = JobAgentConfig.RESUME_STORAGE / resume_filename
        
        with open(resume_path, 'wb') as f:
            await resume.seek(0)
            f.write(await resume.read())
        
        # Initialize agent
        agent = JobApplicationAgent(candidate_data, resume_path)
        agent.setup_driver(headless=True)
        
        try:
            job_title_search = job_title or candidate_data.get('category')
            all_jobs = []
            
            platform_list = [p.strip().lower() for p in platforms.split(',')]
            
            if 'indeed' in platform_list:
                indeed_jobs = agent.search_jobs_indeed(job_title_search, location, num_jobs)
                all_jobs.extend(indeed_jobs)
            
            if 'linkedin' in platform_list:
                linkedin_jobs = agent.search_jobs_linkedin(job_title_search, location, num_jobs)
                all_jobs.extend(linkedin_jobs)
            
            return {
                "candidate": candidate_data,
                "jobs_found": len(all_jobs),
                "jobs": all_jobs,
                "resume_id": resume_filename
            }
            
        finally:
            agent.close()
            
    except Exception as e:
        job_agent_logger.error(f"Error searching jobs: {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/apply-jobs")
async def apply_jobs(
    background_tasks: BackgroundTasks,
    resume: UploadFile = File(...),
    job_urls: str = Form(...),  # Comma-separated URLs
    job_title: Optional[str] = Form(None),
    location: Optional[str] = Form("United States"),
    delay: int = Form(10)
):
    """Apply to specific jobs"""
    try:
        # Parse resume
        filename = resume.filename
        if filename.lower().endswith(".pdf"):
            text = pdf_to_text(resume.file)
        elif filename.lower().endswith(".txt"):
            text = (await resume.read()).decode("utf-8")
        else:
            return JSONResponse({"error": "Invalid file format"}, status_code=400)
        
        # Extract candidate data
        candidate_data = {
            'name': extract_name_from_resume(text),
            'email': extract_email_from_resume(text),
            'phone': extract_contact_number_from_resume(text),
            'category': predict_category(text),
            'skills': extract_skills_from_resume(text),
            'education': extract_education_from_resume(text)
        }
        
        # Save resume
        resume_filename = f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        resume_path = JobAgentConfig.RESUME_STORAGE / resume_filename
        
        with open(resume_path, 'wb') as f:
            await resume.seek(0)
            f.write(await resume.read())
        
        # Parse job URLs
        urls = [url.strip() for url in job_urls.split(',') if url.strip()]
        
        if not urls:
            return JSONResponse({"error": "No job URLs provided"}, status_code=400)
        
        # Create job listings
        job_listings = []
        for url in urls:
            job_listings.append({
                'title': 'Job Application',
                'company': 'Unknown',
                'location': location,
                'url': url,
                'platform': 'custom'
            })
        
        # Initialize agent
        agent = JobApplicationAgent(candidate_data, resume_path)
        agent.setup_driver(headless=True)
        
        try:
            successful, failed = agent.apply_to_jobs_batch(job_listings, delay)
            log_file = agent.save_log()
            
            return {
                "candidate": candidate_data,
                "total_applications": len(job_listings),
                "successful": successful,
                "failed": failed,
                "log_file": log_file,
                "applications": agent.applications_log
            }
            
        finally:
            agent.close()
            
    except Exception as e:
        job_agent_logger.error(f"Error applying to jobs: {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/auto-apply")
async def auto_apply(
    background_tasks: BackgroundTasks,
    resume: UploadFile = File(...),
    job_title: Optional[str] = Form(None),
    location: Optional[str] = Form("United States"),
    num_jobs: int = Form(5),
    platforms: str = Form("indeed"),
    delay: int = Form(10)
):
    """Search and apply to jobs automatically"""
    try:
        # Parse resume
        filename = resume.filename
        if filename.lower().endswith(".pdf"):
            text = pdf_to_text(resume.file)
        elif filename.lower().endswith(".txt"):
            text = (await resume.read()).decode("utf-8")
        else:
            return JSONResponse({"error": "Invalid file format"}, status_code=400)
        
        # Extract candidate data
        candidate_data = {
            'name': extract_name_from_resume(text),
            'email': extract_email_from_resume(text),
            'phone': extract_contact_number_from_resume(text),
            'category': predict_category(text),
            'skills': extract_skills_from_resume(text),
            'education': extract_education_from_resume(text)
        }

        resume_filename = f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        resume_path = JobAgentConfig.RESUME_STORAGE / resume_filename
        
        with open(resume_path, 'wb') as f:
            await resume.seek(0)
            f.write(await resume.read())
        
        # Initialize agent
        agent = JobApplicationAgent(candidate_data, resume_path)
        agent.setup_driver(headless=True)
        
        try:
            job_title_search = job_title or candidate_data.get('category')
            all_jobs = []
            
            platform_list = [p.strip().lower() for p in platforms.split(',')]
            
            if 'indeed' in platform_list:
                indeed_jobs = agent.search_jobs_indeed(job_title_search, location, num_jobs)
                all_jobs.extend(indeed_jobs)
            
            if 'linkedin' in platform_list:
                linkedin_jobs = agent.search_jobs_linkedin(job_title_search, location, num_jobs)
                all_jobs.extend(linkedin_jobs)
            
            if not all_jobs:
                return JSONResponse({"error": "No jobs found"}, status_code=404)
            
            # Apply to jobs
            successful, failed = agent.apply_to_jobs_batch(all_jobs[:num_jobs], delay)
            log_file = agent.save_log()
            
            return {
                "candidate": candidate_data,
                "jobs_found": len(all_jobs),
                "total_applications": len(all_jobs[:num_jobs]),
                "successful": successful,
                "failed": failed,
                "log_file": log_file,
                "applications": agent.applications_log
            }
            
        finally:
            agent.close()
            
    except Exception as e:
        job_agent_logger.error(f"Error in auto-apply: {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/application-logs")
async def get_application_logs():
    """Get list of all application logs"""
    try:
        logs_dir = JobAgentConfig.LOGS_DIR
        log_files = sorted(logs_dir.glob("applications_*.json"), reverse=True)
        
        logs = []
        for log_file in log_files[:20]:  # Last 20 logs
            with open(log_file, 'r') as f:
                data = json.load(f)
                logs.append({
                    'filename': log_file.name,
                    'timestamp': log_file.stem.replace('applications_', ''),
                    'candidate': data.get('candidate', {}).get('name'),
                    'summary': data.get('summary', {})
                })
        
        return {"logs": logs}
        
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/application-logs/{log_filename}")
async def get_application_log_detail(log_filename: str):
    """Get detailed application log"""
    try:
        log_file = JobAgentConfig.LOGS_DIR / log_filename
        
        if not log_file.exists():
            return JSONResponse({"error": "Log file not found"}, status_code=404)
        
        with open(log_file, 'r') as f:
            data = json.load(f)
        
        return data
        
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    
@app.get("/job-agent", response_class=HTMLResponse)
async def job_agent_interface(request: Request):
    """Job agent web interface"""
    return templates.TemplateResponse("job_agent.html", {"request": request})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


