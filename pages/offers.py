# pages/offers.py
import os
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st
import streamlit_authenticator as st_auth

import utils.queries as q  # for get_restaurant_id_for_login

st.set_page_config(layout="wide")

# ---------- Config ----------
OFFERS_CSV_PATH = "offers.csv"  # temporary store; later swap with your API

def get_admin_usernames():
    """
    Optional convention: in .streamlit/secrets.toml add:
      [auth]
      admins = ["admin", "safwan"]
    If not present, default to ["admin"].
    """
    try:
        admins = list(st.secrets["auth"].get("admins", []))
        return admins if admins else ["admin"]
    except Exception:
        return ["admin"]

ADMIN_USERS = set(get_admin_usernames())

# ---------- Auth (same pattern as analytics.py) ----------
def load_auth_from_secrets():
    try:
        s = st.secrets["auth"]
        creds = {"usernames": {}}
        for uname, uinfo in s["credentials"]["usernames"].items():
            creds["usernames"][uname] = {
                "email": uinfo["email"],
                "name":  uinfo["name"],
                "password": uinfo["password"],
            }
        cookie_conf = s["cookie"]
        preauth = s.get("preauthorized", {"emails": []})
        assert cookie_conf["name"] and cookie_conf["key"]
        return creds, cookie_conf, preauth
    except Exception as e:
        st.error(f"Auth configuration error: {e}")
        st.stop()

credentials, cookie_conf, preauthorized = load_auth_from_secrets()
authenticator = st_auth.Authenticate(
    credentials, cookie_conf["name"], cookie_conf["key"], cookie_conf["expiry_days"], preauthorized
)
name, authentication_status, username = authenticator.login("Login", "main")

# ---------- Storage helpers ----------
def _offers_schema_df() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "id", "restaurant_id", "username",
            "title", "description",
            "offer_type", "discount_value",
            "start_date", "expiry_date",
            "active", "approval_status",
            "created_at", "last_modified",
        ]
    )

def load_offers_df() -> pd.DataFrame:
    if os.path.exists(OFFERS_CSV_PATH):
        df = pd.read_csv(OFFERS_CSV_PATH, dtype=str)
        if not df.empty and "active" in df.columns:
            df["active"] = df["active"].fillna("False").astype(str)
        return df
    return _offers_schema_df()

def save_offers_df(df: pd.DataFrame) -> None:
    df.to_csv(OFFERS_CSV_PATH, index=False)

def next_offer_id(df: pd.DataFrame) -> str:
    if df.empty or "id" not in df.columns:
        return "1"
    try:
        return str(df["id"].astype(int).max() + 1)
    except Exception:
        return str(len(df) + 1)

def _s(v) -> str:
    """Safe str for UI."""
    try:
        import pandas as pd
        if v is None:
            return ""
        if isinstance(v, float) and pd.isna(v):
            return ""
    except Exception:
        if v is None:
            return ""
    return str(v)

# def generate_coupon_code(n: int = 8) -> str:
#     alphabet = string.ascii_uppercase + string.digits
#     return "".join(random.choice(alphabet) for _ in range(n))

