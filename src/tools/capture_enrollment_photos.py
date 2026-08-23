"""
Webcam-based enrollment photo capture, for testing the pipeline before you
have real classmate photos. Run this yourself in a terminal (needs a display
window, not through an automated agent):

    python -m src.tools.capture_enrollment_photos --name "Your Name"

Controls:
    SPACE  - capture a photo
    ESC/q  - finish

Move your head slightly between captures (angle, distance, lighting) to
mimic the "5-10 varied reference photos per student" recommendation.
Repeat this for each person in your test roster (e.g. yourself, plus a
couple of friends/family if available, to simulate a small class).
"""

import argparse
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src import config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="Student name, e.g. 'Rahul Kumar'")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--count", type=int, default=8, help="Target number of photos")
    args = parser.parse_args()

    out_dir = config.STUDENTS_DIR / args.name
    out_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise SystemExit(f"Could not open camera index {args.camera}")

    print(f"Capturing photos for '{args.name}' -> {out_dir}")
    print(f"Press SPACE to capture (target {args.count}), ESC/q to finish.")

    saved = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            print("Failed to read frame from camera")
            break

        display = frame.copy()
        cv2.putText(
            display, f"{args.name}: {saved}/{args.count}  [SPACE=capture, ESC=done]",
            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2,
        )
        cv2.imshow("Enrollment capture", display)

        key = cv2.waitKey(1) & 0xFF
        if key == 32:  # SPACE
            path = out_dir / f"photo_{saved+1:02d}.jpg"
            cv2.imwrite(str(path), frame)
            saved += 1
            print(f"  saved {path.name}")
            if saved >= args.count:
                print("Reached target count.")
                break
        elif key in (27, ord("q")):
            break

    cap.release()
    cv2.destroyAllWindows()
    print(f"Done. {saved} photos saved to {out_dir}")
    if saved < 3:
        print("WARNING: fewer than 3 photos captured — recognition quality will suffer.")


if __name__ == "__main__":
    main()
