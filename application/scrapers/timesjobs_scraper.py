import time
import random
from pprint import pprint
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from typing import List, Dict
from urllib.parse import quote_plus

# Common Browser Options
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


# TimesJobs Scraper
def get_timesjobs(query: str = "fresher", location: str = "", pages: int = 3) -> List[Dict]:

    print(f"Starting TimesJobs scraper for role: {query} in location: {location or 'default'}")
    jobs = []
    source_name = "TimesJobs"

    query_encoded = quote_plus(query)
    location_encoded = quote_plus(location)

    for page in range(1, pages + 1):
        
        base_url = f"https://www.timesjobs.com/candidate/job-search.html?searchType=personalizedSearch&from=submit"

        query_parts = [f"txtKeywords={query_encoded}"]
        if location_encoded:
            query_parts.append(f"txtLocation={location_encoded}")

        url = f"{base_url}&{'&'.join(query_parts)}&sequence={page}"

        print(f" Scraping page: {page}. URL: {url}")

        driver = get_driver()
        if not driver:
            break

        try:
            driver.get(url)
            job_cards = WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "li.job-bx"))
            )
        except (TimeoutException, NoSuchElementException):
            print(f"No jobs found or timed out on TimesJobs page {page}. Stopping.")
            driver.quit()
            break

        for card in job_cards:
            title, link, company, experience, scraped_location = "N/A", "N/A", "N/A", "N/A", "N/A"

            try:
                title_element = card.find_element(By.CSS_SELECTOR, "h2 > a")
                title = title_element.text.strip()
                link = title_element.get_attribute("href")
            except NoSuchElementException:
                continue 

            try:
                company = card.find_element(By.CSS_SELECTOR, "h3.joblist-comp-name").text.strip().split('(More Jobs)')[
                    0].strip()
            except NoSuchElementException:
                pass

            try:
                experience = card.find_element(By.CSS_SELECTOR, "ul.top-jd-dtl > li:first-child").text.strip().replace(
                    'card_travel', '').strip()
            except NoSuchElementException:
                pass

            try:
                scraped_location = card.find_element(By.CSS_SELECTOR,
                                                     "ul.top-jd-dtl > li:nth-child(2) > span").text.strip()
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

    print(f"Finished scraping TimesJobs. Found {len(jobs)} total job listings.")
    return jobs


# Local Execution Test Block
if __name__ == "__main__":
    from pprint import pprint

    # case1: Search with specific location
    job_query_1 = input("Enter the job role you want to search on TimesJobs (e.g., 'data scientist'): ").strip()
    job_location_1 = input("Enter the location (e.g., 'Bangalore'): ").strip()

    timesjobs_jobs_1 = get_timesjobs(query=job_query_1, location=job_location_1, pages=1)

    print("\nSample TimesJobs Jobs (With Location):")
    pprint(timesjobs_jobs_1[:3])
    print(f"\nTotal jobs retrieved (With Location): {len(timesjobs_jobs_1)}")

    print("-" * 30)

    # case2: Search without location
    job_query_2 = input("Enter a second job role (no location): ").strip()

    timesjobs_jobs_2 = get_timesjobs(query=job_query_2, pages=1)  # location defaults to ""

    print("\nSample TimesJobs Jobs (Default Search):")
    pprint(timesjobs_jobs_2[:3])

    if timesjobs_jobs_2:
        print(f"\nTotal jobs retrieved (Default Search): {len(timesjobs_jobs_2)}")