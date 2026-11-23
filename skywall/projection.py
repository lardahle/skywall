"""Projections of horizontal (az/alt) coordinates onto the screen."""

import math

import numpy as np

MAX_ANGLE_DEG = 170.0  # beyond this from the centre the projection blows up


class StereographicProjection:
    def __init__(self, center_az_deg: float, center_alt_deg: float, hfov_deg: float,
                 width: int, height: int):
        self.center_az = center_az_deg
        self.center_alt = center_alt_deg
        self.hfov = hfov_deg
        self.width = width
        self.height = height
        self._scale = (width / 2) / (2 * math.tan(math.radians(hfov_deg) / 4))
        self._sin0 = math.sin(math.radians(center_alt_deg))
        self._cos0 = math.cos(math.radians(center_alt_deg))
        self._cos_limit = math.cos(math.radians(MAX_ANGLE_DEG))

    @property
    def vfov_deg(self) -> float:
        return math.degrees(4 * math.atan((self.height / self.width)
                                          * math.tan(math.radians(self.hfov) / 4)))

    def project_many(self, az_deg: np.ndarray, alt_deg: np.ndarray):
        dl = np.radians(np.asarray(az_deg, dtype=float) - self.center_az)
        phi = np.radians(np.asarray(alt_deg, dtype=float))
        sin_p, cos_p, cos_dl = np.sin(phi), np.cos(phi), np.cos(dl)
        cos_c = self._sin0 * sin_p + self._cos0 * cos_p * cos_dl
        valid = cos_c >= self._cos_limit
        k = 2.0 / (1.0 + np.where(valid, cos_c, 0.0))
        X = k * cos_p * np.sin(dl)
        Y = k * (self._cos0 * sin_p - self._sin0 * cos_p * cos_dl)
        x = self.width / 2 + X * self._scale
        y = self.height / 2 - Y * self._scale
        return x, y, valid

    def project(self, az_deg: float, alt_deg: float) -> tuple[float, float] | None:
        x, y, ok = self.project_many(np.array([az_deg]), np.array([alt_deg]))
        return (float(x[0]), float(y[0])) if ok[0] else None


PERSPECTIVE_MAX_FOV = 150.0
PERSPECTIVE_MAX_TILT = 60.0


class PerspectiveProjection:
    """A true window: a vertical image plane facing `center_az`.

    Tilt does not tip the plane (the monitor is upright); it slides the horizon so that
    the screen centre sits `center_alt_deg` above it, like eyes below the screen centre.
    The horizon stays straight and lines of equal azimuth stay vertical.
    """

    def __init__(self, center_az_deg: float, center_alt_deg: float, hfov_deg: float,
                 width: int, height: int):
        self.center_az = center_az_deg
        self.center_alt = max(-PERSPECTIVE_MAX_TILT, min(PERSPECTIVE_MAX_TILT, center_alt_deg))
        self.hfov = min(hfov_deg, PERSPECTIVE_MAX_FOV)
        self.width = width
        self.height = height
        self._scale = (width / 2) / math.tan(math.radians(self.hfov) / 2)
        self._y0 = height / 2 + self._scale * math.tan(math.radians(self.center_alt))  # horizon row

    @property
    def vfov_deg(self) -> float:
        return math.degrees(2 * math.atan((self.height / self.width) * math.tan(math.radians(self.hfov) / 2)))

    def project_many(self, az_deg: np.ndarray, alt_deg: np.ndarray):
        dl = np.radians(np.asarray(az_deg, dtype=float) - self.center_az)
        phi = np.radians(np.asarray(alt_deg, dtype=float))
        depth = np.cos(phi) * np.cos(dl)  # distance along the facing direction
        valid = depth > 1e-3
        d = np.where(valid, depth, 1.0)
        x = self.width / 2 + self._scale * np.cos(phi) * np.sin(dl) / d
        y = self._y0 - self._scale * np.sin(phi) / d
        return x, y, valid

    def project(self, az_deg: float, alt_deg: float) -> tuple[float, float] | None:
        x, y, ok = self.project_many(np.array([az_deg]), np.array([alt_deg]))
        return (float(x[0]), float(y[0])) if ok[0] else None


def make_projection(kind: str, center_az_deg: float, center_alt_deg: float, hfov_deg: float,
                    width: int, height: int):
    cls = PerspectiveProjection if kind == "perspective" else StereographicProjection
    return cls(center_az_deg, center_alt_deg, hfov_deg, width, height)
