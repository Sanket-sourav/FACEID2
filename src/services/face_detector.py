"""
Wraps InsightFace's FaceAnalysis app.

buffalo_l bundles a SCRFD detector + an ArcFace (ResNet50) recognition model,
so a single .get(frame) call returns, per detected face: bbox, 5-point
landmarks (kps), detection confidence, and an already L2-normalized 512-d
embedding. We don't need separate detector/recognizer ONNX sessions.
"""

from dataclasses import dataclass
from typing import List

import numpy as np

from src import config


@dataclass
class DetectedFace:
    bbox: np.ndarray          # [x1, y1, x2, y2]
    landmarks: np.ndarray     # 5x2 keypoints
    det_score: float
    embedding: np.ndarray     # 512-d, L2-normalized


class FaceDetector:
    def __init__(self, model_pack: str = config.MODEL_PACK, ctx_id: int = -1):
        from insightface.app import FaceAnalysis

        self._app = FaceAnalysis(name=model_pack)
        # ctx_id=-1 -> CPU. Set to 0 for GPU if you have onnxruntime-gpu installed.
        # det_thresh is passed explicitly so config.MIN_DETECTION_CONFIDENCE is the
        # single source of truth (InsightFace's own default here is 0.5).
        self._app.prepare(ctx_id=ctx_id, det_size=config.DETECTOR_SIZE, det_thresh=config.MIN_DETECTION_CONFIDENCE)

    def detect(self, frame_bgr: np.ndarray) -> List[DetectedFace]:
        faces = self._app.get(frame_bgr)
        results = []
        for f in faces:
            if f.det_score < config.MIN_DETECTION_CONFIDENCE:
                continue
            results.append(
                DetectedFace(
                    bbox=f.bbox,
                    landmarks=f.kps,
                    det_score=float(f.det_score),
                    embedding=f.normed_embedding,
                )
            )
        return results
