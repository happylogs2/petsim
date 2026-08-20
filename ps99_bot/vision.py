"""
Lightweight template matching for portal/zone-state detection.

Deliberately avoids OCR: reading exact coin counts through K/M/B suffix
formatting is slow and fragile, and you don't actually need the number -
you just need to know "is the portal unlocked yet". A single
cv2.matchTemplate call on a small crop is ~1-5ms vs ~50-200ms for
Tesseract OCR, which matters a lot when polling 15 instances in a loop.
"""
import cv2
import numpy as np


def crop(frame: np.ndarray, region: tuple) -> np.ndarray:
    """region = (x, y, w, h)"""
    x, y, w, h = region
    return frame[y:y + h, x:x + w]


def load_template(path: str) -> np.ndarray:
    tpl = cv2.imread(path, cv2.IMREAD_COLOR)
    if tpl is None:
        raise FileNotFoundError(f"Template not found: {path}")
    return tpl


def matches(frame_crop: np.ndarray, template: np.ndarray, threshold: float = 0.85) -> bool:
    if frame_crop.shape[0] < template.shape[0] or frame_crop.shape[1] < template.shape[1]:
        return False
    result = cv2.matchTemplate(frame_crop, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val >= threshold
