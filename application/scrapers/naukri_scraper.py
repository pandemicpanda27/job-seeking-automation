import random
import time
from pprint import pprint
from typing import List, Dict
from urllib.parse import quote_plus
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
    ElementClickInterceptedException
)



# Common Browser Options

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0 Safari/537.36",
]


def get_driver():
    options = Options()
    options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--log-level=3")  # Suppress console logs
    options.add_argument("--headless")
    try:
        driver = webdriver.Chrome(options=options)
        driver.delete_all_cookies()
        driver.implicitly_wait(5)
        return driver
    except WebDriverException as e:
        print(f"Failed to initialize WebDriver. Check ChromeDriver version. Error: {e}")
        return None


# Scrape Naukri

def get_naukri_jobs(job_role: str, location: str = "", pages: int = 3) -> List[Dict]:
    print(f"Starting Naukri scraper for role: {job_role} in location: {location or 'default'}")

    # Structure to hold job links and initial data (Phase 1 result)
    job_links_data = []
    source_name = "Naukri"

    # Initialize driver ONCE
    driver = get_driver()
    if not driver:
        return []

    # Prepare parameters
    role_path = job_role.replace(" ", "-").lower()
    role_query = quote_plus(job_role)
    loc_query = quote_plus(location)

    try:
        # COLLECT ALL JOB LINKS AND BASIC DATA
        print("\n--- Phase 1: Collecting Links and Basic Data ---")
        for page in range(1, pages + 1):
            base_url_path = f"https://www.naukri.com/{role_path}-jobs-{page}"
            query_parts = [f"k={role_query}"]
            if loc_query:
                query_parts.append(f"l={loc_query}")

            url = base_url_path + "?" + "&".join(query_parts)
            print(f" Scraping Naukri page {page}: {url}")

            driver.get(url)

            # Handle Cookie/Privacy Policy Banner
            try:
                # Using a more robust selector that contains 'I accept'
                cookie_accept_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'I accept')]"))
                )
                cookie_accept_button.click()
                print("Cookie banner accepted.")
                time.sleep(0.5)
            except TimeoutException:
                print("No cookie banner found or timed out waiting for it. Continuing.")
            except Exception as e:
                print(f"Minor error handling cookie banner: {e}")

            # Wait for job listings to load.
            try:
                job_listings = WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CLASS_NAME, "cust-job-tuple"))
                )
            except (TimeoutException, NoSuchElementException):
                print(f"No jobs found or timed out on Naukri page {page}. Stopping.")
                break

            for job in job_listings:
                try:
                    title_elem = job.find_element(By.CSS_SELECTOR, "a.title")
                    link = title_elem.get_attribute("href")

                    # Ensure the link is a non-empty string
                    if not link or not isinstance(link, str):
                        print(f"Skipping job '{title_elem.text.strip()}' because link is invalid or missing.")
                        continue 
                    
                    # Store link and basic data only if the link is valid
                    job_links_data.append({
                        "title": title_elem.text.strip(),
                        "company": job.find_element(By.CSS_SELECTOR, "a.comp-name").text.strip() if job.find_elements(
                            By.CSS_SELECTOR, "a.comp-name") else "N/A",
                        "experience_list": job.find_element(By.CSS_SELECTOR,
                                                            "span.exp").text.strip() if job.find_elements(
                            By.CSS_SELECTOR, "span.exp") else "N/A",
                        "location_list": job.find_element(By.CSS_SELECTOR,
                                                          "span.loc").text.strip() if job.find_elements(By.CSS_SELECTOR,
                                                                                                        "span.loc") else "N/A",
                        "link": link,
                        "portal": source_name,
                        "description": "N/A"  # Placeholder for description
                    })

                except Exception as e:
                    print(f"Error scraping basic data from list view: {e}. Skipping job.")
                    continue

            # Use random sleep between pages
            time.sleep(random.uniform(2, 4))

        print(f"Phase 1 complete. Collected {len(job_links_data)} job links.")

        # SEQUENTIAL NAVIGATION AND DETAIL SCRAPING
        final_jobs = []
        print("\n--- Phase 2: Scraping Details Sequentially ---")

        for i, job_data in enumerate(job_links_data):
            link = job_data['link']
            print(f" [{i + 1}/{len(job_links_data)}] Visiting: {link}")

            try:
                # Navigate to the individual job page
                driver.get(link)

                # Scrape details using provided selectors

                # Title
                job_data['title'] = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h1.styles_jd-header-title__rZwM1"))
                ).text.strip()

                # Company
                try:
                    job_data['company'] = driver.find_element(By.CSS_SELECTOR, "a[title$='Careers']").text.strip()
                except NoSuchElementException:
                    pass 

                # Experience
                try:
                    job_data['experience'] = driver.find_element(By.XPATH,
                                                                 "//span[contains(text(), 'years') or contains(text(), 'Yrs')]").text.strip()
                except NoSuchElementException:
                    job_data['experience'] = job_data.pop('experience_list')  # Use list view data

                # Location
                try:
                    job_data['location'] = driver.find_element(By.CSS_SELECTOR, "a[title^='Jobs in ']").text.strip()
                except NoSuchElementException:
                    job_data['location'] = job_data.pop('location_list') 

                # Description
                desc_container = driver.find_element(By.CSS_SELECTOR, "section.styles_job-desc-container__txpYf")

                # Target all immediate child <div> elements
                desc_divs = desc_container.find_elements(By.TAG_NAME, "div")

                description_parts = []
                # Iterate through the divs and build the description, excluding the footer
                for div in desc_divs:
                    div_class = div.get_attribute('class')
                    div_text = div.text.strip()

                    # Explicitly skip the footer and ensure the div is not empty
                    if not div_text:
                        continue
                    if "styles_JDC__footer__ZJnPe" in div_class:
                        continue

                    # We also avoid known elements like the key skills section
                    if "styles_key-skill" in div_class:
                        continue

                    description_parts.append(div_text)

                # Concatenate the collected parts
                job_data['description'] = "\n\n".join(description_parts)

                # Remove temporary list view data keys
                job_data.pop('experience_list', None)
                job_data.pop('location_list', None)

                final_jobs.append(job_data)

            except Exception as e:
                print(f"Skipping job due to critical error on detail page {job_data['title']}: {e}")
                # Ensure placeholder data is still collected even if description fails
                job_data['description'] = f"Scrape failed: {type(e).__name__}"
                job_data.pop('experience_list', None)
                job_data.pop('location_list', None)
                final_jobs.append(job_data)

            time.sleep(random.uniform(1, 2)) 

    except Exception as e:
        print(f"An outer loop error occurred: {e}")
    finally:
        driver.quit()

    print(f"\nFinished scraping Naukri. Found {len(final_jobs)} total job listings with details.")
    return final_jobs



# Local Execution Test Block
if __name__ == "__main__":

    # case 1: Search with specific location
    job_role_1 = input("Enter the job role you want to search on Naukri (e.g., 'Software Developer'): ").strip()
    job_location_1 = input("Enter the location (e.g., 'Bangalore'): ").strip()

    naukri_jobs_1 = get_naukri_jobs(job_role_1, location=job_location_1, pages=1)

    print("\nSample Naukri Jobs (With Location):")
    pprint(naukri_jobs_1[:3])
    print(f"\nTotal jobs retrieved (With Location): {len(naukri_jobs_1)}")

    print("-" * 30)

    # case 2: Search without location
    job_role_2 = input("Enter a second job role (no location): ").strip()

    naukri_jobs_2 = get_naukri_jobs(job_role_2, pages=1)

    print("\nSample Naukri Jobs (Default/Broad Search):")
    pprint(naukri_jobs_2[:3])
    print(f"\nTotal jobs retrieved (Default Search): {len(naukri_jobs_2)}")