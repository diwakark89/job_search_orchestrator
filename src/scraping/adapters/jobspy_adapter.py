from __future__ import annotations

from typing import Any

from jobspy_mcp_server.jobspy_scrapers import scrape_jobs as _scrape_jobs

from scraping.output import build_jobs_json_payload


class JobspyAdapter:
    """Concrete ScraperPort implementation backed by the vendored jobspy_mcp_server package.

    This adapter is the single point of coupling between the orchestrator service layer
    and the underlying JobSpy scraper library.  Changing the vendored package only
    requires updating this file.
    """

    def search(
        self,
        *,
        site_name: list[str],
        search_term: str,
        cities: list[str] | None,
        results_wanted: int,
        job_type: str | None,
        work_mode: str | None,
        is_remote: bool | None,
        hours_old: int,
        easy_apply: bool,
        country_indeed: str | None,
        linkedin_fetch_description: bool,
        offset: int,
        verbose: int,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]] | None]:
        """Invoke the vendored jobspy scraper and return normalised (jobs, site_errors).

        Raises:
            RuntimeError: Wraps any exception raised by the underlying scraper so
                callers do not need to handle jobspy-specific exception types.
        """
        try:
            jobs_df = _scrape_jobs(
                site_name=site_name,
                search_term=search_term,
                cities=cities,
                results_wanted=results_wanted,
                job_type=job_type,
                work_mode=work_mode,
                is_remote=is_remote,
                hours_old=hours_old,
                easy_apply=easy_apply,
                country_indeed=country_indeed,
                linkedin_fetch_description=linkedin_fetch_description,
                offset=offset,
                verbose=verbose,
                description_format="markdown",
            )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Job search failed: {exc}") from exc

        site_errors: list[dict[str, Any]] | None = (
            jobs_df.attrs.get("site_errors") if hasattr(jobs_df, "attrs") else None
        )
        jobs: list[dict[str, Any]] = []
        if not jobs_df.empty:
            jobs = [dict(job) for job in build_jobs_json_payload(jobs_df)]

        return jobs, site_errors
