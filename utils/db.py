# utils/db.py
import time
import pandas as pd
import psycopg2
import streamlit as st
from psycopg2.extras import RealDictCursor
from psycopg2 import OperationalError, InterfaceError, DatabaseError
from typing import Any, Iterable, Optional
from .config import get_settings

KEEPALIVE_KW = dict(
    keepalives=1,
    keepalives_idle=30,
    keepalives_interval=10,
    keepalives_count=5,
)

@st.cache_resource(show_spinner=False)
def _connect():
    s = get_settings()
    # sslmode=require is fine for managed PG (Supabase/RDS/etc.)
    return psycopg2.connect(
        host=s.host,
        port=s.port,
        dbname=s.dbname,
        user=s.user,
        password=s.password,
        sslmode="require",
        **KEEPALIVE_KW
    )

def _new_conn():
    # used when a cached conn is broken
    _connect.clear()          # drop cached resource
    return _connect()

def _run(query: str, params: Optional[Iterable[Any]]=None) -> pd.DataFrame:
    """
    Single place to run SELECTs safely with auto-reconnect.
    Returns DataFrame, never raises to the page. Errors -> empty df + st.error once.
    """
    tries = 2
    for attempt in range(tries):
        try:
            conn = _connect()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params or ())
                rows = cur.fetchall()
                return pd.DataFrame(rows)
        except (OperationalError, InterfaceError) as e:
            # connection likely dropped; rebuild once
            if attempt == 0:
                st.warning("DB connection dropped. Reconnecting …")
                time.sleep(0.5)
                conn = _new_conn()
                continue
            else:
                st.error(f"Database connection error: {e}")
                return pd.DataFrame()
        except DatabaseError as e:
            st.error(f"Database error: {e}")
            return pd.DataFrame()
        except Exception as e:
            st.error(f"Unexpected error: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

# public helper
@st.cache_data(ttl=120, show_spinner=False)
def get_df(query: str, params: Optional[Iterable[Any]]=None) -> pd.DataFrame:
    # cache at the dataframe layer; invalidates when query or params change
    return _run(query, params)
