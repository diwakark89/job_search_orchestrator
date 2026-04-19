from __future__ import annotations

import json
import os
import random
import re
import time
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from jobspy_mcp_server.jobspy_scrapers.exception import WelcomeToTheJungleException
from jobspy_mcp_server.jobspy_scrapers.model import (
    Compensation,
    CompensationInterval,
    Country,
    DescriptionFormat,
    JobPost,
    JobResponse,
    JobType,
    Location,
    Scraper,
    ScraperInput,
    Site,
)
from jobspy_mcp_server.jobspy_scrapers.util import (
    create_logger,
    create_session,
    extract_salary,
    markdown_converter,
    plain_converter,
)
from jobspy_mcp_server.jobspy_scrapers.welcometothejungle.constant import (
    ALGOLIA_API_KEY,
    ALGOLIA_APP_ID,
    ALGOLIA_INDEX,
    algolia_headers,
    site_headers,
)
from jobspy_mcp_server.jobspy_scrapers.welcometothejungle.util import (
    map_country_to_code,
    parse_iso_date,
    truthy_env,
)

log = create_logger("WelcomeToTheJungle")


class WelcomeToTheJungleScraper(Scraper):
    site_base_url = "https://www.welcometothejungle.com"
    api_base_url = f"https://{ALGOLIA_APP_ID.lower()}-dsn.algolia.net/1/indexes/{ALGOLIA_INDEX}/query"
    delay = 1
    band_delay = 2

    def __init__(
        self,
        proxies: list[str] | str | None = None,
        ca_cert: str | None = None,
        user_agent: str | None = None,
    ):
        super().__init__(Site.WELCOME_TO_THE_JUNGLE, proxies=proxies, ca_cert=ca_cert, user_agent=user_agent)
        self.scraper_input: ScraperInput | None = None
        self.session = None

    def scrape(self, scraper_input: ScraperInput) -> JobResponse:
        if truthy_env(os.getenv("JOBSPY_RESPECT_ROBOTS")):
            log.warning(
                "JOBSPY_RESPECT_ROBOTS is set; skipping Welcome to the Jungle (ToS-restricted)."
            )
            return JobResponse(jobs=[])

        self.scraper_input = scraper_input
        self.session = create_session(
            proxies=self.proxies, ca_cert=self.ca_cert, is_tls=False, has_retry=True
        )
        if self.user_agent:
            algolia_headers["user-agent"] = self.user_agent
            site_headers["user-agent"] = self.user_agent

        job_list: list[JobPost] = []
        results_wanted = scraper_input.results_wanted or 10
        hits_per_page = min(max(results_wanted, 10), 50)
        page = 0

        while len(job_list) < results_wanted:
            try:
                hits = self._fetch_hits(scraper_input, page, hits_per_page)
            except Exception as exc:
                raise WelcomeToTheJungleException(str(exc)) from exc

            if not hits:
                break

            for hit in hits:
                try:
                    job_post = self._build_job_post(hit)
                except Exception as exc:
                    log.error(f"WelcomeToTheJungle: Error building job post: {exc}")
                    continue
                if not job_post:
                    continue
                if scraper_input.is_remote and not (job_post.is_remote or False):
                    continue
                job_list.append(job_post)
                if len(job_list) >= results_wanted:
                    break

            page += 1
            if page > 20:
                break
            time.sleep(random.uniform(self.delay, self.delay + self.band_delay))

        return JobResponse(jobs=job_list[:results_wanted])

    def _fetch_hits(self, scraper_input: ScraperInput, page: int, hits_per_page: int) -> list[dict]:
        params = (
            f"x-algolia-agent=Algolia%20for%20JavaScript%20(4.22.1)%3B%20Browser"
            f"&x-algolia-api-key={ALGOLIA_API_KEY}&x-algolia-application-id={ALGOLIA_APP_ID}"
        )
        url = f"{self.api_base_url}?{params}"

        filters = self._build_filters(scraper_input)
        body = {
            "params": (
                f"query={quote_plus(scraper_input.search_term or '')}"
                f"&hitsPerPage={hits_per_page}&page={page}"
                + (f"&filters={quote_plus(filters)}" if filters else "")
            )
        }

        response = self.session.post(
            url,
            headers=algolia_headers,
            data=json.dumps(body),
            timeout=scraper_input.request_timeout or 30,
        )
        if response.status_code == 403:
            raise WelcomeToTheJungleException(
                "Algolia returned 403; the public search key likely rotated. "
                "Update ALGOLIA_API_KEY in welcometothejungle/constant.py."
            )
        response.raise_for_status()
        payload = response.json()
        return payload.get("hits", [])

    def _build_filters(self, scraper_input: ScraperInput) -> str | None:
        clauses: list[str] = []
        country_code = map_country_to_code(scraper_input.country)
        if country_code:
            clauses.append(f"offices.country_code:{country_code}")
        if scraper_input.is_remote:
            clauses.append("remote.position:'fulltime' OR remote.position:'fully_remote'")
        if scraper_input.job_type == JobType.FULL_TIME:
            clauses.append("contract_type:full_time")
        elif scraper_input.job_type == JobType.PART_TIME:
            clauses.append("contract_type:part_time")
        elif scraper_input.job_type == JobType.INTERNSHIP:
            clauses.append("contract_type:internship")
        elif scraper_input.job_type == JobType.CONTRACT:
            clauses.append("contract_type:freelance")
        return " AND ".join(clauses) if clauses else None

    def _build_job_post(self, hit: dict) -> JobPost | None:
        slug = hit.get("slug")
        organization = hit.get("organization") or {}
        org_slug = organization.get("slug")
        if not slug or not org_slug:
            return None

        language = (hit.get("language") or "en").lower()
        if language not in ("en", "fr", "de", "es", "it", "nl"):
            language = "en"
        job_url = f"{self.site_base_url}/{language}/companies/{org_slug}/jobs/{slug}"
        title = hit.get("name") or hit.get("title")
        if not title:
            return None

        offices = hit.get("offices") or []
        location = self._build_location(offices[0] if offices else {})

        is_remote = bool((hit.get("remote") or {}).get("position")) or hit.get("has_remote", False)

        compensation = self._build_compensation(hit)

        date_posted = parse_iso_date(hit.get("published_at") or hit.get("created_at"))

        description = None
        description_source = None
        if self.scraper_input and self.scraper_input.linkedin_fetch_description:
            description = self._fetch_job_description(job_url)
            description_source = "detail_page" if description else None

        return JobPost(
            id=f"welcometothejungle-{hit.get('objectID') or slug}",
            title=title,
            company_name=organization.get("name"),
            location=location,
            job_url=job_url,
            description=description,
            description_source=description_source,
            is_remote=is_remote or None,
            date_posted=date_posted,
            compensation=compensation,
            company_logo=(organization.get("logo") or {}).get("url") if isinstance(organization.get("logo"), dict) else None,
        )

    @staticmethod
    def _build_location(office: dict) -> Location | None:
        if not office:
            return None
        country_code = (office.get("country_code") or "").upper()
        country: Country | str | None = None
        if country_code:
            for c in Country:
                indeed_value = c.value[1].split(":")[0].upper()
                if indeed_value == country_code:
                    country = c
                    break
            if not country:
                country = country_code
        return Location(
            city=office.get("city") or office.get("name"),
            state=office.get("region") or office.get("state"),
            country=country,
        )

    def _build_compensation(self, hit: dict) -> Compensation | None:
        salary = hit.get("salary") or {}
        min_amt = salary.get("min")
        max_amt = salary.get("max")
        currency = salary.get("currency") or "EUR"
        period = (salary.get("period") or "").lower()
        if min_amt or max_amt:
            interval_map = {
                "year": CompensationInterval.YEARLY,
                "yearly": CompensationInterval.YEARLY,
                "month": CompensationInterval.MONTHLY,
                "monthly": CompensationInterval.MONTHLY,
                "day": CompensationInterval.DAILY,
                "daily": CompensationInterval.DAILY,
                "hour": CompensationInterval.HOURLY,
                "hourly": CompensationInterval.HOURLY,
            }
            interval = interval_map.get(period, CompensationInterval.YEARLY)
            return Compensation(
                interval=interval,
                min_amount=float(min_amt) if min_amt is not None else None,
                max_amount=float(max_amt) if max_amt is not None else None,
                currency=currency,
            )
        text_salary = hit.get("salary_text") or hit.get("salary_range")
        if not text_salary:
            return None
        interval, mn, mx, cur = extract_salary(text_salary)
        if not interval:
            return None
        return Compensation(
            interval=CompensationInterval(interval), min_amount=mn, max_amount=mx, currency=cur
        )

    def _fetch_job_description(self, job_url: str) -> str | None:
        try:
            response = self.session.get(job_url, headers=site_headers, timeout=15)
            if response.status_code not in range(200, 400):
                return None
            soup = BeautifulSoup(response.text, "html.parser")
            description_html: str | None = None
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    payload = json.loads(script.string or "{}")
                except (json.JSONDecodeError, TypeError):
                    continue
                items = payload if isinstance(payload, list) else [payload]
                for item in items:
                    if isinstance(item, dict) and item.get("@type") == "JobPosting":
                        description_html = item.get("description")
                        break
                if description_html:
                    break

            if not description_html:
                content_node = soup.select_one("div[data-testid='job-section-description']") or soup.find(
                    "div", class_=re.compile(r"description", re.I)
                )
                description_html = str(content_node) if content_node else None

            if not description_html:
                return None

            if self.scraper_input.description_format == DescriptionFormat.MARKDOWN:
                return markdown_converter(description_html)
            if self.scraper_input.description_format == DescriptionFormat.PLAIN:
                return plain_converter(description_html)
            return description_html
        except Exception as exc:
            log.error(f"WelcomeToTheJungle: Error fetching description: {exc}")
            return None
