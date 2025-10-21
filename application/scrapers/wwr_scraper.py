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


# Selenium Setup

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
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


# Scraper for We Work Remotely
def get_wwr_jobs(job_role: str, location: str = "", pages: int = 3) -> List[Dict]:
    print(f"Starting We Work Remotely scraper for role: {job_role} in location: {location or 'default'}")
    jobs = []
    source_name = "We Work Remotely"
    driver = get_driver()
    if not driver:
        return jobs

    search_term = f"{job_role} {location}" if location else job_role
    query = quote_plus(search_term)

    for page in range(1, pages + 1):
        url = f"https://weworkremotely.com/remote-jobs/search?term={query}&page={page}"
        print(f" Scraping page {page}: {url}")
        driver.get(url)

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "li.new-listing-container"))
            )
        except TimeoutException:
            print(f"No job listings found on page {page}.")
            break

        job_listings = driver.find_elements(By.CSS_SELECTOR, "li.new-listing-container")
        print(f"  Found {len(job_listings)} jobs on page {page}")

        for li in job_listings:
            title, link, company, scraped_location = "N/A", "N/A", "N/A", "Anywhere"
            experience = "N/A"

            try:
                job_link_el = li.find_element(By.CSS_SELECTOR, "a[href*='/remote-jobs/']")
                link = "https://weworkremotely.com" + job_link_el.get_attribute("href")
            except NoSuchElementException:
                continue

            # Job title
            try:
                title = job_link_el.find_element(By.CSS_SELECTOR, "h3").text.strip()
            except NoSuchElementException:
                pass

            # Company name
            try:
                company = job_link_el.find_element(By.CSS_SELECTOR, "p.new-listing_company-name").text.strip()
            except NoSuchElementException:
                pass

            # Location
            try:
                scraped_location = job_link_el.find_element(By.CSS_SELECTOR,
                                                            "p.new-listing___company-headquarters").text.strip() or "Anywhere"
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

        time.sleep(random.uniform(2, 5))

    driver.quit()
    print(f"Finished scraping We Work Remotely. Collected {len(jobs)} jobs.")
    return jobs


# Local Execution Test Block
if __name__ == "__main__":
    from pprint import pprint

    # case1: Search with location (added to search term)
    job_role_1 = input("Enter the job role you want to search on WWR (e.g., 'React Developer'): ").strip()
    job_location_1 = input("Enter the location (e.g., 'Europe' or 'New York'): ").strip()

    wwr_jobs_1 = get_wwr_jobs(job_role_1, location=job_location_1, pages=1)

    print("\nSample WWR Jobs (With Location in Search Term):")
    pprint(wwr_jobs_1[:3])
    print(f"\nTotal jobs retrieved (With Location): {len(wwr_jobs_1)}")

    print("-" * 30)

    # case2: Search without location
    job_role_2 = input("Enter a second job role (no location): ").strip()

    wwr_jobs_2 = get_wwr_jobs(job_role_2, pages=1)  # location defaults to ""

    print("\nSample WWR Jobs (Default/Remote Search):")
    pprint(wwr_jobs_2[:3])

    if wwr_jobs_2:
        print(f"\nTotal jobs retrieved (Default Search): {len(wwr_jobs_2)}")