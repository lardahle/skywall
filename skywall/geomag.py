"""Magnetic declination (World Magnetic Model) and true facing direction."""

from datetime import datetime, timezone
from functools import lru_cache

from pygeomag import GeoMag

from .config import Config


@lru_cache(maxsize=1)
def _model() -> GeoMag:
    return GeoMag(base_year=2025)


def _decimal_year(when: datetime) -> float:
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    start = datetime(when.year, 1, 1, tzinfo=timezone.utc)
    end = datetime(when.year + 1, 1, 1, tzinfo=timezone.utc)
    return when.year + (when - start) / (end - start)


def declination_deg(lat: float, lon: float, when: datetime) -> float:
    """Magnetic declination in degrees, east positive."""
    return _model().calculate(glat=lat, glon=lon, alt=0, time=_decimal_year(when)).d


def true_facing_deg(cfg: Config, when: datetime) -> float:
    if cfg.facing_reference == "true":
        return cfg.facing_deg
    return (cfg.facing_deg + declination_deg(cfg.latitude, cfg.longitude, when)) % 360.0
