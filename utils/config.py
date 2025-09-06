import streamlit as st
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    dbname: str
    user: str
    password: str

def get_settings() -> Settings:
    return Settings(
        host=st.secrets["PG_HOST"],
        port=int(st.secrets["PG_PORT"]),
        dbname=st.secrets["PG_DBNAME"],
        user=st.secrets["PG_USER"],
        password=st.secrets["PG_PASSWORD"],
    )
