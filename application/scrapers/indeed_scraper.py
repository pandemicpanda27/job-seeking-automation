from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from pprint import pprint
import random
import time
from urllib.parse import quote_plus
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from typing import List, Dict


# selenium browser setup
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

# Scrape Indeed multi page

def get_indeed_jobs(job_role: str, location: str = "", pages: int = 3) -> List[Dict]:
  
    print(f"Starting Indeed scraper for role: {job_role} in location: {location or 'default'}")
    jobs = []
    source_name = "Indeed"

    role_query = quote_plus(job_role)
    loc_query = quote_plus(location)

    # Indeed pagination starts at 0 and increments by 10
    for start_offset in range(0, pages * 10, 10):
        page_num = start_offset // 10 + 1

        base_url = f"https://in.indeed.com/jobs?q={role_query}"

        if loc_query:
            url = f"{base_url}&l={loc_query}&start={start_offset}"
        else:
            url = f"{base_url}&start={start_offset}"

        print(f" Scraping page: {page_num}. URL: {url}")

        driver = get_driver()
        if not driver:
            break 
        try:
            driver.get(url)
            # Wait for job cards to load. The class name "job_seen_beacon" is a common marker.
            job_cards = WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "job_seen_beacon"))
            )
        except (TimeoutException, NoSuchElementException) as e:
            print(f"No jobs found or timed out on Indeed page {page_num}.")
            driver.quit()
            time.sleep(random.uniform(1, 3))
            continue
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            driver.quit()
            break

        for card in job_cards:
            title = "N/A"
            link = "N/A"
            company = "N/A"
            scraped_location = "N/A"  # ranamed variable to avoid conflict with function parameter

            try:
                title_element = card.find_element(By.CSS_SELECTOR, "h2.jobTitle > a")
                title = title_element.text.strip()
                link = title_element.get_attribute("href")
            except NoSuchElementException:
                continue 

            try:
                company = card.find_element(By.CSS_SELECTOR, "[data-testid='company-name']").text.strip()
            except NoSuchElementException:
                pass

            try:
                scraped_location = card.find_element(By.CSS_SELECTOR, "[data-testid='text-location']").text.strip()
            except NoSuchElementException:
                pass

            # Append job as dict
            jobs.append({
                "title": title,
                "company": company,
                "location": scraped_location,
                "link": link,
                "portal": source_name
            })

        driver.quit()
        time.sleep(random.uniform(2, 5))

    print(f"Finished scraping Indeed. Found {len(jobs)} total job listings.")
    return jobs


# Local Execution Test Block
if __name__ == "__main__":
    # case1: Search with location
    job_role_1 = input("Enter the job role you want to search on Indeed (e.g., 'data analyst'): ").strip()
    job_location_1 = input("Enter the location (e.g., 'Bangalore'): ").strip()

    indeed_jobs_1 = get_indeed_jobs(job_role_1, location=job_location_1, pages=1)

    print("\nSample Indeed Jobs (With Location):")
    pprint(indeed_jobs_1[:3])
    print(f"\nTotal jobs retrieved (With Location): {len(indeed_jobs_1)}")

    print("-" * 30)

    # case2: Search without location
    job_role_2 = input("Enter a second job role (no location): ").strip()
    indeed_jobs_2 = get_indeed_jobs(job_role_2, pages=1)

    print("\nSample Indeed Jobs (Default Location):")
    pprint(indeed_jobs_2[:3])
    print(f"\nTotal jobs retrieved (Default Location): {len(indeed_jobs_2)}")