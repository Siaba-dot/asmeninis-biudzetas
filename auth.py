# auth.py
import streamlit as st
from supabase import Client

def clear_session():
    # Išvalom tik tai, ką naudojam patys; jei nori – gali naudoti ir st.session_state.clear(),
    # bet čia laikomės minimalaus "scope".
    st.session_state.pop("sb_session", None)
    st.session_state.pop("refresh_key", None)
    st.session_state.pop("login_email", None)
    st.session_state.pop("login_pwd", None)
    st.session_state.pop("magic_email", None)

def sign_out(supabase: Client):
    try:
        supabase.auth.sign_out()
    finally:
        # 1) Išvalom mūsų sesiją/būseną
        clear_session()
        # 2) Išvalom Streamlit kešus, kad kitas run'as gautų švarią būseną
        try:
            st.cache_data.clear()
        except Exception:
            pass
        try:
            st.cache_resource.clear()
        except Exception:
            pass
