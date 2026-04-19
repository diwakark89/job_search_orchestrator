from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ScraperPort(Protocol):
    """Orchestrator-owned interface for any job-scraping backend.

    All concrete adapters must implement ``search`` with this exact signature.
    Callers in the service layer depend only on this protocol — never on a
    concrete implementation.
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
        """Execute a job search and return a (jobs, site_errors) tuple.

        Args:
            site_name: Job-board identifiers to query.
            search_term: Keywords for the search.
            cities: Optional list of city names to restrict the search.
            results_wanted: Maximum number of results to retrieve.
            job_type: Employment type filter (e.g. ``'fulltime'``).
            work_mode: Work-mode filter (e.g. ``'remote'``).
            is_remote: Explicit remote filter; ``None`` defers to preference defaults.
            hours_old: Maximum age in hours for returned listings.
            easy_apply: Whether to restrict to easy-apply listings.
            country_indeed: Country for Indeed / Glassdoor queries.
            linkedin_fetch_description: Fetch full descriptions from LinkedIn.
            offset: Pagination offset.
            verbose: Verbosity level forwarded to the underlying scraper.

        Returns:
            A 2-tuple of:
            - ``jobs``: list of normalised job dicts (``NormalizedJob``-compatible).
            - ``site_errors``: list of per-site error dicts, or ``None``.

        Raises:
            RuntimeError: If the underlying scraper raises an unrecoverable error.
        """
        ...
