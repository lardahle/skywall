"""Compute where every star and body sits in the observer's sky (no refraction)."""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from skyfield import almanac
from skyfield.api import Loader, Star, wgs84
from skyfield.units import Angle

from .catalog import CATALOG_EPOCH_JD, StarCatalog
from .config import DATA_DIR

BODIES = [("Sun", "sun"), ("Moon", "moon"), ("Mercury", "mercury"), ("Venus", "venus"),
          ("Mars", "mars"), ("Jupiter", "jupiter barycenter"), ("Saturn", "saturn barycenter"),
          ("Uranus", "uranus barycenter"), ("Neptune", "neptune barycenter")]


@dataclass
class Body:
    name: str
    az_deg: float
    alt_deg: float
    phase_fraction: float | None = None
    waxing: bool | None = None


@dataclass
class SkyScene:
    when: datetime
    star_az: np.ndarray
    star_alt: np.ndarray
    star_mag: np.ndarray
    star_bv: np.ndarray
    hip_index: dict[int, int]
    bodies: list[Body]


def compute_scene(lat: float, lon: float, elevation_m: float, when: datetime,
                  stars: StarCatalog, data_dir: Path = DATA_DIR) -> SkyScene:
    load = Loader(str(Path(data_dir) / "skyfield"), verbose=False)
    ts = load.timescale()
    eph = load("de421.bsp")
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    t = ts.from_datetime(when)
    observer = (eph["earth"] + wgs84.latlon(lat, lon, elevation_m=elevation_m)).at(t)

    star = Star(ra=Angle(degrees=stars.ra_deg), dec=Angle(degrees=stars.dec_deg),
                ra_mas_per_year=stars.pm_ra_mas, dec_mas_per_year=stars.pm_dec_mas,
                epoch=CATALOG_EPOCH_JD)
    alt, az, _ = observer.observe(star).apparent().altaz()

    bodies = []
    for name, key in BODIES:
        b_alt, b_az, _ = observer.observe(eph[key]).apparent().altaz()
        body = Body(name, float(b_az.degrees), float(b_alt.degrees))
        if name == "Moon":
            body.phase_fraction = float(almanac.fraction_illuminated(eph, "moon", t))
            body.waxing = bool(almanac.moon_phase(eph, t).degrees < 180)
        bodies.append(body)

    return SkyScene(when=when, star_az=az.degrees, star_alt=alt.degrees,
                    star_mag=stars.mag, star_bv=stars.bv,
                    hip_index={int(h): i for i, h in enumerate(stars.hip)}, bodies=bodies)
