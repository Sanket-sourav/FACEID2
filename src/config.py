"""
Central configuration and tunable thresholds for the attendance pipeline.

These defaults are reasonable starting points for InsightFace's buffalo_l
pack (cosine similarity between L2-normalized ArcFace embeddings), but they
MUST be recalibrated once you have real classroom footage (see Phase 6 /
Phase 27 in the master plan: run the benchmark script and adjust based on
false-present / false-absent / review-rate numbers for your actual room,
lighting, and camera).
"""

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

# Load optional .env file (simplest way to set ATTENDANCE_* variables on your
# own machine). If python-dotenv isn't installed or there's no .env file, this
# is a no-op and env vars / config edits still work normally.
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT_DIR / ".env")
except Exception:
    pass

STUDENTS_DIR = ROOT_DIR / "data" / "students"
EMBEDDINGS_PATH = ROOT_DIR / "data" / "embeddings" / "embeddings.pkl"
VIDEOS_DIR = ROOT_DIR / "data" / "videos"
REPORTS_DIR = ROOT_DIR / "data" / "reports"
UPLOADS_DIR = ROOT_DIR / "data" / "videos" / "uploads"

# ---------------------------------------------------------------------------
# Google Sheets master-sheet sync
# ---------------------------------------------------------------------------
# Path to the Google service-account JSON key used to authenticate as the API
# caller. Override with the ATTENDANCE_CREDENTIALS_FILE env var.
SERVICE_ACCOUNT_FILE = os.environ.get(
    "ATTENDANCE_CREDENTIALS_FILE",
    str(ROOT_DIR / "secrets" / "service-account.json"),
)
# Spreadsheet ID of the master attendance sheet (the long id in its URL).
# Override with the ATTENDANCE_SHEET_ID env var (and/or leave blank here).
SPREADSHEET_ID = os.environ.get("ATTENDANCE_SHEET_ID", "")

# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------
# Teacher login credentials. Set these (or via env vars) to require a teacher
# to log in before they can record/upload attendance. Use a strong password.
TEACHER_USERNAME = os.environ.get("ATTENDANCE_TEACHER_USERNAME", "")
TEACHER_PASSWORD = os.environ.get("ATTENDANCE_TEACHER_PASSWORD", "")

# Optional fixed "master" bearer token, also accepted (sent as
# "Authorization: Bearer <token>"). Convenient for programmatic access or as a
# fallback if teacher login isn't configured. Both are optional, but if EITHER
# is set then authentication is required for all sensitive routes.
ACCESS_TOKEN = os.environ.get("ATTENDANCE_ACCESS_TOKEN", "")

# Valuable on PaaS (Railway etc.) where the service-account key is easier to
# provide as a secret string than as a file: if ATTENDANCE_CREDENTIALS_JSON is
# set, write it to SERVICE_ACCOUNT_FILE automatically on import.
_CREDENTIALS_JSON = os.environ.get("ATTENDANCE_CREDENTIALS_JSON", "")
if _CREDENTIALS_JSON:
    _cred_path = Path(SERVICE_ACCOUNT_FILE)
    _cred_path.parent.mkdir(parents=True, exist_ok=True)
    _cred_path.write_text(_CREDENTIALS_JSON)

# ---------------------------------------------------------------------------
# Face detection / InsightFace model pack
# ---------------------------------------------------------------------------
MODEL_PACK = "buffalo_l"          # also try "antelopev2" and compare (Phase 27)
DETECTOR_SIZE = (640, 640)        # SCRFD input size; larger = slower but catches smaller/farther faces
MIN_DETECTION_CONFIDENCE = 0.4    # lower than InsightFace's 0.5 default: tightly-cropped enrollment
                                   # photos (face fills most of the frame, little margin) can score
                                   # lower even when clearly a real face -- see README photo guidance

# ---------------------------------------------------------------------------
# Video frame sampling
# ---------------------------------------------------------------------------
SAMPLE_EVERY_N_FRAMES = 3         # naive fallback sampling rate
MAX_FRAMES_TO_PROCESS = 120       # hard cap so a long video doesn't run forever
SCENE_DIFF_THRESHOLD = 12.0       # mean abs pixel diff (0-255) to count a frame as "new" content

# ---------------------------------------------------------------------------
# Face quality filtering
# ---------------------------------------------------------------------------
MIN_FACE_SIZE_PX = 40             # reject faces smaller than this (width or height, px)
MIN_BLUR_SCORE = 60.0             # variance-of-Laplacian; lower = blurrier, reject below this
MIN_QUALITY_OVERALL = 0.5         # combined 0-1 quality score threshold to use a face at all

# ---------------------------------------------------------------------------
# Recognition matching thresholds
# ---------------------------------------------------------------------------
# Cosine similarity between a live face embedding and an enrolled embedding.
# For buffalo_l on normalized embeddings, genuine pairs commonly land >0.5,
# impostors <0.3, but this varies a lot by dataset -- calibrate with real data.
MATCH_THRESHOLD = 0.42            # minimum similarity to count as *any* candidate match
MARGIN_THRESHOLD = 0.15           # min gap between best and second-best candidate

# ---------------------------------------------------------------------------
# Temporal / multi-observation aggregation (decision engine)
# ---------------------------------------------------------------------------
HIGH_CONFIDENCE_MIN_OBSERVATIONS = 5   # good-quality observations needed for auto PRESENT
MEDIUM_CONFIDENCE_MIN_OBSERVATIONS = 2 # fewer than this -> always review
MIN_CONSISTENCY_RATIO = 0.75           # fraction of a student's observations that must agree, for auto PRESENT
MEDIUM_MIN_CONSISTENCY_RATIO = 0.5     # below this, even "present-ish" evidence is too ambiguous -> NEEDS_REVIEW
HIGH_CONFIDENCE_MIN_AVG_SIMILARITY = 0.50
MEDIUM_CONFIDENCE_MIN_AVG_SIMILARITY = 0.42
