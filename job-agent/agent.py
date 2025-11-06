import time
import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException,
    ElementClickInterceptedException,
    StaleElementReferenceException
)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('job_application.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class Config:
    FLASK_API_URL = "http://localhost:5000"
    FLASK_PARSE_ENDPOINT = "/api/parse"
    
    BASE_DIR = Path(__file__).parent
    RESUME_DIR = BASE_DIR.parent / "resumes"
    LOGS_DIR = BASE_DIR / "logs"
    
    DEFAULT_DELAY = 5
    MAX_APPLICATIONS_PER_SESSION = 20
    TIMEOUT = 15
    
    # Changed to India
    DEFAULT_LOCATION = "India"
    SEARCH_RADIUS = 25  # miles
    
    LOGS_DIR.mkdir(exist_ok=True)
    

class FormFiller:
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
        'address': [
            'address', 'street', 'location', 'residence'
        ],
        'city': [
            'city', 'town', 'municipality'
        ],
        'state': [
            'state', 'province', 'region'
        ],
        'zip': [
            'zip', 'zipcode', 'postal', 'postalcode', 'postcode'
        ],
        'linkedin': [
            'linkedin', 'linkedin-url', 'linkedin-profile'
        ],
        'website': [
            'website', 'portfolio', 'personal-site', 'url'
        ],
        'resume': [
            'resume', 'cv', 'upload-resume', 'file', 
            'attachment', 'document'
        ],
        'cover_letter': [
            'cover', 'cover-letter', 'coverletter', 
            'letter', 'motivation'
        ]
    }
    
    @staticmethod
    def find_field(driver, field_type, timeout=5):
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
            
            # Try by label text
            try:
                label = driver.find_element(By.XPATH, f"//label[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{pattern}')]")
                for_attr = label.get_attribute('for')
                if for_attr:
                    return driver.find_element(By.ID, for_attr)
            except NoSuchElementException:
                pass
            
            # Try by placeholder
            try:
                return driver.find_element(By.XPATH, f"//*[contains(@placeholder, '{pattern}')]")
            except NoSuchElementException:
                pass
            
            # Try partial match in any attribute
            try:
                return driver.find_element(By.XPATH, f"//*[contains(@id, '{pattern}') or contains(@name, '{pattern}') or contains(@class, '{pattern}')]")
            except NoSuchElementException:
                pass
        
        return None
    
    @staticmethod
    def fill_field(element, value, clear_first=True):
        try:
            if clear_first:
                element.clear()
            element.send_keys(value)
            return True
        except Exception as e:
            logger.warning(f"Could not fill field: {str(e)}")
            return False
    
    @staticmethod
    def upload_file(element, file_path):
        try:
            abs_path = os.path.abspath(file_path)
            if not os.path.exists(abs_path):
                logger.error(f"File not found: {abs_path}")
                return False
            element.send_keys(abs_path)
            return True
        except Exception as e:
            logger.error(f"Could not upload file: {str(e)}")
            return False


