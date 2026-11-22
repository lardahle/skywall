"""Stereographic projection of horizontal (az/alt) coordinates onto the screen."""

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
