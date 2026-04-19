from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from jobspy_mcp_server.jobspy_scrapers.bayt import BaytScraper
from jobspy_mcp_server.jobspy_scrapers.berlinstartupjobs import BerlinStartupJobsScraper
from jobspy_mcp_server.jobspy_scrapers.eustartups import EuStartupsScraper
from jobspy_mcp_server.jobspy_scrapers.glassdoor import Glassdoor
from jobspy_mcp_server.jobspy_scrapers.google import Google
from jobspy_mcp_server.jobspy_scrapers.indeed import Indeed
from jobspy_mcp_server.jobspy_scrapers.join import JoinScraper
from jobspy_mcp_server.jobspy_scrapers.linkedin import LinkedIn
from jobspy_mcp_server.jobspy_scrapers.naukri import Naukri
from jobspy_mcp_server.jobspy_scrapers.stepstone import StepstoneScraper
from jobspy_mcp_server.jobspy_scrapers.welcometothejungle import WelcomeToTheJungleScraper
from jobspy_mcp_server.jobspy_scrapers.xing import XingScraper
from jobspy_mcp_server.jobspy_scrapers.model import JobType, Location, JobResponse, Country
from jobspy_mcp_server.jobspy_scrapers.model import SalarySource, ScraperInput, Site
from jobspy_mcp_server.jobspy_scrapers.util import (
    convert_to_annual,
    create_logger,
    desired_order,
    extract_salary,
    infer_work_mode,
    get_enum_from_value,
    map_str_to_site,
    normalize_job_type_value,
    normalize_work_mode,
    set_logger_level,
)
from jobspy_mcp_server.jobspy_scrapers.ziprecruiter import ZipRecruiter


core_log = create_logger("Core")


