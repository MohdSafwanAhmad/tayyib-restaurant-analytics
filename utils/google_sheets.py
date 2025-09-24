# utils/google_sheets.py
import json
from datetime import datetime
from typing import Optional, Tuple

import gspread
from google.oauth2.service_account import Credentials
import streamlit as st

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SPREADSHEET_NAME = st.secrets.get("GOOGLE_SHEETS_NAME", "Restaurant_Offers_Pending")
SPREADSHEET_ID = st.secrets.get("GOOGLE_SHEETS_ID", "")  # optional but best
WORKSHEET_TITLE = st.secrets.get("GOOGLE_SHEETS_TAB", "Pending")  # or "Sheet1"

HEADERS = [
    "timestamp", "restaurant_id", "restaurant_name", "offer_type",
    "title", "description", "summary", "valid_days_of_week",
    "valid_start_time", "valid_end_time", "start_date", "end_date",
    "unique_usage_per_user", "surprise_bag_data", "status"
]

def _first_row(ws):
    try:
        return ws.row_values(1)
    except Exception:
        return []

def _ensure_headers(ws):
    """Guarantee row 1 exactly matches HEADERS (no blanks/duplicates)."""
    current = _first_row(ws)
    # If missing, different length, or any blank/duplicate -> rewrite
    needs_fix = (
        not current
        or len(current) != len(HEADERS)
        or any(c is None or str(c).strip() == "" for c in current)
        or len(set(map(str, current))) != len(current)
    )
    if needs_fix or current != HEADERS:
        # clear first row cells and write headers in one call
        rng = gspread.utils.rowcol_to_a1(1, 1) + ":" + gspread.utils.rowcol_to_a1(1, len(HEADERS))
        ws.batch_clear([rng])
        ws.update([HEADERS], value_input_option="RAW")

def _normalize_private_key(info: dict) -> dict:
    pk = info.get("private_key", "")
    # If it contains literal backslash-n, turn into real newlines
    if "\\n" in pk and "\n" not in pk:
        info = {**info, "private_key": pk.replace("\\n", "\n")}
    return info

def get_google_sheets_client() -> Optional[gspread.Client]:
    try:
        if "google_service_account" in st.secrets:
            info = _normalize_private_key(dict(st.secrets["google_service_account"]))
            creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        else:
            # local fallback
            import json as _json
            with open("service-account.json", "r") as f:
                info = _normalize_private_key(_json.load(f))
            creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(
            "Failed to initialize Google Sheets client. "
            "Make sure your service account JSON is correct and the spreadsheet "
            "is shared with the service account email."
        )
        with st.expander("Details"):
            st.code(f"{type(e).__name__}: {e}")
        return None

def _open_or_create_spreadsheet(gc: gspread.Client) -> gspread.Spreadsheet:
    # Prefer ID if provided
    if SPREADSHEET_ID:
        return gc.open_by_key(SPREADSHEET_ID)
    # Otherwise try by name, create if missing
    try:
        return gc.open(SPREADSHEET_NAME)
    except gspread.SpreadsheetNotFound:
        ss = gc.create(SPREADSHEET_NAME)
        # You must share the sheet with your service account email to see it in Drive UI
        return ss

def _get_worksheet(ss: gspread.Spreadsheet) -> gspread.Worksheet:
    try:
        ws = ss.worksheet(WORKSHEET_TITLE)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=WORKSHEET_TITLE, rows=1, cols=len(HEADERS))
    _ensure_headers(ws)
    return ws


def _get_ws() -> Optional[gspread.Worksheet]:
    gc = get_google_sheets_client()
    if not gc:
        return None
    try:
        ss = _open_or_create_spreadsheet(gc)
        return _get_worksheet(ss)
    except gspread.exceptions.APIError as e:
        st.error(
            "Google Sheets API error. Verify the spreadsheet exists **and** is "
            "shared with your service account email."
        )
        with st.expander("Details"):
            st.code(f"{type(e).__name__}: {e}")
        return None

