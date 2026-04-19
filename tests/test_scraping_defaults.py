"""Unit tests for the request → effective-params resolver."""
from __future__ import annotations

import pytest

from scraping.defaults import EffectiveSearchParams, resolve_effective_request
from scraping.preferences import RuntimePreferenceDefaults
from scraping.requests import JobSearchRequest


def _defaults(
    *,
    search_term: str | None = "engineer",
    cities: list[str] | None = None,
    country: str = "USA",
    prefer_remote: bool = True,
) -> RuntimePreferenceDefaults:
    return RuntimePreferenceDefaults(
        default_search_term=search_term,
        default_cities=list(cities) if cities is not None else [],
        default_country_indeed=country,
        prefer_remote=prefer_remote,
        prefer_hybrid=False,
        min_salary_eur=0,
        seniority=None,
    )


class TestResolveEffectiveRequest:
    def test_falls_back_to_default_search_term(self) -> None:
        req = JobSearchRequest()
        out = resolve_effective_request(req, _defaults(search_term="python developer"))
        assert isinstance(out, EffectiveSearchParams)
        assert out.search_term == "python developer"

    def test_request_search_term_overrides_default(self) -> None:
        req = JobSearchRequest(search_term="rust")
        out = resolve_effective_request(req, _defaults(search_term="python"))
        assert out.search_term == "rust"

    def test_missing_search_term_raises(self) -> None:
        req = JobSearchRequest()
        with pytest.raises(ValueError, match="search_term is required"):
            resolve_effective_request(req, _defaults(search_term=None))

    def test_cities_default_when_request_omits(self) -> None:
        req = JobSearchRequest(search_term="x")
        out = resolve_effective_request(req, _defaults(cities=["Berlin"]))
        assert out.cities == ["Berlin"]

    def test_cities_explicit_overrides_default(self) -> None:
        req = JobSearchRequest(search_term="x", cities=["Munich"])
        out = resolve_effective_request(req, _defaults(cities=["Berlin"]))
        assert out.cities == ["Munich"]

    def test_country_default(self) -> None:
        req = JobSearchRequest(search_term="x")
        out = resolve_effective_request(req, _defaults(country="Germany"))
        assert out.country_indeed == "Germany"

    def test_is_remote_falls_back_to_prefer_remote(self) -> None:
        req = JobSearchRequest(search_term="x")
        out = resolve_effective_request(req, _defaults(prefer_remote=False))
        assert out.is_remote is False

    def test_is_remote_request_overrides_default(self) -> None:
        req = JobSearchRequest(search_term="x", is_remote=True)
        out = resolve_effective_request(req, _defaults(prefer_remote=False))
        assert out.is_remote is True

    def test_invalid_work_mode_raises(self) -> None:
        req = JobSearchRequest(search_term="x", work_mode="teleport")
        with pytest.raises(ValueError, match="Invalid work_mode"):
            resolve_effective_request(req, _defaults())

    def test_clamps_results_wanted(self) -> None:
        req = JobSearchRequest(search_term="x", results_wanted=10_000)
        out = resolve_effective_request(req, _defaults())
        assert out.results_wanted <= 50  # RESULTS_WANTED_MAX
