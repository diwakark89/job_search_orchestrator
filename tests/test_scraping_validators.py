"""Unit tests for pure validation/clamp helpers in scraping.validators."""
from __future__ import annotations

import pytest

from scraping.guardrails import (
    HOURS_OLD_MAX,
    HOURS_OLD_MIN,
    OFFSET_MAX,
    OFFSET_MIN,
    RESULTS_WANTED_MAX,
    RESULTS_WANTED_MIN,
    SITES_MAX,
)
from scraping.validators import (
    clamp_hours_old,
    clamp_offset,
    clamp_results_wanted,
    resolve_sites,
    validate_cities_count,
    validate_work_mode,
)


class TestResolveSites:
    def test_none_uses_defaults(self) -> None:
        assert resolve_sites(None, defaults=["linkedin"]) == ["linkedin"]

    def test_explicit_value_overrides_defaults(self) -> None:
        assert resolve_sites(["indeed"], defaults=["linkedin"]) == ["indeed"]

    def test_empty_list_rejected(self) -> None:
        with pytest.raises(ValueError, match="At least"):
            resolve_sites([], defaults=["linkedin"])

    def test_invalid_site_rejected(self) -> None:
        with pytest.raises(ValueError, match="Invalid site names"):
            resolve_sites(["not-a-real-site"], defaults=["linkedin"])

    def test_too_many_sites_rejected(self) -> None:
        with pytest.raises(ValueError, match="Maximum"):
            resolve_sites(
                ["linkedin", "indeed", "glassdoor", "google", "zip_recruiter", "naukri"],
                defaults=["linkedin"],
            )

    def test_returns_independent_copy(self) -> None:
        defaults = ["linkedin"]
        result = resolve_sites(None, defaults=defaults)
        result.append("indeed")
        assert defaults == ["linkedin"]


class TestValidateWorkMode:
    @pytest.mark.parametrize("value", [None, "remote", "hybrid", "on-site"])
    def test_accepted(self, value: str | None) -> None:
        validate_work_mode(value)

    def test_rejected(self) -> None:
        with pytest.raises(ValueError, match="Invalid work_mode"):
            validate_work_mode("teleport")


class TestValidateCitiesCount:
    def test_none_ok(self) -> None:
        validate_cities_count(None)

    def test_empty_ok(self) -> None:
        validate_cities_count([])

    def test_too_many(self) -> None:
        with pytest.raises(ValueError, match="Maximum"):
            validate_cities_count(["a", "b", "c", "d", "e", "f"])


class TestClamps:
    def test_clamp_results_wanted_low(self) -> None:
        assert clamp_results_wanted(-10) == RESULTS_WANTED_MIN

    def test_clamp_results_wanted_high(self) -> None:
        assert clamp_results_wanted(RESULTS_WANTED_MAX + 999) == RESULTS_WANTED_MAX

    def test_clamp_hours_old(self) -> None:
        assert clamp_hours_old(0) == HOURS_OLD_MIN
        assert clamp_hours_old(HOURS_OLD_MAX + 5) == HOURS_OLD_MAX

    def test_clamp_offset(self) -> None:
        assert clamp_offset(-5) == OFFSET_MIN
        assert clamp_offset(OFFSET_MAX + 5) == OFFSET_MAX
