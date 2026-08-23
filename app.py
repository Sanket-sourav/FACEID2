"""
Phone-friendly classroom attendance backend.

A teacher opens this server's page on their phone, records a classroom video
with the phone camera, uploads it here; the existing face-recognition pipeline
processes the video in the background and writes the attendance report into the
configured Google Sheets master spreadsheet as a new "<date> <class name>" column.

Run it with:

    python main.py serve

or directly with:

    uvicorn app:app --host 0.0.0.0 --port 8000
"""

import secrets
import threading
import time
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse

from src import config
from src.services.face_detector import FaceDetector
from src.services.face_recognizer import FaceRecognizer

WEB_DIR = Path(__file__).resolve().parent / "web"

app = FastAPI(title="Classroom Attendance API", version="2.0.0")

# ---------------------------------------------------------------------------
# Heavy components are loaded once per process and reused across uploads. The
# pipeline access is serialised with a lock because InsightFace apps are not
# thread-safe and a classroom workload has at most one active video anyway.
# ---------------------------------------------------------------------------
_detector = None
_recognizer = None
_pipeline_lock = threading.Lock()


def get_detector():
    global _detector
    if _detector is None:
        _detector = FaceDetector()
    return _detector


def get_recognizer():
    global _recognizer
    if _recognizer is None:
        _recognizer = FaceRecognizer()
    return _recognizer


def roster_names():
    return get_recognizer().roster()


# ---------------------------------------------------------------------------
# Authentication.
#
# Login sessions: the teacher POSTs a username/password to /api/login, which
# issues a short-lived bearer token stored in memory. Every sensitive route is
# protected by require_auth. A fixed master token (config.ACCESS_TOKEN) is also
# accepted for programmatic access. If NONE of these are configured, the app is
# open (local LAN use stays untouched).
# ---------------------------------------------------------------------------
SESSION_TTL_SEC = 12 * 3600  # a teacher session lasts 12h
SESSION_TOKENS = {}          # token -> expiry (unix seconds)
SESSION_LOCK = threading.Lock()


def _auth_required() -> bool:
    return bool(
        config.ACCESS_TOKEN
        or (config.TEACHER_USERNAME and config.TEACHER_PASSWORD)
    )


def _validate_session(token: str) -> bool:
    now = time.time()
    with SESSION_LOCK:
        exp = SESSION_TOKENS.get(token)
        if exp is None:
            return False
        if exp < now:
            SESSION_TOKENS.pop(token, None)
            return False
        return True


def _register_session() -> str:
    token = secrets.token_urlsafe(32)
    with SESSION_LOCK:
        SESSION_TOKENS[token] = time.time() + SESSION_TTL_SEC
    return token


def _revoke_session(token: str) -> None:
    with SESSION_LOCK:
        SESSION_TOKENS.pop(token, None)


def require_auth(authorization: str = Header(None)):
    if not _auth_required():
        return True
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Login required.")
    token = authorization[len("Bearer "):].strip()
    if _validate_session(token):
        return True
    if config.ACCESS_TOKEN and secrets.compare_digest(token, config.ACCESS_TOKEN):
        return True
    raise HTTPException(status_code=401, detail="Invalid or expired session, please log in again.")


def extract_token(authorization: str) -> str:
    if authorization and authorization.startswith("Bearer "):
        return authorization[len("Bearer "):].strip()
    return ""


@app.post("/api/logout")
def logout(_auth=Depends(require_auth), authorization: str = Header(None)):
    _revoke_session(extract_token(authorization))
    return {"ok": True}


# ---------------------------------------------------------------------------
# In-memory job store
# ---------------------------------------------------------------------------
JOBS = {}
JOBS_LOCK = threading.Lock()


def _commit(job_id: str, **fields):
    with JOBS_LOCK:
        JOBS[job_id].update(**fields, updated_at=time.time())