# ---------- UI helpers ----------
def show_offer_table(df: pd.DataFrame, title: str):
    st.subheader(title)
    if df.empty:
        st.info("No offers yet.")
        return
    display_df = df.copy()
    for col in ["start_date", "expiry_date", "created_at", "last_modified"]:
        if col in display_df.columns:
            display_df[col] = display_df[col].fillna("")
    st.dataframe(
        display_df[
            [
                "id", "title", "offer_type", "discount_value",
                "start_date", "expiry_date", "active", "approval_status", "last_modified"
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

def _safe_parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        return None

def offer_form(defaults: dict, *, submit_label: str = "Submit") -> dict:
    """
    Render the form and return a dict with the field values (no coupon code).
    For BOGO/Combo we do not show any 'Value' input; for Time-Based % we show a slider.
    Campaign dates are selected via a single date-range picker.
    """
    d_start = _safe_parse_date(defaults.get("start_date"))
    d_end   = _safe_parse_date(defaults.get("expiry_date"))
    if d_start and d_end:
        range_value = (d_start, d_end)
    else:
        today = date.today()
        range_value = (today, today + timedelta(days=30))

    with st.form("offer_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            title = st.text_input("Offer title", value=defaults.get("title", ""), max_chars=80)
            offer_type = st.selectbox(
                "Offer type",
                ["BOGO", "Combo", "Time-Based %"],
                index=["BOGO","Combo","Time-Based %"].index(defaults.get("offer_type","BOGO"))
                if defaults.get("offer_type") in ["BOGO","Combo","Time-Based %"] else 0
            )

            if offer_type == "Time-Based %":
                discount_value = st.slider(
                    "Discount percent",
                    min_value=1, max_value=90,
                    value=int(defaults.get("discount_value", "10") or 10), step=1
                )
                discount_value = str(discount_value)
            else:
                discount_value = ""  # hidden for BOGO/Combo

        with col2:
            description = st.text_area("Offer description", value=defaults.get("description", ""), height=120)

        # Single range picker for campaign window (Start, End)
        dr = st.date_input(
            "Campaign dates",
            value=range_value,            # tuple => range
            format="MM.DD.YYYY",
        )

        active = st.checkbox("Active", value=(str(defaults.get("active", "True")).lower() == "true"))
        submitted = st.form_submit_button(submit_label)

        start_out, end_out = "", ""
        if isinstance(dr, (list, tuple)) and len(dr) == 2 and dr[0] and dr[1]:
            start_out = str(dr[0])
            end_out   = str(dr[1])

        return {
            "submitted": submitted,
            "title": title.strip(),
            "description": description.strip(),
            "offer_type": offer_type,
            "discount_value": (discount_value or "").strip(),
            "start_date": start_out,
            "expiry_date": end_out,
            "active": str(bool(active)),
        }

def _row_overlaps_range(row, range_start: date, range_end: date) -> bool:
    rs = _safe_parse_date(row.get("start_date")) or date.min
    re = _safe_parse_date(row.get("expiry_date")) or date.max
    return max(rs, range_start) <= min(re, range_end)

def render_offer_list(df: pd.DataFrame):
    """
    Full-width list: one bordered container per offer with Edit/Delete inside.
    """
    if df is None or df.empty:
        st.info("No offers yet.")
        return

    df = df.fillna("")
    for _, row in df.iterrows():
        with st.container(border=True):
            # Header
            left, right = st.columns([0.8, 0.2])
            with left:
                st.markdown(f"### {_s(row['title'])}")
                st.caption(f"Status: {_s(row.get('approval_status','Pending'))}")
            with right:
                badge = "🟢 Active" if _s(row.get("active","False")).lower() == "true" else "⚪ Inactive"
                st.markdown(f"<div style='text-align:right;'>{badge}</div>", unsafe_allow_html=True)

            # Body
            if _s(row.get("description", "")):
                st.write(_s(row.get("description","")))

            m1, m2, m3 = st.columns(3)
            with m1:
                st.caption("Type")
                st.write(_s(row.get("offer_type","")))
            with m2:
                st.caption("Value")
                if _s(row.get("offer_type")) == "Time-Based %":
                    st.write(f"{_s(row.get('discount_value',''))}%")
                else:
                    st.write("—")
            with m3:
                st.caption("Dates")
                s = _s(row.get("start_date")) or "—"
                e = _s(row.get("expiry_date")) or "—"
                st.write(f"{s} → {e}")

            # Actions (inside same container)
            a1, a2 = st.columns([0.1, 0.1])
            with a1:
                if st.button("Edit", key=f"edit_{row['id']}"):
                    st.session_state["edit_offer_id"] = row["id"]
                    st.rerun()
            with a2:
                if st.button("Delete", key=f"del_{row['id']}"):
                    df_all = load_offers_df().fillna("")
                    idx = df_all.index[df_all["id"] == row["id"]]
                    if len(idx) == 1:
                        df_all = df_all.drop(idx)
                        save_offers_df(df_all)
                        st.success("Offer deleted.")
                        st.rerun()
                    else:
                        st.error("Could not locate this offer to delete.")

# ---------- Page logic ----------
if authentication_status is False:
    st.error("Username/password is incorrect")
elif authentication_status is None:
    st.warning("Please enter your username and password")
elif authentication_status:
    display_name = credentials["usernames"][username]["name"]
    st.sidebar.title(f"Welcome {display_name}")
    authenticator.logout("Logout", "sidebar")
    st.title(f"Offers • {display_name}")

    is_admin = username in ADMIN_USERS
    offers_df = load_offers_df()

    # ----- ADMIN FLOW (no "My Offers") -----
    if is_admin:
        st.subheader("Admin • Review & Approve Offers")

        # Admin date-range filter (campaign window)
        today = date.today()
        default_start = today - timedelta(days=30)
        default_end = today + timedelta(days=60)
        dr = st.date_input(
            "Filter by campaign dates",
            (default_start, default_end),
            format="MM.DD.YYYY",
        )
        if isinstance(dr, (list, tuple)) and len(dr) == 2:
            rstart, rend = dr
            if rstart and rend:
                mask = offers_df.apply(lambda r: _row_overlaps_range(r, rstart, rend), axis=1)
                filtered_admin_df = offers_df[mask]
            else:
                filtered_admin_df = offers_df
        else:
            filtered_admin_df = offers_df

        pending = filtered_admin_df[filtered_admin_df["approval_status"].isin(["Pending", "Edit Pending"])].copy()
        show_offer_table(pending.sort_values("last_modified", ascending=False), "Pending Approval")

        if not pending.empty:
            id_to_review = st.selectbox(
                "Select pending offer",
                options=pending["id"].tolist(),
                format_func=lambda oid: f"{oid} • {pending.loc[pending['id']==oid, 'title'].values[0]}",
            )
            selected = pending.loc[pending["id"] == id_to_review].iloc[0].to_dict()

            with st.expander("Offer details", expanded=True):
                st.write({k: selected[k] for k in [
                    "id","restaurant_id","username","title","description",
                    "offer_type","discount_value",
                    "start_date","expiry_date","active","approval_status","last_modified"
                ]})

            colA, colB = st.columns(2)
            with colA:
                if st.button("Approve", type="primary"):
                    new_df = offers_df.copy()
                    idx = new_df.index[new_df["id"] == id_to_review]
                    if len(idx) == 1:
                        i = idx[0]
                        new_df.at[i, "approval_status"] = "Approved"
                        new_df.at[i, "last_modified"] = datetime.utcnow().isoformat()
                        save_offers_df(new_df)
                        st.success("Offer approved.")
                        offers_df = new_df
                    else:
                        st.error("Could not locate the offer to approve.")
            with colB:
                if st.button("Reject"):
                    reason = st.text_input("Rejection reason (optional)", key="rej_reason")
                    new_df = offers_df.copy()
                    idx = new_df.index[new_df["id"] == id_to_review]
                    if len(idx) == 1:
                        i = idx[0]
                        new_df.at[i, "approval_status"] = "Rejected"
                        new_df.at[i, "last_modified"] = datetime.utcnow().isoformat()
                        # optionally persist `reason` to a new column
                        save_offers_df(new_df)
                        st.warning("Offer rejected.")
                        offers_df = new_df

        st.markdown("---")
        show_offer_table(offers_df.sort_values("last_modified", ascending=False), "All Offers")
        st.stop()  # do not render restaurant UI for admins

    # ----- RESTAURANT FLOW (only "My Offers") -----
    rid_df = q.get_restaurant_id_for_login(username)
    if rid_df.empty:
        st.error(f"Could not find restaurant ID for {username}.")
        st.stop()
    restaurant_id = str(int(rid_df.iloc[0]["id"]))

    st.subheader("Create or Edit Offers")

    my_offers_full = offers_df[offers_df["restaurant_id"] == restaurant_id].copy()

    edit_id = st.session_state.get("edit_offer_id")
    rec = my_offers_full.loc[my_offers_full["id"] == edit_id] if edit_id else pd.DataFrame()

    st.markdown("#### " + ("Edit Offer" if not rec.empty else "Add New Offer"))

    defaults = {
        "title": "",
        "description": "",
        "offer_type": "BOGO",
        "discount_value": "",
        "start_date": "",
        "expiry_date": "",
        "active": "True",
    }
    if not rec.empty:
        defaults.update(rec.iloc[0].to_dict())

    vals = offer_form(defaults, submit_label=("Save Changes" if not rec.empty else "Submit"))

    if vals["submitted"]:
        new_df = offers_df.copy()
        now = datetime.utcnow().isoformat()

        if not rec.empty:
            idx = new_df.index[new_df["id"] == edit_id]
            if len(idx) == 1:
                i = idx[0]
                new_df.at[i, "title"] = vals["title"]
                new_df.at[i, "description"] = vals["description"]
                new_df.at[i, "offer_type"] = vals["offer_type"]
                new_df.at[i, "discount_value"] = vals["discount_value"]
                new_df.at[i, "start_date"] = vals["start_date"]
                new_df.at[i, "expiry_date"] = vals["expiry_date"]
                new_df.at[i, "active"] = vals["active"]
                new_df.at[i, "approval_status"] = "Edit Pending"
                new_df.at[i, "last_modified"] = now
                save_offers_df(new_df)
                st.success("Offer update submitted for approval.")
                if "edit_offer_id" in st.session_state:
                    del st.session_state["edit_offer_id"]
                st.rerun()
            else:
                st.error("Could not find the selected offer to update.")
        else:
            if not vals["title"]:
                st.error("Please provide an offer title.")
            else:
                oid = next_offer_id(new_df)
                row = {
                    "id": oid,
                    "restaurant_id": restaurant_id,
                    "username": username,
                    "title": vals["title"],
                    "description": vals["description"],
                    "offer_type": vals["offer_type"],
                    "discount_value": vals["discount_value"],
                    "start_date": vals["start_date"],
                    "expiry_date": vals["expiry_date"],
                    "active": vals["active"],
                    "approval_status": "Pending",
                    "created_at": now,
                    "last_modified": now,
                }
                new_df = pd.concat([new_df, pd.DataFrame([row])], ignore_index=True)
                save_offers_df(new_df)
                st.success("Offer submitted for approval.")
                st.rerun()

    st.markdown("---")

    # Restaurant date-range filter (campaign window)
    today = date.today()
    default_start = today - timedelta(days=60)
    default_end = today + timedelta(days=120)
    dr = st.date_input(
        "Filter by campaign dates",
        (default_start, default_end),
        format="MM.DD.YYYY",
    )
    my_offers = my_offers_full.copy()
    if isinstance(dr, (list, tuple)) and len(dr) == 2:
        rstart, rend = dr
        if rstart and rend:
            mask = my_offers.apply(lambda r: _row_overlaps_range(r, rstart, rend), axis=1)
            my_offers = my_offers[mask]

    st.subheader("Your Offers")
    if "last_modified" in my_offers.columns:
        my_offers = my_offers.sort_values("last_modified", ascending=False)
    my_offers = my_offers.fillna("")
    render_offer_list(my_offers)
