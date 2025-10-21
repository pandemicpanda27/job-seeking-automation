import time
import random
from pprint import pprint
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from urllib.parse import quote_plus
from typing import List, Dict

# Selenium Browser Setup
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
    options.add_argument("--headless")
    options.add_argument("--log-level=3")
    try:
        driver = webdriver.Chrome(options=options)
        driver.delete_all_cookies()
        return driver
    except WebDriverException as e:
        print(f"🚨 Failed to initialize WebDriver. Check ChromeDriver version. Error: {e}")
        return None


# Scraper for Authentic Jobs

def get_authentic_jobs(job_role: str, location: str = "", pages: int = 3) -> List[Dict]:
    """
    Scrapes job listings from Authentic Jobs based on job_role and optional location,
    and returns them as a list of dictionaries.
    """
    print(f"Starting Authentic Jobs scraper for role: {job_role} in location: {location or 'default'}")

    driver = get_driver()
    if not driver:
        return []

    jobs = []
    source_name = "Authentic Jobs"

    search_term = f"{job_role} {location}" if location else job_role
    query = quote_plus(search_term)

    for page in range(1, pages + 1):
        url = f"https://authenticjobs.com/jobs/?keywords={query}&page={page}"
        print(f" Scraping page {page}: {url}")
        driver.get(url)

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "li.job_listing"))
            )
        except TimeoutException:
            print(f"No job listings found on page {page} or timeout. Stopping.")
            break

        job_lis = driver.find_elements(By.CSS_SELECTOR, "li.job_listing")
        print(f"Found {len(job_lis)} jobs on page {page}")

        for li in job_lis:
            link = "N/A"
            title = "N/A"
            company = "N/A"
            scraped_location = "N/A"

            # Link (Apply Link)
            try:
                link_el = li.find_element(By.CSS_SELECTOR, "a[href]")
                link = link_el.get_attribute("href").strip()
            except NoSuchElementException:
                continue  # Skip job if no link

            # Title
            try:
                title = li.find_element(By.CSS_SELECTOR, "div.position h2").text.strip()
            except NoSuchElementException:
                pass

            # Company
            try:
                company = li.find_element(By.CSS_SELECTOR, "div.company strong").text.strip()
            except NoSuchElementException:
                pass

            # Location
            try:
                scraped_location = li.find_element(By.CSS_SELECTOR, "div.location").text.strip()
            except NoSuchElementException:
                pass

            # append job as dict
            jobs.append({
                "title": title,
                "company": company,
                "location": scraped_location,
                "link": link,
                "portal": source_name
            })

        time.sleep(random.uniform(2, 5))

    driver.quit()
    print(f"Finished scraping Authentic Jobs. Collected {len(jobs)} jobs.")
    return jobs


# Local Execution Test Block

if __name__ == "__main__":
    # case1: search with location
    job_role_1 = input("Enter the job role for Authentic Jobs (e.g., 'Web Developer'): ").strip()
    job_location_1 = input("Enter the location (e.g., 'San Francisco'): ").strip()

    authentic_jobs_1 = get_authentic_jobs(job_role_1, location=job_location_1, pages=1)

    print("\nSample Authentic Jobs (With Location in Keywords):")
    pprint(authentic_jobs_1[:3])
    print(f"\nTotal jobs retrieved (With Location): {len(authentic_jobs_1)}")

    print("-" * 30)

    # case2: Search without location
    job_role_2 = input("Enter a second job role (no location): ").strip()
    authentic_jobs_2 = get_authentic_jobs(job_role_2, pages=1)

    print("\nSample Authentic Jobs (Default/Remote Search):")
    pprint(authentic_jobs_2[:3])
    print(f"\nTotal jobs retrieved (Default Search): {len(authentic_jobs_2)}")