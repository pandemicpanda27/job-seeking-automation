from .scrapers.authentic_jobs_scraper import get_authentic_jobs
from .scrapers.indeed_scraper import get_indeed_jobs
from .scrapers.naukri_scraper import get_naukri_jobs
from cachetools import TTLCache

job_cache = TTLCache(maxsize = 500, ttl = 1200)


def fetch_all_jobs(query: str, location: str = ""):
    cache_key = f"{query.lower()}_{location.lower()}"
    
    if cache_key in job_cache:
        print("Using cached jobs")
        return job_cache[cache_key], cache_key
    
    print(f"Fetching fresh jobs for '{query}' in '{location or 'Anywhere'}'")

    print(f"Starting aggregated job search: '{query}' in location: '{location or 'Anywhere'}'")

    all_jobs = []


    all_jobs += get_authentic_jobs(query, location)
    all_jobs += get_indeed_jobs(query, location)
    all_jobs += get_naukri_jobs(query, location)

    print(f" Total unique jobs collected from all portals: {len(all_jobs)}")
    
    # caching
    job_cache[cache_key] = all_jobs
    for i in all_jobs[:5]:
       print("SAMPLE JOB: ", i)
    return all_jobs, cache_key