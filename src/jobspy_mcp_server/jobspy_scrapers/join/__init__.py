from __future__ import annotations

import os
import random
import re
import time
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from jobspy_mcp_server.jobspy_scrapers.exception import JoinException
from jobspy_mcp_server.jobspy_scrapers.join.constant import headers
from jobspy_mcp_server.jobspy_scrapers.join.util import (
    parse_location,
    parse_post_date,
    truthy_env,
)
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

log = create_logger("Join")


class JoinScraper(Scraper):
    base_url = "https://join.com"
    delay = 2
    band_delay = 3

    def __init__(
        self,
        proxies: list[str] | str | None = None,
        ca_cert: str | None = None,
        user_agent: str | None = None,
    ):
        super().__init__(Site.JOIN, proxies=proxies, ca_cert=ca_cert, user_agent=user_agent)
        self.scraper_input: ScraperInput | None = None
        self.session = None

    def scrape(self, scraper_input: ScraperInput) -> JobResponse:
        if truthy_env(os.getenv("JOBSPY_RESPECT_ROBOTS")):
            log.warning("JOBSPY_RESPECT_ROBOTS is set; skipping join.com (ToS-restricted).")
            return JobResponse(jobs=[])

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
            log.info(f"Fetching join.com jobs page {page}")
            try:
                cards = self._fetch_jobs(scraper_input, page)
            except Exception as exc:
                raise JoinException(str(exc)) from exc
            if not cards:
                break

            initial_count = len(job_list)
            for card in cards:
                try:
                    job_post = self._extract_job_info(card)
                except Exception as exc:
                    log.error(f"Join: Error extracting job info: {exc}")
                    continue
                if not job_post or job_post.job_url in seen_urls:
                    continue
                if scraper_input.is_remote and not (job_post.is_remote or False):
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
            params.append(f"search={quote_plus(scraper_input.search_term)}")
        if scraper_input.location:
            params.append(f"location={quote_plus(scraper_input.location)}")
        if scraper_input.is_remote:
            params.append("remote=true")
        if page > 1:
            params.append(f"page={page}")

        url = f"{self.base_url}/jobs" + (f"?{'&'.join(params)}" if params else "")
        response = self.session.get(url, timeout=scraper_input.request_timeout or 30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        cards = soup.select("a[href*='/jobs/'][data-testid='job-card']")
        if not cards:
            cards = [
                a for a in soup.find_all("a", href=True)
                if re.search(r"/companies/[^/]+/jobs/", a["href"])
            ]
        log.debug(f"Found {len(cards)} join.com job cards")
        return cards

    def _extract_job_info(self, card: BeautifulSoup) -> JobPost | None:
        href = card.get("href") if hasattr(card, "get") else None
        if not href:
            return None
        job_url = href if href.startswith("http") else urljoin(self.base_url, href)

        title_tag = card.select_one("[data-testid='job-card-title'], h3, h2")
        title = title_tag.get_text(strip=True) if title_tag else card.get_text(" ", strip=True)[:120]
        if not title:
            return None

        company_tag = card.select_one("[data-testid='company-name'], [data-testid='job-card-company']")
        company_name = company_tag.get_text(strip=True) if company_tag else None
        if not company_name:
            m = re.search(r"/companies/([^/]+)/jobs/", job_url)
            company_name = m.group(1).replace("-", " ").title() if m else None

        location_tag = card.select_one("[data-testid='job-location'], [data-testid='job-card-location']")
        location_text = location_tag.get_text(" ", strip=True) if location_tag else None
        location = parse_location(location_text)

        type_tag = card.select_one("[data-testid='employment-type'], [data-testid='job-card-employment-type']")
        type_text = type_tag.get_text(strip=True).lower() if type_tag else ""
        job_types = self._infer_job_types(type_text)

        is_remote = "remote" in (location_text or "").lower() or "remote" in type_text

        slug = re.sub(r"[^A-Za-z0-9]+", "-", job_url.rstrip("/").split("/")[-1])
        job_id = f"join-{slug or abs(hash(job_url))}"

        description = None
        description_source = None
        compensation = None
        if self.scraper_input and self.scraper_input.linkedin_fetch_description:
            description, salary_text = self._fetch_job_description(job_url)
            description_source = "detail_page" if description else None
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
            compensation=compensation,
        )

    @staticmethod
    def _infer_job_types(text: str) -> list[JobType]:
        if not text:
            return []
        if "full" in text:
            return [JobType.FULL_TIME]
        if "part" in text:
            return [JobType.PART_TIME]
        if "intern" in text:
            return [JobType.INTERNSHIP]
        if "freelanc" in text or "contract" in text:
            return [JobType.CONTRACT]
        if "temp" in text:
            return [JobType.TEMPORARY]
        return []

    def _fetch_job_description(self, job_url: str) -> tuple[str | None, str | None]:
        try:
            response = self.session.get(job_url, timeout=15)
            if response.status_code not in range(200, 400):
                return None, None
            soup = BeautifulSoup(response.text, "html.parser")
            content_node = (
                soup.select_one("[data-testid='job-description']")
                or soup.select_one("section.job-description")
                or soup.find("div", class_=re.compile(r"description", re.I))
            )
            if not content_node:
                return None, None

            salary_tag = soup.select_one("[data-testid='salary'], [data-testid='job-salary']")
            salary_text = salary_tag.get_text(" ", strip=True) if salary_tag else None

            html_text = str(content_node)
            if self.scraper_input.description_format == DescriptionFormat.MARKDOWN:
                return markdown_converter(html_text), salary_text
            if self.scraper_input.description_format == DescriptionFormat.PLAIN:
                return plain_converter(html_text), salary_text
            return html_text, salary_text
        except Exception as exc:
            log.error(f"Join: Error fetching description: {exc}")
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