def add_offer_to_sheet(restaurant_id, restaurant_name, offer_data) -> bool:
    """Append one pending offer as a new row."""
    ws = _get_ws()
    if not ws:
        return False

    row = [
        datetime.utcnow().isoformat(),            # timestamp (UTC)
        str(restaurant_id),
        restaurant_name,
        offer_data["offer_type"],
        offer_data["about"]["en"]["title"],
        offer_data["about"]["en"].get("description", ""),
        offer_data["about"]["en"].get("summary", ""),
        json.dumps(offer_data.get("valid_days_of_week") or []),
        (str(offer_data.get("valid_start_time")) or ""),
        (str(offer_data.get("valid_end_time")) or ""),
        str(offer_data.get("start_date") or ""),
        str(offer_data.get("end_date") or ""),
        "TRUE" if offer_data.get("unique_usage_per_user") else "FALSE",
        json.dumps(offer_data.get("surprise_bag") or {}),
        "pending",
    ]

    try:
        ws.append_row(row, value_input_option="USER_ENTERED")
        return True
    except Exception as e:
        # retry once (transient errors happen)
        try:
            ws.append_row(row, value_input_option="USER_ENTERED")
            return True
        except Exception as e2:
            st.error("Failed to add offer to Google Sheets.")
            with st.expander("Details"):
                st.code(f"{type(e2).__name__}: {e2}")
            return False

def get_pending_offers_from_sheet(restaurant_id):
    """Return normalized dicts for this restaurant's pending rows."""
    ws = _get_ws()
    if not ws:
        return []
    values = ws.get_all_records(expected_headers=HEADERS)  # list[dict] using first row as headers

    out = []
    for r in values:
        if str(r.get("restaurant_id")) != str(restaurant_id):
            continue
        if str(r.get("status", "")).lower() != "pending":
            continue

        try:
            pending = {
                "timestamp": r.get("timestamp", ""),
                "offer_type": r.get("offer_type", ""),
                "about": {
                    "en": {
                        "title": r.get("title", ""),
                        "description": r.get("description", ""),
                        "summary": r.get("summary", ""),
                    }
                },
                "valid_days_of_week": json.loads(r.get("valid_days_of_week") or "[]") or None,
                "valid_start_time": r.get("valid_start_time") or None,
                "valid_end_time": r.get("valid_end_time") or None,
                "start_date": r.get("start_date") or None,
                "end_date": r.get("end_date") or None,
                "unique_usage_per_user": str(r.get("unique_usage_per_user", "")).strip().lower() in ("true", "1", "yes"),
                "status": "pending",
            }
            sb = r.get("surprise_bag_data") or ""
            if sb:
                pending["surprise_bag"] = json.loads(sb)
            out.append(pending)
        except Exception:
            # ignore malformed rows instead of breaking the page
            continue
    return out

def remove_offer_from_sheet(restaurant_id, offer_title, offer_type) -> bool:
    ws = _get_ws()
    if not ws:
        return False
    records = ws.get_all_records()
    for i, r in enumerate(records, start=2):  # header row is 1
        if (
            str(r.get("restaurant_id")) == str(restaurant_id)
            and r.get("title") == offer_title
            and r.get("offer_type") == offer_type
        ):
            ws.delete_rows(i)
            return True
    return False

def sync_offers_with_db(restaurant_id, restaurant_name):
    """Deletes pending rows from Sheets when they already exist in DB."""
    try:
        from .queries import check_offer_exists_in_db
    except Exception:
        # queries not available (e.g., local dev without DB)
        return

    ws = _get_ws()
    if not ws:
        return

    records = ws.get_all_records(expected_headers=HEADERS)
    to_delete = []
    for i, r in enumerate(records, start=2):
        if str(r.get("restaurant_id")) != str(restaurant_id):
            continue
        if str(r.get("status", "")).lower() != "pending":
            continue
        title = r.get("title", "")
        otype = r.get("offer_type", "")
        try:
            if check_offer_exists_in_db(restaurant_id, title, otype):
                to_delete.append(i)
        except Exception:
            # if DB is down, skip silently
            pass

    for idx in reversed(to_delete):
        ws.delete_rows(idx)
    if to_delete:
        st.success(f"Synced {len(to_delete)} pending offer(s) with the database.")