def _job_snapshot(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        return dict(job) if job else None


def _run_job(job_id: str, video_path: str, class_name: str):
    _commit(job_id, status="processing")
    sheet_result = None
    sheet_error = None
    decisions = None
    stats = None
    error = None
    try:
        from src.pipeline import process_video

        with _pipeline_lock:
            # verbose=False keeps the server log clean; progress is reported
            # via the job object instead.
            decisions, stats = process_video(
                video_path,
                verbose=False,
                detector=get_detector(),
                recognizer=get_recognizer(),
            )

        try:
            from src.sheets.sync import write_attendance

            sheet_result = write_attendance(decisions, class_name=class_name)
        except Exception as exc:  # keep the recognition result, flag the sync
            sheet_error = f"{type(exc).__name__}: {exc}"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        _commit(
            job_id,
            status="error" if error else "done",
            error=error,
            stats=stats,
            decisions=decisions,
            sheet=sheet_result,
            sheet_error=sheet_error,
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/")
def index(_auth=Depends(require_auth)):
    return FileResponse(WEB_DIR / "index.html")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "embeddings_built": config.EMBEDDINGS_PATH.exists(),
        "sheets_configured": bool(config.SPREADSHEET_ID),
        "service_account_configured": Path(config.SERVICE_ACCOUNT_FILE).exists(),
        "auth_required": _auth_required(),
        "login_configured": bool(config.TEACHER_USERNAME and config.TEACHER_PASSWORD),
    }


@app.post("/api/login")
def login(username: str = Form(""), password: str = Form("")):
    if not (config.TEACHER_USERNAME and config.TEACHER_PASSWORD):
        raise HTTPException(
            status_code=403,
            detail="Teacher login is not configured on this server.",
        )
    if username == config.TEACHER_USERNAME and secrets.compare_digest(
        password, config.TEACHER_PASSWORD
    ):
        return {"token": _register_session(), "username": username}
    raise HTTPException(status_code=401, detail="Invalid username or password.")


@app.get("/api/roster")
def roster(_auth=Depends(require_auth)):
    if not config.EMBEDDINGS_PATH.exists():
        raise HTTPException(
            status_code=400,
            detail="No embeddings database found. Run 'python main.py build-embeddings' first.",
        )
    return {"names": roster_names()}


@app.post("/api/upload")
async def upload(video: UploadFile, class_name: str = Form(""), _auth=Depends(require_auth)):
    if not config.EMBEDDINGS_PATH.exists():
        raise HTTPException(
            status_code=400,
            detail="No embeddings database found. Run 'python main.py build-embeddings' first.",
        )
    class_name = (class_name or "").strip()
    if not class_name:
        raise HTTPException(status_code=400, detail="class_name is required (e.g. '5A').")

    original_name = Path(video.filename or "upload.mp4").name
    if Path(original_name).suffix.lower() not in {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {original_name}. Expected a video (mp4/mov/avi/mkv/webm/m4v).",
        )

    job_id = uuid.uuid4().hex[:12]
    dest_dir = config.UPLOADS_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{job_id}_{original_name}"

    size = 0
    with open(dest, "wb") as out:
        while chunk := await video.read(1024 * 1024):
            out.write(chunk)
            size += len(chunk)

    if size == 0:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    with JOBS_LOCK:
        JOBS[job_id] = {
            "id": job_id,
            "status": "queued",
            "class_name": class_name,
            "video_name": original_name,
            "video_path": str(dest),
            "size_mb": round(size / (1024 * 1024), 2),
            "stats": None,
            "decisions": None,
            "sheet": None,
            "sheet_error": None,
            "error": None,
            "created_at": time.time(),
            "updated_at": time.time(),
        }

    threading.Thread(
        target=_run_job,
        args=(job_id, str(dest), class_name),
        daemon=True,
        name=f"attendance-job-{job_id}",
    ).start()

    return {"job_id": job_id, "status": "queued"}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str, _auth=Depends(require_auth)):
    job = _job_snapshot(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    # Do not leak filesystem paths to the phone UI.
    job.pop("video_path", None)
    return job