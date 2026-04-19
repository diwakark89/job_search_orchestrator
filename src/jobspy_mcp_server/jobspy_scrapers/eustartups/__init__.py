from __future__ import annotations

import random
import re
import time
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from jobspy_mcp_server.jobspy_scrapers.eustartups.constant import headers
from jobspy_mcp_server.jobspy_scrapers.eustartups.util import parse_location, parse_post_date
from jobspy_mcp_server.jobspy_scrapers.exception import EuStartupsException
from jobspy_mcp_server.jobspy_scrapers.model import (
    Compensation,
    CompensationInterval,
    DescriptionFormat,
    JobPost,
    JobResponse,
    JobType,
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

log = create_logger("EuStartups")


class EuStartupsScraper(Scraper):
    base_url = "https://jobs.eu-startups.com"
    delay = 2
    band_delay = 3

    def __init__(
        self,
        proxies: list[str] | str | None = None,
        ca_cert: str | None = None,
        user_agent: str | None = None,
    ):
        super().__init__(Site.EU_STARTUPS, proxies=proxies, ca_cert=ca_cert, user_agent=user_agent)
        self.scraper_input: ScraperInput | None = None
        self.session = None

    def scrape(self, scraper_input: ScraperInput) -> JobResponse:
        self.scraper_input = scraper_input
        self.session = create_session(
            proxies=self.proxies, ca_cert=self.ca_cert, is_tls=False, has_retry=True
        )
        if self.user_agent:
            headers["user-agent"] = self.user_agent
        self.session.headers.update(headers)

        job_list: list[JobPost] = []
        page = 1
        results_wanted = scraper_input.results_wanted or 10
        seen_urls: set[str] = set()

        while len(job_list) < results_wanted:
            log.info(f"Fetching EU-Startups jobs page {page}")
            try:
                cards = self._fetch_jobs(scraper_input, page)
            except Exception as exc:
                raise EuStartupsException(str(exc)) from exc
            if not cards:
                break

            initial_count = len(job_list)
            for card in cards:
                try:
                    job_post = self._extract_job_info(card)
                except Exception as exc:
                    log.error(f"EuStartups: Error extracting job info: {exc}")
                    continue
                if not job_post or job_post.job_url in seen_urls:
                    continue
                seen_urls.add(job_post.job_url)
                job_list.append(job_post)
                if len(job_list) >= results_wanted:
                    break

            if len(job_list) == initial_count:
                log.info(f"No new jobs found on page {page}. Ending pagination.")
                break

            page += 1
            time.sleep(random.uniform(self.delay, self.delay + self.band_delay))

        return JobResponse(jobs=job_list[:results_wanted])

    def _fetch_jobs(self, scraper_input: ScraperInput, page: int) -> list:
        params: list[str] = []
        if scraper_input.search_term:
            params.append(f"search_keywords={quote_plus(scraper_input.search_term)}")
        if scraper_input.location:
            params.append(f"search_location={quote_plus(scraper_input.location)}")
        elif scraper_input.is_remote:
            params.append("search_location=Remote")
        if scraper_input.job_type:
            jt_slug = self._job_type_slug(scraper_input.job_type)
            if jt_slug:
                params.append(f"job_types={jt_slug}")
        if page > 1:
            params.append(f"page={page}")

        query = "&".join(params)
        url = f"{self.base_url}/jobs/" + (f"?{query}" if query else "")
        response = self.session.get(url, timeout=scraper_input.request_timeout or 30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.select("li.job_listing")
        if not cards:
            cards = soup.select("li.job-listing, div.job_listing")
        log.debug(f"Found {len(cards)} EU-Startups job cards")
        return cards

    @staticmethod
    def _job_type_slug(job_type: JobType) -> str | None:
        mapping = {
            JobType.FULL_TIME: "full-time",
            JobType.PART_TIME: "part-time",
            JobType.CONTRACT: "freelance",
            JobType.INTERNSHIP: "internship",
            JobType.TEMPORARY: "temporary",
        }
        return mapping.get(job_type)

    def _extract_job_info(self, card: BeautifulSoup) -> JobPost | None:
        link = card.find("a", href=True)
        if not link:
            return None
        job_url = link["href"] if link["href"].startswith("http") else urljoin(self.base_url, link["href"])

        title_tag = card.select_one("h3, .position h3, .position .title")
        title = title_tag.get_text(strip=True) if title_tag else None
        if not title:
            return None

        company_tag = card.select_one(".company strong, .company .name, .company")
        company_name = company_tag.get_text(strip=True) if company_tag else None

        location_tag = card.select_one(".location, .job-location")
        location_text = location_tag.get_text(" ", strip=True) if location_tag else None
        location = parse_location(location_text)

        type_tag = card.select_one(".job-type, li.job-type")
        type_text = type_tag.get_text(strip=True).lower() if type_tag else ""
        job_types = []
        if "full" in type_text:
            job_types = [JobType.FULL_TIME]
        elif "part" in type_text:
            job_types = [JobType.PART_TIME]
        elif "intern" in type_text:
            job_types = [JobType.INTERNSHIP]
        elif "freelanc" in type_text or "contract" in type_text:
            job_types = [JobType.CONTRACT]

        is_remote = "remote" in (location_text or "").lower() or "remote" in type_text

        date_tag = card.select_one("time, .date")
        date_posted = None
        if date_tag:
            date_posted = parse_post_date(date_tag.get("datetime") or date_tag.get_text(strip=True))

        data_id = card.get("data-post-id") or card.get("data-id")
        slug = data_id or re.sub(r"[^A-Za-z0-9]+", "-", job_url.rstrip("/").split("/")[-1])
        job_id = f"eustartups-{slug or abs(hash(job_url))}"

        description = None
        description_source = None
        compensation = None
        if self.scraper_input and self.scraper_input.linkedin_fetch_description:
            description, salary_text = self._fetch_job_description(job_url)
            description_source = "detail_page" if description else None
            if salary_text:
                compensation = self._build_compensation(salary_text)

        return JobPost(
            id=job_id,
            title=title,
            company_name=company_name,
            location=location,
            job_url=job_url,
            description=description,
            description_source=description_source,
            job_type=job_types or None,
            is_remote=is_remote or None,
            date_posted=date_posted,
            compensation=compensation,
        )

    def _fetch_job_description(self, job_url: str) -> tuple[str | None, str | None]:
        try:
            response = self.session.get(job_url, timeout=15)
            if response.status_code not in range(200, 400):
                return None, None
            soup = BeautifulSoup(response.text, "html.parser")
            content_node = (
                soup.select_one("div.job_description")
                or soup.select_one("div.entry-content")
                or soup.select_one("section.job-description")
            )
            if not content_node:
                return None, None

            salary_text = None
            salary_tag = soup.select_one(".salary, li.job-salary, .job-salary")
            if salary_tag:
                salary_text = salary_tag.get_text(" ", strip=True)

            html_text = str(content_node)
            if self.scraper_input.description_format == DescriptionFormat.MARKDOWN:
                return markdown_converter(html_text), salary_text
            if self.scraper_input.description_format == DescriptionFormat.PLAIN:
                return plain_converter(html_text), salary_text
            return html_text, salary_text
        except Exception as exc:
            log.error(f"EuStartups: Error fetching description: {exc}")
            return None, None

    @staticmethod
    def _build_compensation(text: str | None) -> Compensation | None:
        if not text:
            return None
        interval, mn, mx, cur = extract_salary(text)
        if not interval:
            return None
        return Compensation(
            interval=CompensationInterval(interval), min_amount=mn, max_amount=mx, currency=cur
        )
