from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from pprint import pprint

import random
import time
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from typing import List, Dict
from urllib.parse import quote_plus

# Common Browser Options

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0 Safari/537.36",
]


def get_driver():
    # Sets up and returns a configured Chrome WebDriver instance
    options = Options()
    options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--log-level=3")
    options.add_argument("--headless")
    try:
        driver = webdriver.Chrome(options=options)
        driver.delete_all_cookies()
        return driver
    except WebDriverException as e:
        print(f"Failed to initialize WebDriver. Check ChromeDriver version. Error: {e}")
        return None


# Scrape Naukri multi page

def get_naukri_jobs(job_role: str, location: str = "", pages: int = 3) -> List[Dict]:
    
    print(f"Starting Naukri scraper for role: {job_role} in location: {location or 'default'}")
    jobs = []
    source_name = "Naukri"

    role_path = job_role.replace(" ", "-").lower()
    
    role_query = quote_plus(job_role)
    
    loc_query = quote_plus(location)

    for page in range(1, pages + 1):
        
        base_url_path = f"https://www.naukri.com/{role_path}-jobs-{page}"

        query_parts = [f"k={role_query}"]
        if loc_query:
            query_parts.append(f"l={loc_query}")

        query_string = "?" + "&".join(query_parts)
        url = base_url_path + query_string

        print(f" Scraping Naukri page {page}: {url}")

        driver = get_driver()
        if not driver:
            break

        try:
            driver.get(url)
            # wait for job listings to load.
            job_listings = WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "cust-job-tuple"))
            )
        except (TimeoutException, NoSuchElementException):
            print(f"No jobs found or timed out on Naukri page {page}. Stopping.")
            driver.quit()
            break

        for job in job_listings:
            title = "N/A"
            link = "N/A"
            company = "N/A"
            experience = "N/A"
            scraped_location = "N/A" 

            try:
                title_elem = job.find_element(By.CSS_SELECTOR, "a.title")
                title = title_elem.text.strip()
                link = title_elem.get_attribute("href")
            except NoSuchElementException:
                continue 

            try:
                company = job.find_element(By.CSS_SELECTOR, "a.comp-name").text.strip()
            except NoSuchElementException:
                pass

            try:
                experience = job.find_element(By.CSS_SELECTOR, "span.exp").text.strip()
            except NoSuchElementException:
                pass

            try:
                scraped_location = job.find_element(By.CSS_SELECTOR, "span.loc").text.strip()
            except NoSuchElementException:
                pass

                # Append job in the required dictionary format
            jobs.append({
                "title": title,
                "company": company,
                "location": scraped_location,
                "link": link,
                "portal": source_name,
                "experience": experience
            })

        driver.quit()
        time.sleep(random.uniform(2, 4))

    print(f"Finished scraping Naukri. Found {len(jobs)} total job listings.")
    return jobs


# Local Execution Test Block

if __name__ == "__main__":
    from pprint import pprint

    # case1: Search with specific location
    job_role_1 = input("Enter the job role you want to search on Naukri (e.g., 'Software Developer'): ").strip()
    job_location_1 = input("Enter the location (e.g., 'Bangalore'): ").strip()

    naukri_jobs_1 = get_naukri_jobs(job_role_1, location=job_location_1, pages=1)

    print("\nSample Naukri Jobs (With Location):")
    pprint(naukri_jobs_1[:3])
    print(f"\nTotal jobs retrieved (With Location): {len(naukri_jobs_1)}")

    print("-" * 30)

    # case2: Search without location
    job_role_2 = input("Enter a second job role (no location): ").strip()

    naukri_jobs_2 = get_naukri_jobs(job_role_2, pages=1)  # location defaults to ""

    print("\nSample Naukri Jobs (Default/Broad Search):")
    pprint(naukri_jobs_2[:3])
    print(f"\nTotal jobs retrieved (Default Search): {len(naukri_jobs_2)}")