def scrape_jobs(
    site_name: str | list[str] | Site | list[Site] | None = None,
    search_term: str | None = None,
    google_search_term: str | None = None,
    cities: list[str] | None = None,
    is_remote: bool = False,
    work_mode: str | None = None,
    job_type: str | None = None,
    easy_apply: bool | None = None,
    results_wanted: int = 15,
    country_indeed: str = "usa",
    proxies: list[str] | str | None = None,
    ca_cert: str | None = None,
    description_format: str = "markdown",
    linkedin_fetch_description: bool | None = True,
    linkedin_company_ids: list[int] | None = None,
    offset: int | None = 0,
    hours_old: int = None,
    enforce_annual_salary: bool = False,
    verbose: int = 0,
    user_agent: str = None,
    # Deprecated parameters (kept for backward compatibility, but ignored)
    location: str | None = None,
    distance: int | None = None,
    **kwargs,
) -> pd.DataFrame:
    """
    Scrapes job data from job boards concurrently
    
    Args:
        site_name: Job board(s) to scrape
        search_term: Job search keywords
        cities: List of cities to search (e.g., ['Munich', 'Berlin', 'Darmstadt'])
        is_remote: Filter for remote jobs only
        job_type: Type of employment
        easy_apply: Filter for jobs with easy apply
        results_wanted: Number of results per city
        country_indeed: Country for job search
        ... other parameters ...
    
    Returns: Pandas DataFrame containing job data
    
    Note: The 'location' and 'distance' parameters are deprecated and will be ignored.
          Use 'cities' parameter instead.
    """
    if location is not None or distance is not None:
        import warnings
        warnings.warn(
            "The 'location' and 'distance' parameters are deprecated. Use 'cities' instead. "
            "Example: scrape_jobs(cities=['Munich', 'Berlin'], ...)",
            DeprecationWarning,
            stacklevel=2
        )
    
    SCRAPER_MAPPING = {
        Site.LINKEDIN: LinkedIn,
        Site.INDEED: Indeed,
        Site.ZIP_RECRUITER: ZipRecruiter,
        Site.GLASSDOOR: Glassdoor,
        Site.GOOGLE: Google,
        Site.BAYT: BaytScraper,
        Site.NAUKRI: Naukri,
        Site.STEPSTONE: StepstoneScraper,
        Site.XING: XingScraper,
        Site.BERLIN_STARTUP_JOBS: BerlinStartupJobsScraper,
        Site.WELCOME_TO_THE_JUNGLE: WelcomeToTheJungleScraper,
        Site.EU_STARTUPS: EuStartupsScraper,
        Site.JOIN: JoinScraper,
    }
    set_logger_level(verbose)
    job_type = get_enum_from_value(job_type) if job_type else None
    normalized_work_mode = normalize_work_mode(work_mode)

    def get_site_type():
        site_types = list(Site)
        if isinstance(site_name, str):
            site_types = [map_str_to_site(site_name)]
        elif isinstance(site_name, Site):
            site_types = [site_name]
        elif isinstance(site_name, list):
            site_types = [
                map_str_to_site(site) if isinstance(site, str) else site
                for site in site_name
            ]
        return site_types

    country_enum = Country.from_string(country_indeed)

    # Handle multi-city orchestration
    # If cities are specified, we'll create one ScraperInput per city
    # Otherwise, create a single ScraperInput with no location
    cities_to_search = cities if cities else [None]
    
    def create_scraper_input_for_city(
        city: str | None,
        city_results_wanted: int,
    ) -> ScraperInput:
        """Create a ScraperInput for a specific city (or no city filter if city is None)"""
        return ScraperInput(
            site_type=get_site_type(),
            country=country_enum,
            search_term=search_term,
            google_search_term=google_search_term,
            location=city,  # Temporarily use location field for backward compatibility with scrapers
            cities=[city] if city else None,
            is_remote=is_remote,
            work_mode=normalized_work_mode,
            job_type=job_type,
            easy_apply=easy_apply,
            description_format=description_format,
            linkedin_fetch_description=linkedin_fetch_description,
            results_wanted=city_results_wanted,
            linkedin_company_ids=linkedin_company_ids,
            offset=offset,
            hours_old=hours_old,
        )

    def scrape_site(site: Site, scraper_input: ScraperInput) -> tuple[str, JobResponse]:
        scraper_class = SCRAPER_MAPPING[site]
        scraper = scraper_class(proxies=proxies, ca_cert=ca_cert, user_agent=user_agent)
        scraped_data: JobResponse = scraper.scrape(scraper_input)
        display_names = {"Zip_recruiter": "ZipRecruiter", "Linkedin": "LinkedIn"}
        cap_name = site.value.capitalize()
        display_name = display_names.get(cap_name, cap_name)
        create_logger(display_name).info("finished scraping")
        return site.value, scraped_data

    selected_site_types = get_site_type()

    # Aggregate results from all cities with per-site caps.
    all_jobs_by_site = {}
    site_errors: list[dict[str, str | None]] = []
    per_site_cap = max(0, results_wanted)
    site_counts: dict[str, int] = {site.value: 0 for site in selected_site_types}
    site_attempted_cities: dict[str, list[str | None]] = {site.value: [] for site in selected_site_types}
    site_found_jobs: dict[str, bool] = {site.value: False for site in selected_site_types}
    
    for city in cities_to_search:
        active_sites = [site for site in selected_site_types if site_counts[site.value] < per_site_cap]
        if not active_sites:
            break
        max_remaining_for_active_site = max(
            (per_site_cap - site_counts[site.value]) for site in active_sites
        )
        scraper_input = create_scraper_input_for_city(city, max_remaining_for_active_site)

        with ThreadPoolExecutor() as executor:
            future_to_site = {
                executor.submit(scrape_site, site, scraper_input): site for site in active_sites
            }

            for future in as_completed(future_to_site):
                site = future_to_site[future]
                site_attempted_cities[site.value].append(city)
                try:
                    site_value, scraped_data = future.result()
                except Exception as exc:
                    error_text = str(exc)
                    site_errors.append(
                        {
                            "site": site.value,
                            "city": city,
                            "message": error_text,
                        }
                    )
                    core_log.error(
                        "Failed scraping site=%s city=%s: %s",
                        site.value,
                        city,
                        error_text,
                    )
                    continue
                if site_value not in all_jobs_by_site:
                    all_jobs_by_site[site_value] = []
                site_remaining = per_site_cap - site_counts[site_value]
                if site_remaining <= 0:
                    continue
                jobs_to_add = scraped_data.jobs[:site_remaining]
                all_jobs_by_site[site_value].extend(jobs_to_add)
                site_counts[site_value] += len(jobs_to_add)
                if jobs_to_add:
                    site_found_jobs[site_value] = True

    for site in selected_site_types:
        if not site_found_jobs[site.value]:
            attempted = [city for city in site_attempted_cities[site.value] if city]
            attempted_text = f" Attempted cities: {attempted}." if attempted else ""
            site_errors.append(
                {
                    "site": site.value,
                    "city": None,
                    "message": f"No jobs found for site with given filters.{attempted_text}",
                }
            )

    # Convert aggregated results to DataFrame format
    jobs_dfs: list[pd.DataFrame] = []
    
    for site, job_list in all_jobs_by_site.items():
        for job in job_list:
            job_data = job.model_dump()
            job_data["site"] = site
            job_data["company"] = job_data["company_name"]
            job_data["job_type"] = (
                ", ".join(job_type.value[0] for job_type in job_data["job_type"])
                if job_data["job_type"]
                else None
            )
            job_data["job_type"] = normalize_job_type_value(job_data["job_type"])
            job_data["emails"] = (
                ", ".join(job_data["emails"]) if job_data["emails"] else None
            )
            if job_data["location"]:
                job_data["location"] = Location(
                    **job_data["location"]
                ).display_location()

            # Handle compensation
            compensation_obj = job_data.get("compensation")
            if compensation_obj and isinstance(compensation_obj, dict):
                job_data["interval"] = (
                    compensation_obj.get("interval").value
                    if compensation_obj.get("interval")
                    else None
                )
                job_data["min_amount"] = compensation_obj.get("min_amount")
                job_data["max_amount"] = compensation_obj.get("max_amount")
                job_data["currency"] = compensation_obj.get("currency", "USD")
                job_data["salary_source"] = SalarySource.DIRECT_DATA.value
                if enforce_annual_salary and (
                    job_data["interval"]
                    and job_data["interval"] != "yearly"
                    and job_data["min_amount"]
                    and job_data["max_amount"]
                ):
                    convert_to_annual(job_data)
            else:
                if country_enum == Country.USA:
                    (
                        job_data["interval"],
                        job_data["min_amount"],
                        job_data["max_amount"],
                        job_data["currency"],
                    ) = extract_salary(
                        job_data["description"],
                        enforce_annual_salary=enforce_annual_salary,
                    )
                    job_data["salary_source"] = SalarySource.DESCRIPTION.value

            job_data["salary_source"] = (
                job_data["salary_source"]
                if "min_amount" in job_data and job_data["min_amount"]
                else None
            )

            job_data["skills"] = (
                ", ".join(job_data["skills"]) if job_data["skills"] else None
            )

            inferred_work_mode = infer_work_mode(
                work_from_home_type=job_data.get("work_from_home_type"),
                is_remote=job_data.get("is_remote"),
                title=job_data.get("title"),
                description=job_data.get("description"),
                location=job_data.get("location"),
            )
            job_data["work_mode"] = inferred_work_mode

            if normalized_work_mode and inferred_work_mode != normalized_work_mode:
                continue

            job_df = pd.DataFrame([job_data])
            jobs_dfs.append(job_df)

    if jobs_dfs:
        # Step 1: Filter out all-NA columns from each DataFrame before concatenation
        filtered_dfs = [df.dropna(axis=1, how="all") for df in jobs_dfs]

        # Step 2: Concatenate the filtered DataFrames
        jobs_df = pd.concat(filtered_dfs, ignore_index=True)

        # Step 3: Ensure all desired columns are present, adding missing ones as empty
        for column in desired_order:
            if column not in jobs_df.columns:
                jobs_df[column] = None  # Add missing columns as empty

        # Reorder the DataFrame according to the desired order
        jobs_df = jobs_df[desired_order]

        # Step 4: Sort the DataFrame as required
        jobs_df = jobs_df.sort_values(
            by=["site", "date_posted"], ascending=[True, False]
        ).reset_index(drop=True)
        jobs_df.attrs["site_errors"] = site_errors
        return jobs_df
    else:
        jobs_df = pd.DataFrame()
        jobs_df.attrs["site_errors"] = site_errors
        return jobs_df