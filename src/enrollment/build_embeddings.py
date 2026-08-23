"""
Scans data/students/<Student Name>/*.jpg, runs each enrollment photo through
the face detector, and stores the resulting embeddings in
data/embeddings/embeddings.pkl.

Expected folder layout:

    data/students/
        Rahul Kumar/
            front.jpg
            left_angle.jpg
            ...
        Priya Das/
            photo1.jpg
            ...

Student IDs are auto-assigned from folder name order unless a roster.csv
(student_id,name) is present in data/students/, in which case IDs are taken
from there.
"""

import csv
import pickle
import sys
from pathlib import Path

import cv2
import numpy as np
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src import config
from src.services.face_detector import FaceDetector

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}


def load_roster_ids(students_dir: Path) -> dict:
    """Returns {folder_name: student_id} from roster.csv if present."""
    roster_path = students_dir / "roster.csv"
    if not roster_path.exists():
        return {}
    mapping = {}
    with open(roster_path, newline="") as f:
        for row in csv.DictReader(f):
            mapping[row["name"].strip()] = row["student_id"].strip()
    return mapping


def build():
    students_dir = config.STUDENTS_DIR
    if not students_dir.exists():
        raise SystemExit(f"No students directory found at {students_dir}")

    student_folders = sorted(p for p in students_dir.iterdir() if p.is_dir())
    if not student_folders:
        raise SystemExit(
            f"No student folders found in {students_dir}.\n"
            f"Create one folder per student, e.g. {students_dir}/Jane Doe/photo1.jpg"
        )

    roster_ids = load_roster_ids(students_dir)
    detector = FaceDetector()

    db = {}
    total_photos = 0
    total_faces = 0

    for i, folder in enumerate(student_folders):
        name = folder.name
        student_id = roster_ids.get(name, f"S{i+1:03d}")

        images = [p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXTS]
        if not images:
            print(f"  WARNING: no photos found for {name}, skipping")
            continue

        embeddings = []
        for img_path in tqdm(images, desc=f"{name}"):
            total_photos += 1
            img = cv2.imread(str(img_path))
            if img is None:
                print(f"  WARNING: could not read {img_path}")
                continue
            faces = detector.detect(img)
            if not faces:
                print(f"  WARNING: no face detected in {img_path.name}")
                continue
            if len(faces) > 1:
                print(f"  WARNING: {img_path.name} has {len(faces)} faces, using the largest")
                faces.sort(key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]), reverse=True)
            embeddings.append(faces[0].embedding)
            total_faces += 1

        if not embeddings:
            print(f"  WARNING: 0 usable embeddings for {name}, skipping enrollment")
            continue

        db[student_id] = {"name": name, "embeddings": np.stack(embeddings)}
        print(f"  {name} ({student_id}): {len(embeddings)}/{len(images)} photos usable")

    config.EMBEDDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(config.EMBEDDINGS_PATH, "wb") as f:
        pickle.dump(db, f)

    print(f"\nEnrolled {len(db)} students from {total_photos} photos ({total_faces} usable faces).")
    print(f"Saved to {config.EMBEDDINGS_PATH}")


if __name__ == "__main__":
    build()
