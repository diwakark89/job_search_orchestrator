from __future__ import annotations

import random
import re
import time
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from jobspy_mcp_server.jobspy_scrapers.berlinstartupjobs.constant import headers
from jobspy_mcp_server.jobspy_scrapers.berlinstartupjobs.util import (
    parse_location,
    parse_post_date,
)
from jobspy_mcp_server.jobspy_scrapers.exception import BerlinStartupJobsException
from jobspy_mcp_server.jobspy_scrapers.model import (
    Compensation,
    CompensationInterval,
    Country,
    DescriptionFormat,
    JobPost,
    JobResponse,
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

log = create_logger("BerlinStartupJobs")


class BerlinStartupJobsScraper(Scraper):
    base_url = "https://berlinstartupjobs.com"
    delay = 2
    band_delay = 3

    def __init__(
        self,
        proxies: list[str] | str | None = None,
        ca_cert: str | None = None,
        user_agent: str | None = None,
    ):
        super().__init__(Site.BERLIN_STARTUP_JOBS, proxies=proxies, ca_cert=ca_cert, user_agent=user_agent)
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
            log.info(f"Fetching Berlin Startup Jobs page {page}")
            try:
                cards = self._fetch_jobs(scraper_input.search_term, page)
            except Exception as exc:
                raise BerlinStartupJobsException(str(exc)) from exc

            if not cards:
                break

            initial_count = len(job_list)
            for card in cards:
                try:
                    job_post = self._extract_job_info(card)
                except Exception as exc:
                    log.error(f"BerlinStartupJobs: Error extracting job info: {exc}")
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

    def _fetch_jobs(self, query: str | None, page: int) -> list:
        if query:
            url = f"{self.base_url}/jobs/page/{page}/?s={quote_plus(query)}"
        else:
            url = f"{self.base_url}/jobs/page/{page}/"
        response = self.session.get(url, timeout=self.scraper_input.request_timeout if self.scraper_input else 30)
        if response.status_code == 404:
            return []
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        cards = soup.select("article.bjs-jlid")
        if not cards:
            cards = soup.select("article.job, article.post")
        log.debug(f"Found {len(cards)} job cards on page {page}")
        return cards

    def _extract_job_info(self, card: BeautifulSoup) -> JobPost | None:
        title_tag = card.select_one("h4.bjs-jlid__h, h2 a, h3 a")
        title_link = title_tag.find("a") if title_tag and title_tag.name in ("h2", "h3", "h4") else title_tag
        if title_tag and not title_link:
            title_link = title_tag.find("a")
        title = (title_link.get_text(strip=True) if title_link else (title_tag.get_text(strip=True) if title_tag else None))
        if not title:
            return None

        href = title_link.get("href") if title_link and hasattr(title_link, "get") else None
        if not href:
            link = card.find("a", href=True)
            href = link["href"] if link else None
        if not href:
            return None
        job_url = href if href.startswith("http") else urljoin(self.base_url, href)

        company_tag = card.select_one(".bjs-jlid__company a, .bjs-jlid__company, .company a, .company")
        company_name = company_tag.get_text(strip=True) if company_tag else None

        excerpt_tag = card.select_one(".bjs-jlid__excerpt, .entry-summary, .excerpt")
        excerpt = excerpt_tag.get_text(" ", strip=True) if excerpt_tag else None

        cats_tag = card.select_one(".bjs-jlid__cats, .bjs-jlid__tags, .job-tags")
        cats_text = cats_tag.get_text(" ", strip=True).lower() if cats_tag else ""
        is_remote = "remote" in cats_text

        post_id = card.get("id") or ""
        slug = re.sub(r"[^A-Za-z0-9]+", "-", job_url.rstrip("/").split("/")[-1] or post_id) or str(abs(hash(job_url)))
        job_id = f"berlinstartupjobs-{slug}"

        date_tag = card.select_one("time")
        date_posted = None
        if date_tag:
            date_posted = parse_post_date(date_tag.get("datetime") or date_tag.get_text(strip=True))

        description = None
        description_source = None
        compensation = None
        if self.scraper_input and self.scraper_input.linkedin_fetch_description:
            description, salary_text = self._fetch_job_description(job_url)
            description_source = "detail_page" if description else None
            compensation = self._build_compensation(salary_text or excerpt)
        else:
            compensation = self._build_compensation(excerpt)

        return JobPost(
            id=job_id,
            title=title,
            company_name=company_name,
            location=Location(country=Country.GERMANY, city="Berlin"),
            job_url=job_url,
            description=description or excerpt,
            description_source=description_source,
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
                soup.select_one("div.bjs-jlid__main")
                or soup.select_one("div.entry-content")
                or soup.select_one("article .content")
            )
            if not content_node:
                return None, None

            salary_text = None
            salary_node = content_node.find(string=re.compile(r"(salary|gehalt|€|EUR)", re.I))
            if salary_node:
                salary_text = str(salary_node).strip()

            html_text = str(content_node)
            if self.scraper_input.description_format == DescriptionFormat.MARKDOWN:
                return markdown_converter(html_text), salary_text
            if self.scraper_input.description_format == DescriptionFormat.PLAIN:
                return plain_converter(html_text), salary_text
            return html_text, salary_text
        except Exception as exc:
            log.error(f"BerlinStartupJobs: Error fetching description: {exc}")
            return None, None

    @staticmethod
    def _build_compensation(text: str | None) -> Compensation | None:
        if not text:
            return None
        interval, min_amt, max_amt, currency = extract_salary(text)
        if not interval:
            return None
        return Compensation(
            interval=CompensationInterval(interval),
            min_amount=min_amt,
            max_amount=max_amt,
            currency=currency,
        )
