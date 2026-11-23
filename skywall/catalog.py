"""Star catalogue (HYG v4.1, Hipparcos-based; CC BY-SA 4.0) and constellation lines (Stellarium 'modern' sky culture)."""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .config import DATA_DIR
from .runner import Runner, run

CATALOG_MAG = 8.0  # stored catalogue depth; renders filter to cfg.mag_limit
CATALOG_VERSION = 3

GREEK = {"Alp": "α", "Bet": "β", "Gam": "γ", "Del": "δ", "Eps": "ε", "Zet": "ζ", "Eta": "η",
         "The": "θ", "Iot": "ι", "Kap": "κ", "Lam": "λ", "Mu": "μ", "Nu": "ν", "Xi": "ξ",
         "Omi": "ο", "Pi": "π", "Rho": "ρ", "Sig": "σ", "Tau": "τ", "Ups": "υ", "Phi": "φ",
         "Chi": "χ", "Psi": "ψ", "Ome": "ω"}
_SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def bayer_label(bayer: str, con: str) -> str:
    """HYG Bayer code + constellation → e.g. "Kap-2", "Boo" → "κ² Boo"."""
    if not bayer:
        return ""
    letter, _, num = bayer.partition("-")
    return f"{GREEK.get(letter, letter)}{num.translate(_SUPERSCRIPT)} {con}".strip()
CATALOG_EPOCH_JD = 2451545.0  # J2000: HYG positions are J2000
HYG_URL = "https://raw.githubusercontent.com/astronexus/HYG-Database/c7f7f883fe678cc7680169a50ccd7dcc49b060ce/hyg/CURRENT/hygdata_v41.csv"
STELLARIUM_APP = "org.stellarium.Stellarium"
_MODERN_INDEX = "files/share/stellarium/skycultures/modern/index.json"


class DataUnavailable(Exception):
    pass


@dataclass
class StarCatalog:
    hip: np.ndarray
    ra_deg: np.ndarray
    dec_deg: np.ndarray
    pm_ra_mas: np.ndarray
    pm_dec_mas: np.ndarray
    mag: np.ndarray
    bv: np.ndarray
    name: np.ndarray  # proper name or ""
    designation: np.ndarray  # Bayer letter, e.g. "ζ Boo", or ""


@dataclass
class Constellation:
    abbr: str
    name: str
    lines: list[list[int]]


def _stellarium_index(runner: Runner) -> Path:
    for scope in ("--user", "--system"):
        try:
            loc = runner(["flatpak", "info", scope, "--show-location", STELLARIUM_APP]).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
        path = Path(loc) / _MODERN_INDEX
        if path.exists():
            return path
    raise DataUnavailable("Stellarium (Flatpak) not found: needed once for constellation lines")


def _build_constellations(index: Path, out: Path) -> None:
    raw = json.loads(index.read_text())
    cons = [{"abbr": c["id"].split()[-1],
             "name": c.get("common_name", {}).get("native", c["id"].split()[-1]),
             "lines": c["lines"]}
            for c in raw["constellations"]]
    out.write_text(json.dumps(cons))


def _parse_hyg(csv_path: Path, mag_limit: float, keep: set[int] = frozenset()) -> dict[str, np.ndarray]:
    """Stars brighter than mag_limit, plus any HIP in `keep` (constellation-line stars)."""
    import csv
    rows, names, desigs = [], [], []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not r["hip"] or not r["mag"]:
                continue
            if float(r["mag"]) > mag_limit and int(r["hip"]) not in keep:
                continue
            rows.append((int(r["hip"]), float(r["ra"]) * 15.0, float(r["dec"]),
                         float(r["pmra"] or 0), float(r["pmdec"] or 0), float(r["mag"]),
                         float(r["ci"]) if r["ci"] else np.nan))
            names.append(r["proper"] or "")
            desigs.append(bayer_label(r["bayer"], r["con"]))
    a = np.array(rows, dtype=float)
    return {"hip": a[:, 0].astype(int), "ra_deg": a[:, 1], "dec_deg": a[:, 2],
            "pm_ra_mas": a[:, 3], "pm_dec_mas": a[:, 4], "mag": a[:, 5], "bv": a[:, 6],
            "name": np.array(names, dtype=str), "designation": np.array(desigs, dtype=str), "version": np.array(CATALOG_VERSION)}


def ensure_data(data_dir: Path = DATA_DIR, mag_limit: float = 6.5, runner: Runner = run) -> None:
    data_dir = Path(data_dir)
    cons = data_dir / "constellations.json"
    stars = data_dir / "stars.npz"
    sky = data_dir / "skyfield"
    if stars.exists() and _stars_version(stars) != CATALOG_VERSION:
        stars.unlink()  # older layout: rebuild from the cached CSV
    if cons.exists() and stars.exists() and (sky / "de421.bsp").exists():
        return
    data_dir.mkdir(parents=True, exist_ok=True)
    if not cons.exists():
        _build_constellations(_stellarium_index(runner), cons)
    try:
        from skyfield.api import Loader
        load = Loader(str(sky), verbose=False)
        load("de421.bsp")
        if not stars.exists():
            with load.open(HYG_URL, filename="hygdata_v41.csv") as f:
                src = Path(f.name)
            keep = {h for c in load_constellations(data_dir) for line in c.lines for h in line}
            np.savez(stars, **_parse_hyg(src, CATALOG_MAG, keep))
    except OSError as e:
        raise DataUnavailable(f"download failed: {e}") from e


def _stars_version(path: Path) -> int:
    try:
        with np.load(path) as z:
            return int(z["version"]) if "version" in z.files else 1
    except (OSError, ValueError):
        return 0


def load_stars(data_dir: Path = DATA_DIR, mag_limit: float = 6.5) -> StarCatalog:
    """Stars down to `mag_limit`, plus any star a constellation line needs."""
    with np.load(Path(data_dir) / "stars.npz") as z:
        cols = {k: z[k] for k in z.files if k != "version"}
    keep = {h for c in load_constellations(data_dir) for line in c.lines for h in line}
    mask = (cols["mag"] <= mag_limit) | np.isin(cols["hip"], list(keep))
    return StarCatalog(**{k: v[mask] for k, v in cols.items()})


def load_constellations(data_dir: Path = DATA_DIR) -> list[Constellation]:
    raw = json.loads((Path(data_dir) / "constellations.json").read_text())
    return [Constellation(**c) for c in raw]
