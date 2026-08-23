"""
Google Sheets "mastersheet" sync.

After the face-recognition pipeline produces an attendance report for a
classroom video, this module writes it into a shared Google Sheet.

Layout (one tab; a blank tab is auto-initialised):

    col A  : "Name"                       one row per enrolled student
                                            (from the embeddings roster).
    col B..: one new column per session   headed "<YYYY-MM-DD> <class name>".

Attendance marks per student (edit ``ATTENDANCE_MARK`` to change them):

    PRESENT              -> "P"    auto-present
    PRESENT_REVIEW       -> "A?"   likely present, please confirm manually
    NEEDS_REVIEW         -> "A?"   weak / ambiguous evidence -> confirm
    NOT_OBSERVED         -> "A"    no reliable evidence -> treated as absent

Rules:
    * If the same "<date> <class>" header already exists, that column is
      overwritten (e.g. re-uploading the same class on the same day).
    * A roster student missing from column A is appended so the mastersheet
      tracks the data/students folder.
    * Name matching is case-insensitive on the full name.

Authentication
---------------
Set creds either in src/config.py or via env vars:
    ATTENDANCE_SHEET_ID         the master spreadsheet id (URL long id)
    ATTENDANCE_CREDENTIALS_FILE path to the service-account JSON key
Share the spreadsheet to the service account's email (see secrets/README).
"""

import os
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from src import config

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

ATTENDANCE_STATUS = {
    "PRESENT": "P",
    "PRESENT_REVIEW": "A?",
    "NEEDS_REVIEW": "A?",
    "NOT_OBSERVED": "A",
}

_service = None


def _credentials():
    from google.oauth2 import service_account

    cred_file = Path(config.SERVICE_ACCOUNT_FILE)
    if not cred_file.exists():
        raise FileNotFoundError(
            "Google service-account key not found at: %s\n"
            "Create one via secrets/README.md, then set ATTENDANCE_CREDENTIALS_FILE." % cred_file
        )
    return service_account.Credentials.from_service_account_file(
        str(cred_file), scopes=SCOPES
    )


def get_service():
    """Lazily build a single Google Sheets API client (reused across writes)."""
    global _service
    if _service is None:
        from googleapiclient.discovery import build

        _service = build("sheets", "v4", credentials=_credentials())
    return _service


def _spreadsheet_id() -> str:
    if not config.SPREADSHEET_ID:
        raise RuntimeError(
            "Google Spreadsheet ID is not configured. Set ATTENDANCE_SHEET_ID."
        )
    return config.SPREADSHEET_ID


def _tab_title(service, spreadsheet_id: str) -> str:
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return meta["sheets"][0]["properties"]["title"]


def _read_grid(service, spreadsheet_id: str, tab: str) -> List[List[str]]:
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"{tab}!A1:ZZ2000")
        .execute()
    )
    values = result.get("values", []) or []
    return [[str(c or "") for c in row] for row in values]


def _col_letter(idx: int) -> str:
    """1-based column index -> spreadsheet letters (28 -> 'AB')."""
    s = ""
    while idx:
        idx, rem = divmod(idx - 1, 26)
        s = chr(65 + rem) + s
    return s


def _batch_write(service, spreadsheet_id: str, updates: list) -> None:
    body = {"valueInputOption": "USER_ENTERED", "data": updates}
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheet_id, body=body
    ).execute()


def _find_session_column(headers: List[str], header: str, min_col: int) -> int:
    """0-based column index for ``header``.

    Existing header match wins; else first empty header at/after ``min_col``;
    else append after the last column.
    """
    existing = None
    first_empty = None
    width = max(len(headers), min_col + 1)
    for i in range(min_col, width):
        h = headers[i].strip() if i < len(headers) else ""
        if existing is None and h == header:
            existing = i
        if first_empty is None and not h:
            first_empty = i
    if existing is not None:
        return existing
    if first_empty is not None:
        return first_empty
    return width


def write_attendance(
    decisions: Sequence,
    class_name: str,
    date_str: Optional[str] = None,
    spreadsheet_id: Optional[str] = None,
) -> Dict:
    """Write a pipeline decision list into the master sheet as a new column.

    Args:
        decisions: iterable of objects with ``.student_name`` and ``.status``
            attributes (e.g. the pipeline's AttendanceDecision records).
        class_name: heading word for the session, e.g. "5A" or "Physics".
        date_str: ISO date for the column header (defaults to today).
        spreadsheet_id: optional override of the configured spreadsheet.

    Returns a summary dict like
        {"spreadsheet_id", "tab", "column", "headers": <new header>, "written": n}
    """
    spreadsheet_id = spreadsheet_id or _spreadsheet_id()
    service = get_service()
    tab = _tab_title(service, spreadsheet_id)

    header = f"{date_str or date.today().isoformat()} {class_name}".strip()
    grid = _read_grid(service, spreadsheet_id, tab)
    is_empty = not grid or all(not (c or "").strip() for row in grid for c in row)

    headers = grid[0] if grid else []
    col_idx = _find_session_column([h or "" for h in headers], header, min_col=1)

    # ---- name -> 1-based spreadsheet row from column A (-ish) ----
    row_of: Dict[str, int] = {}
    if not is_empty:
        for r, row in enumerate(grid, start=1):
            if row and (row[0] or "").strip():
                row_of[row[0].strip().lower()] = r

    # ---- append any roster student missing from column A ----
    # On an empty tab row 1 is reserved for the "Student Name" header, so
    # data rows begin at 2; otherwise continue after the existing rows.
    next_row = 2 if (is_empty and not grid) else len(grid) + 1
    appended = []
    for d in decisions:
        key = d.student_name.strip().lower()
        if key not in row_of:
            row_of[key] = next_row
            appended.append((next_row, d.student_name.strip()))
            next_row += 1

    # ---- build the batch of cell updates ----
    updates = []

    a1_missing = not grid or not grid[0] or not (grid[0][0] or "").strip()
    if a1_missing:
        updates.append({"range": f"{tab}!A1", "values": [["Student Name"]]})

    if appended:
        updates.append(
            {
                "range": f"{tab}!A{appended[0][0]}:A{appended[-1][0]}",
                "values": [[name] for _, name in appended],
            }
        )

    last_row = max(row_of.values()) if row_of else 1
    col_values: List[List[str]] = [[""] for _ in range(last_row)]
    col_values[0] = [header]
    for d in decisions:
        r = row_of.get(d.student_name.strip().lower())
        if r is None:
            continue
        mark = ATTENDANCE_STATUS.get(d.status, str(d.status))
        col_values[r - 1][0] = mark

    c_letter = _col_letter(col_idx + 1)
    updates.append(
        {
            "range": f"{tab}!{c_letter}1:{c_letter}{last_row}",
            "values": col_values,
        }
    )

    _batch_write(service, spreadsheet_id, updates)
    return {
        "spreadsheet_id": spreadsheet_id,
        "tab": tab,
        "column": c_letter,
        "header": header,
        "written": len(decisions),
    }