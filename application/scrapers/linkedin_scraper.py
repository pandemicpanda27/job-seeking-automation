import time
import random
from urllib.parse import quote_plus
from typing import List, Dict

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

PAGES = 2
RESULTS_PER_PAGE = 25  # LinkedIn default is 25 per page
HEADLESS = True
DELAY_MIN = 1.5
DELAY_MAX = 3.5
MAX_RETRIES = 2
SOURCE_PORTAL = "LinkedIn"  # New variable for the required 'portal' key

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
]


# Scraping helpers

def build_search_url(query: str, location: str, start: int = 0) -> str:
    # constructs the LinkedIn jobs search URL
   
    return f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(query)}&location={quote_plus(location)}&start={start}"


def text_or_none(el):
    # Safely extracts text from a Playwright element handle
    try:
        return el.inner_text().strip()
    except Exception:
        return None


def scrape_page(page, url) -> List[Dict]:
    # Scrapes job data from a single search results page
    jobs = []
    try:
        # Wait for the main results list to load
        page.wait_for_selector("ul.jobs-search__results-list", timeout=8000)
    except PlaywrightTimeoutError:
        print(f"⚠️ Timeout waiting for job list on {url}")
        pass

    job_items = page.query_selector_all("ul.jobs-search__results-list li, .jobs-search-results__list-item")
    for item in job_items:
        job_title = "N/A"
        company = "N/A"
        scraped_location = "N/A"
        exp_text = "N/A"
        job_link = "N/A"

        try:
            # DATA EXTRACTION

            # Job title
            title_el = item.query_selector("h3, .base-search-card__title")
            job_title = text_or_none(title_el) or "N/A"

            # Company
            company_el = item.query_selector(".base-search-card__subtitle")
            company = text_or_none(company_el) or "N/A"

            # Location
            loc_el = item.query_selector(".job-card-container__metadata-item, .job-card-list__location")
            scraped_location = text_or_none(loc_el) or "N/A"

            # Experience
            snippet_el = item.query_selector(".job-card-container__snippet, .job-card-list__snippet")
            if snippet_el:
                text = text_or_none(snippet_el)
                if text and ("year" in text.lower() or "yr" in text.lower()):
                    exp_text = text

            # Job link
            link_el = item.query_selector("a")
            job_link = link_el.get_attribute("href") if link_el else None
            # Handle relative links if they exist
            if job_link and job_link.startswith("/"):
                job_link = "https://www.linkedin.com" + job_link

            if job_title != "N/A" and job_link:
                jobs.append({
                    "title": job_title,
                    "company": company,
                    "location": scraped_location,
                    "link": job_link,
                    "portal": SOURCE_PORTAL,
                    "experience": exp_text
                })
        except Exception:
            # skip job card on general error
            continue
    return jobs


# Orchestrator

def get_linkedin_jobs(query: str, location: str = "", pages: int = PAGES) -> List[Dict]:
    print(f"Starting LinkedIn scraper for role: '{query}' in location: '{location or 'default'}'")
    scraped = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)

        for page_num in range(pages):
            ua = random.choice(USER_AGENTS)
            # Create a new context for each page to manage user agent/cookies better
            context = browser.new_context(user_agent=ua)
            page = context.new_page()

            url = build_search_url(query, location, page_num * RESULTS_PER_PAGE)
            print(f"[{page_num + 1}/{pages}] Visiting: {url}")

            # Retry mechanism for page navigation
            for attempt in range(MAX_RETRIES + 1):
                try:
                    page.goto(url, timeout=30000)
                    break
                except PlaywrightTimeoutError:
                    print(f"   [!] Navigation timeout on attempt {attempt + 1}")
                    if attempt == MAX_RETRIES:
                        print("   [!] Max retries reached. Skipping page.")
                    time.sleep(2)
            else:
                context.close()
                continue

            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

            jobs_on_page = scrape_page(page, url)
            print(f"   Found {len(jobs_on_page)} jobs on page {page_num + 1}")
            scraped.extend(jobs_on_page)

            context.close()

        browser.close()

    print(f"Finished scraping LinkedIn. Collected {len(scraped)} jobs.")
    return scraped


# Entry point
if __name__ == "__main__":
    from pprint import pprint

    # case1: Search with location
    QUERY_1 = input("Enter the job role you want to search for (e.g., 'Data Engineer'): ").strip()
    LOCATION_1 = input("Enter the location (e.g., 'India, Remote'): ").strip()

    results_1 = get_linkedin_jobs(QUERY_1, LOCATION_1, pages=1)

    print("\nSample LinkedIn Jobs (With Location):")
    pprint(results_1[:3])
    print(f"\nTotal jobs retrieved (With Location): {len(results_1)}")

    print("-" * 30)

    # case2: Search without location
    QUERY_2 = input("Enter a second job role (no location): ").strip()

    results_2 = get_linkedin_jobs(QUERY_2, pages=1)

    print("\nSample LinkedIn Jobs (Default/Broad Search):")
    pprint(results_2[:3])
    print(f"\nTotal jobs retrieved (Default Search): {len(results_2)}")