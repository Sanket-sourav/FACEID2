"""
Records a short webcam video to stand in for a classroom video while you
don't have real footage. Run this yourself in a terminal (needs a display
window):

    python -m src.tools.record_test_video --seconds 15 --out data/videos/test.mp4

Tip: since it's just your webcam, slowly move your face left/right/closer/
farther during the recording to simulate the "pan across the room" pattern
described in the master plan, so you get some variety across frames.
"""

import argparse
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src import config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--seconds", type=int, default=15)
    parser.add_argument("--out", type=str, default=str(config.VIDEOS_DIR / "test.mp4"))
    parser.add_argument("--fps", type=int, default=30)
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise SystemExit(f"Could not open camera index {args.camera}")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_path), fourcc, args.fps, (width, height))

    print(f"Recording {args.seconds}s to {out_path}. Press ESC/q to stop early.")
    start = time.time()
    frames_written = 0

    while time.time() - start < args.seconds:
        ok, frame = cap.read()
        if not ok:
            break
        writer.write(frame)
        frames_written += 1

        remaining = args.seconds - (time.time() - start)
        display = frame.copy()
        cv2.putText(
            display, f"REC  {remaining:0.1f}s left  [ESC=stop]",
            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2,
        )
        cv2.imshow("Recording test video", display)
        if (cv2.waitKey(1) & 0xFF) in (27, ord("q")):
            break

    cap.release()
    writer.release()
    cv2.destroyAllWindows()
    print(f"Saved {frames_written} frames to {out_path}")


if __name__ == "__main__":
    main()
