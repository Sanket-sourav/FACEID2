"""
End-to-end: video -> sampled frames -> detected faces -> quality filter ->
recognition -> decision engine -> attendance report.
"""

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import List

from src import config
from src.services.decision_engine import Observation, build_observations, decide_all
from src.services.face_detector import FaceDetector
from src.services.face_quality import score_face
from src.services.face_recognizer import FaceRecognizer
from src.services.video_processor import VideoProcessor


def process_video(video_path: str, verbose: bool = True, detector=None, recognizer=None):
    detector = detector or FaceDetector()
    recognizer = recognizer or FaceRecognizer()

    observations: List[Observation] = []
    frames_processed = 0
    faces_detected = 0
    faces_passed_quality = 0

    t0 = time.time()
    with VideoProcessor(video_path) as vp:
        meta = vp.get_metadata()
        if verbose:
            print(
                f"Video: {meta.width}x{meta.height} @ {meta.fps:.1f}fps, "
                f"{meta.frame_count} frames, {meta.duration_sec:.1f}s"
            )

        for sampled in vp.select_frames():
            frames_processed += 1
            faces = detector.detect(sampled.image_bgr)
            faces_detected += len(faces)

            for face in faces:
                quality = score_face(sampled.image_bgr, face)
                if not quality.passed:
                    continue
                faces_passed_quality += 1

                candidates = recognizer.match(face.embedding, top_k=2)
                obs = build_observations(
                    frame_index=sampled.frame_index,
                    timestamp_sec=sampled.timestamp_sec,
                    candidates=candidates,
                    quality=quality.overall,
                )
                if obs is not None:
                    observations.append(obs)

    elapsed = time.time() - t0
    if verbose:
        print(
            f"Processed {frames_processed} frames in {elapsed:.1f}s | "
            f"{faces_detected} faces detected | {faces_passed_quality} passed quality | "
            f"{len(observations)} usable observations"
        )

    roster = {sid: name for sid, name in zip(recognizer.roster_ids(), recognizer.roster())}
    decisions = decide_all(observations, roster)
    return decisions, {
        "frames_processed": frames_processed,
        "faces_detected": faces_detected,
        "faces_passed_quality": faces_passed_quality,
        "observations": len(observations),
        "elapsed_sec": round(elapsed, 1),
    }


def print_report(decisions, stats):
    print("\n" + "=" * 60)
    print("ATTENDANCE RESULT")
    print("=" * 60)
    status_symbol = {
        "PRESENT": "✓",
        "PRESENT_REVIEW": "⚠",
        "NEEDS_REVIEW": "⚠",
        "NOT_OBSERVED": "✗",
    }
    for d in decisions:
        sym = status_symbol.get(d.status, "?")
        conf_str = f"{d.confidence*100:.0f}%" if d.evidence_count else "--"
        print(f"{sym} {d.student_name:<25} {d.status:<16} {conf_str:>5}   ({d.reason})")
    print("=" * 60)
    n_present = sum(1 for d in decisions if d.status == "PRESENT")
    n_review = sum(1 for d in decisions if d.requires_review)
    print(f"{len(decisions)} enrolled | {n_present} auto-present | {n_review} need review")
    print(
        f"[{stats['frames_processed']} frames, {stats['faces_detected']} faces detected, "
        f"{stats['faces_passed_quality']} passed quality, {stats['elapsed_sec']}s]"
    )


def save_report_json(decisions, stats, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"stats": stats, "decisions": [asdict(d) for d in decisions]}
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Saved JSON report to {out_path}")
