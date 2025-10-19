from .scrapers.indeed_scraper import get_indeed_jobs
from .scrapers.naukri_scraper import get_naukri_jobs
from .scrapers.linkedin_scraper import get_linkedin_jobs
from .scrapers.authentic_jobs_scraper import get_authentic_jobs
from .scrapers.timesjobs_scraper import get_timesjobs
from .scrapers.wwr_scraper import get_wwr_jobs


def fetch_all_jobs(query: str, location: str = ""):
    """
    Safely fetch job listings from all scraper sources.
    Continues execution even if some scrapers fail.
    """
    print(f"Starting aggregated job search: '{query}' in location: '{location or 'Anywhere'}'")

    all_jobs = []

    # List of scrapers with their names for logging
    scrapers = [
        ('Indeed', get_indeed_jobs),
        ('Naukri', get_naukri_jobs),
        ('LinkedIn', get_linkedin_jobs),
        ('TimesJobs', get_timesjobs),
        ('AuthenticJobs', get_authentic_jobs),
        ('WWR', get_wwr_jobs),
    ]

    for name, scraper in scrapers:
        try:
            print(f"🔍 Running {name} scraper...")
            jobs = scraper(query, location)
            print(f"{name} returned {len(jobs)} jobs.")
            all_jobs.extend(jobs)
        except Exception as e:
            print(f"Error in {name} scraper: {e}")

    print(f"Total jobs collected from all portals: {len(all_jobs)}")
    return all_jobs
