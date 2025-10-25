from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from pprint import pprint
import random
import time
from urllib.parse import quote_plus
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException, StaleElementReferenceException
from typing import List, Dict


# Common Browser Options
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0 Safari/537.36",
]


def get_driver():
    """Sets up and returns a configured Chrome WebDriver instance."""
    options = Options()
    options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    options.add_argument("--disable-blink-features=AutomationControlled")  # Added for stealth
    options.add_argument("--log-level=3")  # Suppress console logs
    options.add_argument("--headless") 
    try:
        driver = webdriver.Chrome(options=options)
        driver.delete_all_cookies()
        return driver
    except WebDriverException as e:
        print(f"Failed to initialize WebDriver. Check ChromeDriver version. Error: {e}")
        return None


# Scrape Indeed multi-page
def get_indeed_jobs(job_role: str, location: str = "", pages: int = 3) -> List[Dict]:

    print(f"Starting Indeed scraper for role: {job_role} in location: {location or 'default'}")
    jobs = []
    source_name = "Indeed"

    role_query = quote_plus(job_role)
    loc_query = quote_plus(location)

    for start_offset in range(0, pages * 10, 10):
        page_num = start_offset // 10 + 1
        # conditional URL Construction
        base_url = f"https://in.indeed.com/jobs?q={role_query}"

        if loc_query:
            url = f"{base_url}&l={loc_query}&start={start_offset}"
        else:
            url = f"{base_url}&start={start_offset}"

        print(f" Scraping page: {page_num}. URL: {url}")

        # Scraping Logic
        driver = get_driver()
        if not driver:
            break

        try:
            driver.get(url)
            # Wait for job cards to be present
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "job_seen_beacon"))
            )
            # Get all job card elements
            job_cards = driver.find_elements(By.CLASS_NAME, "job_seen_beacon")

        except (TimeoutException, NoSuchElementException) as e:
            print(f"No jobs found or timed out on Indeed page {page_num}.")
            driver.quit()
            time.sleep(random.uniform(1, 3))
            continue
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            driver.quit()
            break

            # Store the handle of the main search window
        main_window_handle = driver.current_window_handle

        for i, card in enumerate(job_cards):  # Use enumerate to track progress/index

            title = "N/A"
            link = "N/A"
            company = "N/A"
            scraped_location = "N/A"
            description = "N/A"

            try:
                # Extract static data
                title_element = card.find_element(By.CSS_SELECTOR, "h2.jobTitle > a")
                title = title_element.text.strip() # Title
                link = title_element.get_attribute("href") # Link

                company = card.find_element(By.CSS_SELECTOR, "[data-testid='company-name']").text.strip() # Company
                scraped_location = card.find_element(By.CSS_SELECTOR, "[data-testid='text-location']").text.strip() # Location

            except NoSuchElementException as e:
                # If essential elements aren't found, skip the card
                print(f" Skipping card {i + 1} due to missing data: {e.__class__.__name__}")
                continue
            except StaleElementReferenceException:
                # If the element becomes stale skip and continue
                print(f" Skipping card {i + 1}. Stale element reference.")
                continue

            # Open the Link in a NEW TAB and scrape the description
            if link and link != "N/A":
                try:
                    # Execute JavaScript to open the link in a new tab
                    driver.execute_script(f"window.open('{link}');")

                    # Wait for the new tab to open
                    WebDriverWait(driver, 5).until(EC.number_of_windows_to_be(2))

                    # Switch focus to the new tab
                    new_tab_handle = [handle for handle in driver.window_handles if handle != main_window_handle][0]
                    driver.switch_to.window(new_tab_handle)

                    # Wait for the job description to load in the new tab
                    job_desc_element = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.ID, "jobDescriptionText"))
                    )
                    description = job_desc_element.text.strip()

                except TimeoutException:
                    print(f" Description extraction failed (Timeout) for: {title} in new tab.")
                except Exception as e:
                    print(f" An error occurred while opening/extracting description for {title}: {e}")
                finally:
                    # 3. Close the new tab and switch back to the main search tab
                    driver.close()
                    driver.switch_to.window(main_window_handle)
            else:
                # if no link was found
                print(f" Could not extract link for job: {title}. Skipping description.")

            # Append job data
            jobs.append({
                "title": title,
                "company": company,
                "location": scraped_location,
                "link": link,
                "description": description,
                "portal": source_name
            })

        driver.quit()
        time.sleep(random.uniform(2, 5))

    print(f"Finished scraping Indeed. Found {len(jobs)} total job listings.")
    return jobs

# Local Execution Test Block

if __name__ == "__main__":
    # case 1: Search with location
    job_role_1 = input("Enter the job role you want to search on Indeed (e.g., 'data analyst'): ").strip()
    job_location_1 = input("Enter the location (e.g., 'Bangalore'): ").strip()

    indeed_jobs_1 = get_indeed_jobs(job_role_1, location=job_location_1, pages=1)

    print("\nSample Indeed Jobs (With Location):")
    pprint(indeed_jobs_1[:3])
    print(f"\nTotal jobs retrieved (With Location): {len(indeed_jobs_1)}")

    print("-" * 30)

    # case 2: Search without location (default scraping)
    job_role_2 = input("Enter a second job role (no location): ").strip()
    indeed_jobs_2 = get_indeed_jobs(job_role_2, pages=1)

    print("\nSample Indeed Jobs (Default Location):")
    pprint(indeed_jobs_2[:3])
    print(f"\nTotal jobs retrieved (Default Location): {len(indeed_jobs_2)}")