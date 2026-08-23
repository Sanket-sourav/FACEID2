"""
Reads a video file and yields a manageable set of frames to run face
detection on, skipping near-duplicate frames (see master plan section 7:
adaptive frame selection).
"""

from dataclasses import dataclass
from typing import Iterator, Optional

import cv2
import numpy as np

from src import config


@dataclass
class VideoMetadata:
    width: int
    height: int
    fps: float
    frame_count: int
    duration_sec: float


@dataclass
class SampledFrame:
    frame_index: int
    timestamp_sec: float
    image_bgr: np.ndarray


class VideoProcessor:
    def __init__(self, video_path: str):
        self.video_path = str(video_path)
        self._cap = cv2.VideoCapture(self.video_path)
        if not self._cap.isOpened():
            raise FileNotFoundError(f"Could not open video: {video_path}")

    def get_metadata(self) -> VideoMetadata:
        fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_count = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = frame_count / fps if fps else 0.0
        return VideoMetadata(width=width, height=height, fps=fps, frame_count=frame_count, duration_sec=duration)

    def select_frames(self) -> Iterator[SampledFrame]:
        """Yields frames spaced by SAMPLE_EVERY_N_FRAMES, additionally
        dropping any frame that looks near-identical to the last KEPT frame
        (stationary camera / no new information), up to MAX_FRAMES_TO_PROCESS."""
        prev_gray: Optional[np.ndarray] = None
        kept = 0
        idx = -1

        while True:
            ok, frame = self._cap.read()
            if not ok:
                break
            idx += 1

            if idx % config.SAMPLE_EVERY_N_FRAMES != 0:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray_small = cv2.resize(gray, (160, 90))

            if prev_gray is not None:
                diff = float(np.mean(cv2.absdiff(gray_small, prev_gray)))
                if diff < config.SCENE_DIFF_THRESHOLD:
                    continue

            prev_gray = gray_small
            fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
            yield SampledFrame(frame_index=idx, timestamp_sec=idx / fps, image_bgr=frame)
            kept += 1
            if kept >= config.MAX_FRAMES_TO_PROCESS:
                break

    def release(self):
        self._cap.release()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()
