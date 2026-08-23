# Classroom Attendance Recognition

Face-recognition attendance pipeline. A teacher records a classroom video with
their **phone**, uploads it to the web server, and the pipeline **marks
attendance in a Google Sheet mastersheet** — one new column per date + class.

Two modes:
- `python main.py process-video --video ...` — CLI prototype (video in → report out)
- `python main.py serve` — phone-friendly web UI (video in → Google Sheet out)

## Setup

```bash
bash scripts/setup_venv.sh
source venv/bin/activate
pip install -r requirements.txt
```

First run of the detector downloads InsightFace's `buffalo_l` model pack
(~326MB) to `~/.insightface/models/`. It's cached after that.

## 0. Protect it with a teacher login (recommended before exposing it)

The server ships with **no login by default** so it "just works" on your local
LAN. The moment you deploy it publicly (Railway), anyone with the URL could
record a video and write attendance. To require a teacher to log in before
they can use it, set these env vars to anything you like:

```bash
set ATTENDANCE_TEACHER_USERNAME=yourname
set ATTENDANCE_TEACHER_PASSWORD=a-strong-password
```

- When both are set, the phone page shows a **login form** instead of the
  upload form. Only a logged-in teacher can upload / change attendance.
- You can also set `ATTENDANCE_ACCESS_TOKEN` to a fixed "master" bearer token
  (also accepted via `Authorization: Bearer <token>`) — handy for scripts.
- If neither is set, the app is open (fine for local testing only).

## 1. Enroll students

Create one folder per student under `data/students/`, each containing 3-10
photos of that person (front-facing, some angle/lighting variation ideally):

```
data/students/
    Rahul Kumar/
        photo1.jpg
        photo2.jpg
    Priya Das/
        photo1.jpg
```

Optional: add `data/students/roster.csv` with columns `student_id,name` to
control student IDs; otherwise IDs are auto-assigned (S001, S002, ...).

### Don't have real student photos yet? Test with your own webcam

```bash
python -m src.tools.capture_enrollment_photos --name "Your Name" --count 8
```

Opens a webcam preview window. Press SPACE to capture a photo (move your
head slightly between shots), ESC/q when done. Repeat with a different
`--name` for each person you want in your test roster (you + a couple of
friends/family works fine to prove the pipeline distinguishes people).

Then build the embeddings database:

```bash
python main.py build-embeddings
```

This detects a face in every enrollment photo and stores its embedding in
`data/embeddings/embeddings.pkl`. It'll warn you about any photo where no
face (or multiple faces) was found.

## 2. Get a video to test on

Point `--video` at any classroom video once you have one. Until then:

```bash
python -m src.tools.record_test_video --seconds 15 --out data/videos/test.mp4
```

Opens a webcam preview and records straight to `data/videos/test.mp4`. Move
around a bit during recording (closer/farther, slight angle changes) so the
pipeline has more than one identical frame to work with.

## 3. Run the pipeline

```bash
python main.py process-video --video data/videos/test.mp4
```

Prints something like:

```
============================================================
ATTENDANCE RESULT
============================================================
✓ Rahul Kumar               PRESENT           96%   (14 consistent high-quality observations, avg similarity 0.71.)
⚠ Priya Das                 PRESENT_REVIEW    58%   (Only 3 observations or borderline similarity (0.55) — verify before finalizing.)
✗ Ananya Singh               NOT_OBSERVED       --   (No face observations matched this student above the match threshold.)
============================================================
3 enrolled | 1 auto-present | 2 need review
```

Add `--save-json` to also write the full report to `data/reports/`.

## 4. Use it from your phone → Google Sheet

Set up Google access first (one-time): open **`secrets/README.md`** and follow
the four steps (create mastersheet → service account key → share sheet → set
config/env vars). Then start the server from the computer that has the model
and the enrollment embeddings:

```bash
python main.py serve
# or: uvicorn app:app --host 0.0.0.0 --port 8000
```

The console prints addresses. Make sure the **phone and computer are on the
same Wi-Fi**, then on the phone open:

```
http://<computer's-LAN-IP>:8000
```

(Find the IP on the computer with
`python -c "import socket; print(socket.gethostbyname(socket.gethostname()))"`.)

From the phone page:
1. Type the class name, e.g. `5A` (this becomes part of the new sheet column).
2. Tap the video field → the phone's camera opens → record the classroom — pan
   slowly across the students, hold briefly on each face.
3. Upload. The page polls until processing finishes and shows the result with
   how it was written into the spreadsheet.

Each class session becomes a **new column** in the mastersheet:

```
| Name         | 2026-08-23 5A | 2026-08-24 5A |
|--------------|---------------|---------------|
| Rahul Kumar  | P             | A             |
| Priya Das    | P?            | P             |
| Ananya Singh | A             | P             |
```

