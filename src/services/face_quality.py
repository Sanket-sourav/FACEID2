"""
Scores a detected face crop on blur, size, and pose so low-quality
observations can be filtered out before they dilute recognition evidence
(see master plan section 9: "Bad evidence should not be allowed to dilute
good evidence").
"""

from dataclasses import dataclass

import cv2
import numpy as np

from src import config
from src.services.face_detector import DetectedFace


@dataclass
class QualityScore:
    blur: float      # 0-1, higher = sharper
    size: float       # 0-1, higher = larger face
    pose: float       # 0-1, higher = more frontal
    overall: float    # 0-1 combined score
    passed: bool


def _blur_score(face_crop_gray: np.ndarray) -> float:
    if face_crop_gray.size == 0:
        return 0.0
    variance = cv2.Laplacian(face_crop_gray, cv2.CV_64F).var()
    # Normalize against MIN_BLUR_SCORE so passing faces land around/above 0.5.
    return float(min(1.0, variance / (config.MIN_BLUR_SCORE * 2)))


def _size_score(bbox: np.ndarray) -> float:
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    min_dim = min(w, h)
    return float(min(1.0, min_dim / (config.MIN_FACE_SIZE_PX * 3)))


def _pose_score(landmarks: np.ndarray) -> float:
    """Rough frontal-ness estimate from 5-point landmarks (eyes, nose, mouth
    corners). A perfectly frontal face has the nose roughly centered
    horizontally between the eyes; large asymmetry implies a profile view."""
    left_eye, right_eye, nose, left_mouth, right_mouth = landmarks
    eye_center_x = (left_eye[0] + right_eye[0]) / 2
    eye_dist = abs(right_eye[0] - left_eye[0]) + 1e-6
    offset_ratio = abs(nose[0] - eye_center_x) / eye_dist
    # offset_ratio near 0 -> frontal; grows for profile views
    score = max(0.0, 1.0 - offset_ratio)
    return float(min(1.0, score))


def score_face(frame_bgr: np.ndarray, face: DetectedFace) -> QualityScore:
    x1, y1, x2, y2 = [int(max(0, v)) for v in face.bbox]
    crop = frame_bgr[y1:y2, x1:x2]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.size else np.zeros((1, 1), dtype=np.uint8)

    blur = _blur_score(gray)
    size = _size_score(face.bbox)
    pose = _pose_score(face.landmarks)
    det = face.det_score

    overall = float(np.clip(0.35 * blur + 0.25 * size + 0.25 * pose + 0.15 * det, 0.0, 1.0))
    passed = (
        overall >= config.MIN_QUALITY_OVERALL
        and min(face.bbox[2] - face.bbox[0], face.bbox[3] - face.bbox[1]) >= config.MIN_FACE_SIZE_PX
    )
    return QualityScore(blur=blur, size=size, pose=pose, overall=overall, passed=passed)
