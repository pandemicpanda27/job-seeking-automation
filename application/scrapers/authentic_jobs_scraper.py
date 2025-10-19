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

# -------------------------
# Selenium Browser Setup
# -------------------------
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0 Safari/537.36",
]


def get_driver():
    """Sets up and returns a configured Chrome WebDriver instance."""
    options = Options()
    options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    # options.add_argument("--headless")  # uncomment to run in background
    options.add_argument("--log-level=3")  # Suppress console logs
    try:
        driver = webdriver.Chrome(options=options)
        driver.delete_all_cookies()
        return driver
    except WebDriverException as e:
        print(f"🚨 Failed to initialize WebDriver. Check ChromeDriver version. Error: {e}")
        return None


# -------------------------
# Scraper for Authentic Jobs
# -------------------------
def get_authentic_jobs(job_role: str, location: str = "", pages: int = 3) -> List[Dict]:
    """
    Scrapes job listings from Authentic Jobs based on job_role and optional location,
    and returns them as a list of dictionaries.
    """
    print(f"🚀 Starting Authentic Jobs scraper for role: {job_role} in location: {location or 'default'}")

    driver = get_driver()
    if not driver:
        return []

    jobs = []
    source_name = "Authentic Jobs"

    # Combine job_role and location for the 'keywords' parameter if location is provided
    search_term = f"{job_role} {location}" if location else job_role
    query = quote_plus(search_term)

    for page in range(1, pages + 1):
        # The search URL uses 'keywords' for the entire search phrase
        url = f"https://authenticjobs.com/jobs/?keywords={query}&page={page}"
        print(f" Scraping page {page}: {url}")
        driver.get(url)

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "li.job_listing"))
            )
        except TimeoutException:
            print(f"⚠️ No job listings found on page {page} or timeout. Stopping.")
            break

        job_lis = driver.find_elements(By.CSS_SELECTOR, "li.job_listing")
        print(f"  Found {len(job_lis)} jobs on page {page}")

        for li in job_lis:
            link = "N/A"
            title = "N/A"
            company = "N/A"
            scraped_location = "N/A"

            # 1. Link (Apply Link)
            try:
                link_el = li.find_element(By.CSS_SELECTOR, "a[href]")
                link = link_el.get_attribute("href").strip()
            except NoSuchElementException:
                continue  # Skip job if no link

            # 2. Title
            try:
                title = li.find_element(By.CSS_SELECTOR, "div.position h2").text.strip()
            except NoSuchElementException:
                pass

            # 3. Company
            try:
                company = li.find_element(By.CSS_SELECTOR, "div.company strong").text.strip()
            except NoSuchElementException:
                pass

            # 4. Location
            try:
                scraped_location = li.find_element(By.CSS_SELECTOR, "div.location").text.strip()
            except NoSuchElementException:
                pass

            # Append job in the requested dictionary format
            jobs.append({
                "title": title,
                "company": company,
                "location": scraped_location,
                "link": link,
                "portal": source_name
            })

        time.sleep(random.uniform(2, 5))

    driver.quit()
    print(f"✅ Finished scraping Authentic Jobs. Collected {len(jobs)} jobs.")
    return jobs


# -------------------------
# Local Execution Test Block
# -------------------------
if __name__ == "__main__":
    # Test 1: Search with location (will be added to keywords)
    job_role_1 = input("Enter the job role for Authentic Jobs (e.g., 'Web Developer'): ").strip()
    job_location_1 = input("Enter the location (e.g., 'San Francisco'): ").strip()

    authentic_jobs_1 = get_authentic_jobs(job_role_1, location=job_location_1, pages=1)

    print("\nSample Authentic Jobs (With Location in Keywords):")
    pprint(authentic_jobs_1[:3])
    print(f"\nTotal jobs retrieved (With Location): {len(authentic_jobs_1)}")

    print("-" * 30)

    # Test 2: Search without location
    job_role_2 = input("Enter a second job role (no location): ").strip()
    authentic_jobs_2 = get_authentic_jobs(job_role_2, pages=1)

    print("\nSample Authentic Jobs (Default/Remote Search):")
    pprint(authentic_jobs_2[:3])
    print(f"\nTotal jobs retrieved (Default Search): {len(authentic_jobs_2)}")