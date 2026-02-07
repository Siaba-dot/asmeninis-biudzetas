# supabase_client.py
import streamlit as st
from supabase import create_client, Client


@st.cache_resource
def get_supabase() -> Client:
    """
    Sukuria ir kešuoja Supabase klientą.
    Veikia tiek lokaliai su .streamlit/secrets.toml, tiek Streamlit Cloud su App → Secrets.
    """
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["anon_key"]
    return create_client(url, key)


def current_user(supabase: Client):
    """
    Patogus helper'is gauti prisijungusį vartotoją.
    Gražina None, jei sesija negalioja.
    """
    try:
        return supabase.auth.get_user().user
    except Exception:
        return None