Marks: `P` = present, `P?` = need to check (likely present), `A?` = weak
evidence / confirm, `A` = not observed (treated absent). Re-uploading the same
class on the same date overwrites that column.

> **Tip for phones recording in MOV:** OpenCV usually reads it fine. If the
> job errors with "Could not open video", re-encode it once (e.g. convert to
> MP4 in any converter app) and re-upload.

## 5. Deploy publicly (Railway, etc.)

The server is *LAN-only by default* simply because it runs on your own
computer, which isn't reachable from the internet. Deploying it to a cloud
host like Railway gives it a **public HTTPS URL**, so a phone anywhere with
internet can open it. No code change is needed for binding — Railway's
`PORT` env var is picked up automatically by `serve`.

Set these environment variables in Railway:

```
PORT                            (Railway sets this automatically)
ATTENDANCE_TEACHER_USERNAME     the teacher's login username
ATTENDANCE_TEACHER_PASSWORD     a strong password (this is what protects the app)
ATTENDANCE_SHEET_ID             e.g. 1AbC...xyz
ATTENDANCE_ACCESS_TOKEN         optional extra "master" token for scripts / fallback
ATTENDANCE_CREDENTIALS_JSON     paste the full service-account JSON (simplest option on Railway)
ATTENDANCE_CREDENTIALS_FILE     or a local path to the key file, if you write it to disk at startup
```

Service-account key + models on Railway:

- Your service-account JSON is a local, gitignored file. On Railway, store the
  JSON contents in a secret/env var and write them to `secrets/service-
  account.json` at startup (a small `startup` script).
- The InsightFace model (~326MB) and your `data/embeddings/embeddings.pkl`
  are also local, gitignored files, and Railway's disk is ephemeral. For a
  real deployment you must either: (1) ship `data/students/` enrollment
  photos and rebuild embeddings at startup, or (2) keep `embeddings.pkl`
  somewhere durable and fetch it at startup.

Because this exposes attendance to whoever holds the URL, **always set
`ATTENDANCE_TEACHER_USERNAME` and `ATTENDANCE_TEACHER_PASSWORD`** when
deploying publicly. The web page then shows a **login form**; only the logged-in
teacher can upload or change attendance. (You can set `ATTENDANCE_ACCESS_TOKEN`
too, as a master token for scripts.) `/health` stays public so the page can
tell users a login is required; the roster/upload/job routes all require it.

## Tuning

All thresholds live in `src/config.py` (`MATCH_THRESHOLD`,
`MARGIN_THRESHOLD`, `HIGH_CONFIDENCE_MIN_OBSERVATIONS`, etc.). The defaults
are reasonable starting points but **must** be recalibrated against real
classroom footage — that's Phase 6/27 in the master plan: collect several
real videos with known ground truth, run the pipeline, and adjust thresholds
based on false-present / false-absent / review-rate, not vibes.

## What's not built yet

- Face tracking across frames (currently each frame's detections are
  independent observations, aggregated by best-match identity only — still
  Phase 4 in the master plan)
- PostgreSQL / durable job queue (jobs live in memory until the server stops)
- Human review UI (review-flagged students surface as `P?` / `A?` in the sheet
  and in the results table; there's no click-to-confirm screen yet)
- Authentication on the web server (usable only on your LAN by default)

## Project layout

```
attendance-app/
    main.py                          CLI entrypoint (+ `serve` subcommand)
    app.py                           FastAPI backend: phone upload -> jobs -> Google Sheets
    web/index.html                   mobile web UI (record + upload + results)
    src/
        config.py                    all tunable thresholds + sheets config
        pipeline.py                  ties detector -> quality -> recognizer -> decision engine together
        services/
            video_processor.py       frame sampling from a video file
            face_detector.py         InsightFace wrapper (detection + embedding)
            face_quality.py          blur/size/pose scoring
            face_recognizer.py       cosine-similarity matching against enrolled roster
            decision_engine.py       multi-observation aggregation -> PRESENT/REVIEW/NOT_OBSERVED
        enrollment/
            build_embeddings.py      builds embeddings.pkl from data/students/
        sheets/
            sync.py                  writes a new "<date> <class>" column into the Google Sheet
        tools/
            capture_enrollment_photos.py   webcam photo capture (for testing without real data)
            record_test_video.py           webcam video capture (for testing without real data)
    secrets/
        README.md                    one-time Google Sheets + service-account setup guide
        (service-account.json        your downloaded Google API key - gitignored)
    data/
        students/                    enrollment photos (gitignored)
        embeddings/embeddings.pkl    built embeddings database (gitignored)
        videos/                      test/classroom videos + uploads/ (gitignored)
        reports/                     JSON output reports (gitignored)
```
