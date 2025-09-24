# utils/db.py
import pandas as pd
import psycopg2
import streamlit as st
from psycopg2 import OperationalError, InterfaceError
from typing import Any, Iterable, Optional
from .config import get_settings
import numpy as np
from psycopg2.extensions import TRANSACTION_STATUS_INERROR

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

def _normalize_param(x: Any) -> Any:
    if isinstance(x, (np.integer,)):   # np.int64, np.int32, ...
        return int(x)
    if isinstance(x, (np.floating,)):  # np.float64, ...
        return float(x)
    if isinstance(x, (list, tuple)):   # normalize nested sequences if you ever pass IN (...) arrays etc.
        return type(x)(_normalize_param(v) for v in x)
    return x

@st.cache_data(ttl=120, show_spinner=False)
def get_df(query: str, params: Optional[Iterable[Any]] = None) -> pd.DataFrame:
    # cache at the dataframe layer; invalidates when query or params change
    if params is not None:
        params = tuple(_normalize_param(x) for x in params)
    return _run(query, params)

def _run(query: str, params=None) -> pd.DataFrame:
    """
    Execute a query using the cached connection from _connect().
    - If a previous error left the TX aborted -> rollback before executing
    - Rollback on any exception
    - Recreate the connection and retry once on Interface/Operational errors
    - Commit after every execute (including SELECT) to clear TX state
    """
    conn = _connect()

    def _execute_with(conn_):
        # If previous statement failed, connection may be in "aborted" state; clear it.
        ts = getattr(conn_, "get_transaction_status", lambda: None)()
        if ts == TRANSACTION_STATUS_INERROR:
            try:
                conn_.rollback()
            except Exception:
                pass

        with conn_.cursor() as cur:
            cur.execute(query, params)
            if cur.description:  # SELECT-like
                rows = cur.fetchall()
                cols = [c[0] for c in cur.description]
                conn_.commit()  # clear tx state; safe even for reads
                return pd.DataFrame(rows, columns=cols)
            else:
                conn_.commit()
                return pd.DataFrame()

    try:
        return _execute_with(conn)
    except (InterfaceError, OperationalError):
        # connection broken: drop cached resource and retry once
        conn = _new_conn()
        try:
            return _execute_with(conn)
        except Exception as e2:
            try:
                conn.rollback()
            except Exception:
                pass
            raise e2
    except Exception as e:
        # Any other DB error: rollback so we don't poison the session
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    
def table_exists(schema: str, name: str) -> bool:
    df = _run("SELECT to_regclass(%s) IS NOT NULL AS exists", (f"{schema}.{name}",))
    return bool(df.iloc[0]["exists"])