class JobApplicationAgent:
    
    def __init__(self, resume_path, config=None):
        self.config = config or Config()
        self.resume_path = Path(resume_path)
        
        if not self.resume_path.exists():
            raise FileNotFoundError(f"Resume not found: {self.resume_path}")
        
        self.candidate_data = {}
        self.driver = None
        self.applications_log = []
        self.form_filler = FormFiller()
        
    def setup_driver(self, headless=False):
        options = webdriver.ChromeOptions()
        
        if headless:
            options.add_argument('--headless')
        
        # Anti-detection measures
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Realistic user agent
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # preferences
        prefs = {
            "download.default_directory": str(self.config.LOGS_DIR),
            "download.prompt_for_download": False,
        }
        options.add_experimental_option("prefs", prefs)
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.maximize_window()
        
        # Execute CDP commands for stealth
        self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        logger.info("WebDriver initialized successfully")
        
    def parse_resume(self):
        """Parse resume using Flask API"""
        try:
            api_url = f"{self.config.FLASK_API_URL}{self.config.FLASK_PARSE_ENDPOINT}"
            
            with open(self.resume_path, 'rb') as f:
                files = {'resume': f}
                response = requests.post(api_url, files=files, timeout=30)
            
            if response.status_code == 200:
                self.candidate_data = response.json()
                logger.info("Resume parsed successfully")
                logger.info(f"Candidate: {self.candidate_data.get('name')}")
                logger.info(f"Category: {self.candidate_data.get('category')}")
                logger.info(f"Skills: {len(self.candidate_data.get('skills', []))} found")
                return True
            else:
                logger.error(f"API returned status {response.status_code}")
                return False
                
        except requests.exceptions.ConnectionError:
            logger.error(f"Cannot connect to Flask API at {self.config.FLASK_API_URL}")
            logger.error("Make sure your Flask app is running!")
            return False
        except Exception as e:
            logger.error(f"Error parsing resume: {str(e)}")
            return False
    
    def search_jobs_indeed(self, job_title=None, location=None, num_jobs=10):
        job_title = job_title or self.candidate_data.get('category', 'Software Engineer')
        location = location or self.config.DEFAULT_LOCATION
        
        try:
            base_url = "https://www.indeed.com/jobs"
            params = {
                'q': job_title,
                'l': location,
                'fromage': '7',  # Last 7 days
                'sort': 'date'
            }
            
            query_string = '&'.join([f"{k}={v.replace(' ', '+')}" for k, v in params.items()])
            search_url = f"{base_url}?{query_string}"
            
            logger.info(f"Searching Indeed: {job_title} in {location}")
            self.driver.get(search_url)
            time.sleep(3)

            wait = WebDriverWait(self.driver, self.config.TIMEOUT)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.job_seen_beacon")))
            
            job_listings = []
            job_cards = self.driver.find_elements(By.CSS_SELECTOR, "div.job_seen_beacon")
            
            for card in job_cards[:num_jobs]:
                try:
                    # Get job title and link
                    title_elem = card.find_element(By.CSS_SELECTOR, "h2.jobTitle a")
                    job_url = title_elem.get_attribute('href')
                    job_title_text = title_elem.text
                    
                    # Get company
                    try:
                        company = card.find_element(By.CSS_SELECTOR, "span[data-testid='company-name']").text
                    except:
                        company = "Unknown"
                    
                    # Get location
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
                    logger.debug(f"Could not parse job card: {str(e)}")
                    continue
            
            logger.info(f"Found {len(job_listings)} jobs on Indeed")
            return job_listings
            
        except TimeoutException:
            logger.error("Timeout waiting for Indeed results")
            return []
        except Exception as e:
            logger.error(f"Error searching Indeed: {str(e)}")
            return []
    
    def search_jobs_linkedin(self, job_title=None, location=None, num_jobs=10):
        """Search for jobs on LinkedIn (requires login)"""
        job_title = job_title or self.candidate_data.get('category', 'Software Engineer')
        location = location or self.config.DEFAULT_LOCATION
        
        try:
            base_url = "https://www.linkedin.com/jobs/search/"
            search_url = f"{base_url}?keywords={job_title.replace(' ', '%20')}&location={location.replace(' ', '%20')}&f_TPR=r604800&sortBy=DD"
            
            logger.info(f"Searching LinkedIn: {job_title} in {location}")
            self.driver.get(search_url)
            time.sleep(4)
            
            # Scroll to load more jobs
            for _ in range(3):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
            
            job_listings = []
            job_cards = self.driver.find_elements(By.CSS_SELECTOR, "div.base-card")
            
            for card in job_cards[:num_jobs]:
                # try:
                #     title_elem = card.find_element(By.CSS_SELECTOR, "h3.base-search-card__title")
                #     link_elem = card.find_element(By.CSS_SELECTOR, "a.base-card__full-link")
                    
                #     job_url = link_elem.get_attribute('href')
                #     job_title_text = title_elem.textfor card in job_cards[:num_jobs]:
                try:
                    # Try multiple selectors for title
                    title_elem = None
                    title_selectors = [
                        "h3.base-search-card__title",
                        "h3.job-card-list__title",
                        "a.job-card-container__link",
                        ".job-card-list__title--link"
                    ]
                    
                    for selector in title_selectors:
                        try:
                            title_elem = card.find_element(By.CSS_SELECTOR, selector)
                            if title_elem and title_elem.text.strip():
                                break
                        except NoSuchElementException:
                            continue
                    
                    if not title_elem or not title_elem.text.strip():
                        logger.debug("Skipping card - no title found")
                        continue
                    
                    # Try multiple selectors for link
                    link_elem = None
                    link_selectors = [
                        "a.base-card__full-link",
                        "a.job-card-container__link",
                        "a.job-card-list__title"
                    ]
                    
                    for selector in link_selectors:
                        try:
                            link_elem = card.find_element(By.CSS_SELECTOR, selector)
                            if link_elem:
                                break
                        except NoSuchElementException:
                            continue
                    
                    if not link_elem:
                        logger.debug("Skipping card - no link found")
                        continue
                    
                    try:
                        company_selectors = [
                            "h4.base-search-card__subtitle",
                            "a.job-card-container__company-name",
                            ".job-card-container__primary-description"
                        ]
                        company = "Unknown"
                        for selector in company_selectors:
                            try:
                                comp_elem = card.find_element(By.CSS_SELECTOR, selector)
                                if comp_elem and comp_elem.text.strip():
                                    company = comp_elem.text.strip()
                                    break
                            except:
                                continue
                    except:
                        company = "Unknown"

                    try:
                        location_selectors = [
                            "span.job-search-card__location",
                            ".job-card-container__metadata-item",
                            "span.job-card-container__location"
                        ]
                        loc = location
                        for selector in location_selectors:
                            try:
                                loc_elem = card.find_element(By.CSS_SELECTOR, selector)
                                if loc_elem and loc_elem.text.strip():
                                    loc = loc_elem.text.strip()
                                    break
                            except:
                                continue
                    except:
                        loc = location
                    
                except Exception as e:
                    logger.debug(f"Could not parse LinkedIn job card: {str(e)}")
                    continue
            
            logger.info(f"Found {len(job_listings)} jobs on LinkedIn")
            return job_listings
            
        except Exception as e:
            logger.error(f"Error searching LinkedIn: {str(e)}")
            return []
    
    def fill_application_form(self):
        try:
            # Split name
            name = self.candidate_data.get('name', '')
            name_parts = name.split() if name else []
            first_name = name_parts[0] if name_parts else ''
            last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
            
            filled_fields = []
            
            # Try to fill full name
            full_name_field = self.form_filler.find_field(self.driver, 'full_name')
            if full_name_field:
                if self.form_filler.fill_field(full_name_field, name):
                    filled_fields.append('full_name')
            else:
                # Try first and last name separately
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
            
            logger.info(f"Filled fields: {', '.join(filled_fields)}")
            return len(filled_fields) > 0
            
        except Exception as e:
            logger.error(f"Error filling form: {str(e)}")
            return False
    
    def apply_to_job(self, job_info):
        """Apply to a specific job"""
        try:
            job_url = job_info['url']
            platform = job_info.get('platform', 'generic')
            
            logger.info(f"Applying to: {job_info['title']} at {job_info['company']}")
            
            self.driver.get(job_url)
            time.sleep(3)
            
            # Look for apply button
            apply_button = None
            apply_selectors = [
                # Indeed-specific selectors
                "//button[contains(text(), 'Apply now')]",
                "//a[contains(text(), 'Apply now')]",
                "//div[contains(@class, 'jobsearch-IndeedApplyButton')]//button",
                "//button[contains(@class, 'indeed-apply-button')]",
                
                # Generic "Apply on company site" buttons
                "//button[contains(text(), 'Apply on company site')]",
                "//a[contains(text(), 'Apply on company site')]",
                "//a[contains(@class, 'jobsearch-IndeedApplyButton')]",
                
                # Generic apply buttons
                "//button[contains(translate(text(), 'APPLY', 'apply'), 'apply')]",
                "//a[contains(translate(text(), 'APPLY', 'apply'), 'apply')]",
                "//button[contains(@class, 'apply')]",
                "//button[contains(@id, 'apply')]",
                
                # Fallback patterns
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
                logger.warning("No apply button found")
                logger.debug(f"Current URL: {self.driver.current_url}")
                logger.debug(f"Page title: {self.driver.title}")
                
                # Try to find any buttons/links with text
                try:
                    all_buttons = self.driver.find_elements(By.TAG_NAME, "button")
                    all_links = self.driver.find_elements(By.TAG_NAME, "a")
                    
                    button_texts = [b.text for b in all_buttons if b.text.strip()][:10]
                    link_texts = [a.text for a in all_links if a.text.strip()][:10]
                    
                    logger.debug(f"Sample buttons: {button_texts}")
                    logger.debug(f"Sample links: {link_texts}")
                except:
                    pass
                
                return False
            
            # Check if it's an external application button
            button_text = apply_button.text.lower()
            is_external = 'company site' in button_text or 'employer site' in button_text

            # Click apply button
            try:
                apply_button.click()
            except ElementClickInterceptedException:
                # Try JavaScript click
                self.driver.execute_script("arguments[0].click();", apply_button)

            time.sleep(2)

            # Handle external vs internal application
            if is_external:
                form_filled = self.handle_external_application(job_info)
            else:
                # Fill the form on current page
                form_filled = self.fill_application_form()
            
            if not form_filled:
                logger.warning("Could not fill any form fields")
                return False
            
            # Look for submit button
            submit_selectors = [
                "//button[contains(translate(text(), 'SUBMIT', 'submit'), 'submit')]",
                "//button[@type='submit']",
                "//input[@type='submit']",
                "//button[contains(text(), 'Send application')]",
            ]
            
            for selector in submit_selectors:
                try:
                    submit_btn = self.driver.find_element(By.XPATH, selector)
                    logger.info(f"✓ Application ready to submit")
                    
                    # Log the application
                    self.applications_log.append({
                        **job_info,
                        'timestamp': datetime.now().isoformat(),
                        'status': 'ready_to_submit',
                        'form_filled': True
                    })
                    
                    submit_btn.click()
                    logger.info("✓ Application submitted!")
                    
                    return True
                except NoSuchElementException:
                    continue
            
            logger.warning("Could not find submit button")
            return False
            
        except Exception as e:
            logger.error(f"Error applying to job: {str(e)}")
            return False
    
    def handle_external_application(self, job_info):
        """Handle 'Apply on company site' redirects"""
        try:
            logger.info("Detected external application - following redirect...")
            time.sleep(2)
            
            # Get current window handle
            main_window = self.driver.current_window_handle
            
            # Check if new tab/window opened
            if len(self.driver.window_handles) > 1:
                # Switch to new window
                for handle in self.driver.window_handles:
                    if handle != main_window:
                        self.driver.switch_to.window(handle)
                        break
                
                logger.info(f"Redirected to: {self.driver.current_url}")
                time.sleep(3)
                
                # Try to fill form on external site
                form_filled = self.fill_application_form()
                
                # Look for submit button
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
                            logger.info("Ready to submit on external site (auto-submit disabled)")
                            
                            self.applications_log.append({
                                **job_info,
                                'timestamp': datetime.now().isoformat(),
                                'status': 'ready_to_submit_external',
                                'form_filled': True,
                                'external_url': self.driver.current_url
                            })
                            
                            # Close external tab and return to main window
                            self.driver.close()
                            self.driver.switch_to.window(main_window)
                            return True
                        except NoSuchElementException:
                            continue
                
                # Close external tab and return to main window
                self.driver.close()
                self.driver.switch_to.window(main_window)
                return False
            else:
                # Stayed in same window - just redirected
                logger.info(f"Redirected to: {self.driver.current_url}")
                time.sleep(3)
                return self.fill_application_form()
                
        except Exception as e:
            logger.error(f"Error handling external application: {str(e)}")
            # Try to get back to main window
            try:
                self.driver.switch_to.window(main_window)
            except:
                pass
            return False
    
    def apply_to_jobs_batch(self, job_listings, delay=None):
        """Apply to multiple jobs"""
        delay = delay or self.config.DEFAULT_DELAY
        
        successful = 0
        failed = 0
        
        for i, job in enumerate(job_listings, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing job {i}/{len(job_listings)}")
            logger.info(f"{'='*60}")
            
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
            
            # Rate limiting
            if i < len(job_listings):
                logger.info(f"Waiting {delay} seconds before next application...")
                time.sleep(delay)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Batch complete: {successful} ready to submit, {failed} failed")
        logger.info(f"{'='*60}")
        
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
        
        logger.info(f"Log saved to: {log_file}")
    
    def close(self):
        """Cleanup"""
        if self.driver:
            self.driver.quit()
            logger.info("WebDriver closed")


# Main Execution
def main():
    """Main execution function"""
    
    # Config
    RESUME_PATH = "../resumes/resume_sample_1.pdf"
    JOB_TITLE = None
    LOCATION = "Bengaluru, KA"  # Change, according to resume
    NUM_JOBS = 5
    HEADLESS = False  # Set True to run in background
    
    # Initialize agent
    logger.info("Initializing Job Application Agent...")
    agent = JobApplicationAgent(
        resume_path=RESUME_PATH
    )
    
    try:
        # Parse resume
        logger.info("Parsing resume via Flask API...")
        if not agent.parse_resume():
            logger.error("Failed to parse resume. Exiting.")
            return
        
        # Setup browser
        logger.info("Setting up WebDriver...")
        agent.setup_driver(headless=HEADLESS)
        
        # Search jobs
        job_title = JOB_TITLE or agent.candidate_data.get('category')
        logger.info(f"\nSearching for jobs: {job_title}")
        
        all_jobs = []
        
        # Search Indeed
        indeed_jobs = agent.search_jobs_indeed(job_title, LOCATION, NUM_JOBS)
        all_jobs.extend(indeed_jobs)
        
        # Search LinkedIn
        linkedin_jobs = agent.search_jobs_linkedin(job_title, LOCATION, NUM_JOBS)
        all_jobs.extend(linkedin_jobs)
        
        if not all_jobs:
            logger.warning("No jobs found!")
            return

        logger.info(f"\nFound {len(all_jobs)} jobs:")
        for i, job in enumerate(all_jobs, 1):
            logger.info(f"{i}. {job['title']} at {job['company']} ({job['platform']})")
        
        # Apply to jobs
        logger.info("\nStarting application process...")
        agent.apply_to_jobs_batch(all_jobs[:3], delay=10)  # Apply to first 3 jobs

        agent.save_log()
        
        logger.info("\n✓ Process complete!")
        
    except KeyboardInterrupt:
        logger.info("\nProcess interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
    finally:
        agent.close()


if __name__ == "__main__":
    main()