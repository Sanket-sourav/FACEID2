Google Sheets setup
===================

The backend writes attendance into a **master Google Sheet** using a Google
*service account*. Nothing is ever saved unless you complete the steps below.

1. Create a Google Sheet (the mastersheet)
------------------------------------------
   - Go to https://sheets.new → it creates a blank spreadsheet
   - Rename it, e.g. `Class Attendance Master`
   - The spreadsheet ID is the long code in the URL, e.g.
     `https://docs.google.com/spreadsheets/d/1AbC...xyz/edit`
     → the ID is `1AbC...xyz`

2. Create a service account + download the JSON key
---------------------------------------------------
   - Open https://console.cloud.google.com/ (create a project if needed)
   - APIs & Services → Library → enable **Google Sheets API**
     (https://console.cloud.google.com/apis/library/sheets.googleapis.com)
   - APIs & Services → Credentials → Create credentials → **Service account**
   - Under *Keys* → *Add key* → **JSON** → download the file
   - Save the downloaded file in this folder as:
     ```
     secrets/service-account.json
     ```
     (This exact name is the default the app looks for.)

3. Grant the service account access to your mastersheet
-------------------------------------------------------
   - Open your mastersheet → click **Share** (top right)
   - Paste the service account email, which looks like
     `something@project-id.iam.gserviceaccount.com`
   - Role: **Editor** → Send / Share

4. Tell the app which spreadsheet to write to
----------------------------------------------
   Two options (either works; use env vars so no secret lives in code):

   **Option A — environment variables (recommended):**
   ```
   set ATTENDANCE_SHEET_ID=1AbC...xyz
   set ATTENDANCE_CREDENTIALS_FILE=secrets/service-account.json
   ```

   **Option B — edit `src/config.py`:** set `SPREADSHEET_ID` to the ID and
   `SERVICE_ACCOUNT_FILE` to the key path (default is already the path above).

What the sheet looks like after a run
-------------------------------------
   | Name         | 2026-08-23 5A | 2026-08-24 5A | ...
   |--------------|---------------|---------------|
   | Rahul Kumar  | P             | A             |
   | Priya Das    | P?            | P             |
   | Ananya Singh | A             | A             |

   Marks (edit in `src/sheets/sync.py` → `ATTENDANCE_STATUS`):
     `P`   auto-present
     `P?`  PRESENT_REVIEW   — seems present, double-check
     `A?`  NEEDS_REVIEW     — weak evidence, confirm manually
     `A`   NOT_OBSERVED     — not seen in the video (treated absent)

Notes
-----
- A new column is added **per upload** with header `<date> <class-name>`
  (class name comes from the phone form). Re-uploading the same class on the
  same day overwrites that column instead of duplicating it.
- Students are matched to rows case-insensitively by name; anyone in the
  roster (data/students) who is missing from column A is appended at the end.