"""Pengujian csais/sources.py: negara sumber dari TLD domain."""

import pytest

from csais import sources


@pytest.mark.parametrize(
    "domain,expected",
    [
        ("detik.com", "unknown"),
        ("kompas.id", "ID"),
        ("sulsel.fajar.co.id", "ID"),
        ("bbc.co.uk", "GB"),
        ("tempo.co", "unknown"),
        ("industrialcyber.co", "unknown"),
        ("eltiempo.com.co", "CO"),
        ("abc.gov.co", "CO"),
        ("some.tv", "unknown"),
        ("cbc.ca", "CA"),
        ("localhost", "unknown"),
    ],
)
def test_country_of(domain, expected):
    assert sources.country_of(domain) == expected
