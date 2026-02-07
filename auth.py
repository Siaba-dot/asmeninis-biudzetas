# auth.py
import streamlit as st
from supabase import Client
from typing import Optional

# --- Sesijos helperiai ---
def get_session():
    """Gauk dabartinę Supabase sesiją iš session_state (jei jau prisijungta)."""
    return st.session_state.get("sb_session")

def set_session(session):
    """Išsaugok sesiją į session_state."""
    st.session_state["sb_session"] = session

def clear_session():
    st.session_state.pop("sb_session", None)

# --- Auth veiksmai ---
def sign_out(supabase: Client):
    try:
        supabase.auth.sign_out()
    finally:
        clear_session()

def sign_in_password(supabase: Client, email: str, password: str) -> Optional[str]:
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        set_session(res.session)
        return None
    except Exception as e:
        return str(e)

def sign_up_password(supabase: Client, email: str, password: str) -> Optional[str]:
    try:
        _ = supabase.auth.sign_up({"email": email, "password": password})
        # Jei Supabase'e įjungtas email confirm, vartotojas turės patvirtinti laišku.
        return None
    except Exception as e:
        return str(e)

def send_magic_link(supabase: Client, email: str) -> Optional[str]:
    try:
        supabase.auth.sign_in_with_otp({"email": email, "shouldCreateUser": True})
        return None
    except Exception as e:
        return str(e)

# --- UI ---
def render_auth_ui(supabase: Client) -> bool:
    """
    Rodo login UI jei vartotojas NE prisijungęs.
    Grąžina True, jei prisijungta; False, jei dar reikia prisijungti.
    """
    # Jei turime sesiją — pabandom gauti user'į (patikrinti ar token dar galioja)
    sb_sess = get_session()
    if sb_sess and sb_sess.get("access_token"):
        try:
            supabase.auth.get_user()
            return True
        except Exception:
            sign_out(supabase)

    st.markdown("### Prisijungimas")
    tabs = st.tabs(["El. paštas + slaptažodis", "Magic link"])

    # --- Email + password ---
    with tabs[0]:
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("El. paštas", key="login_email")
            password = st.text_input("Slaptažodis", type="password", key="login_pwd")
            c1, c2 = st.columns(2)
            submit = c1.form_submit_button("Prisijungti")
            create = c2.form_submit_button("Sukurti paskyrą")
        if submit:
            err = sign_in_password(supabase, email, password)
            if err:
                st.error(f"Nepavyko prisijungti: {err}")
            else:
                st.rerun()
        if create:
            err = sign_up_password(supabase, email, password)
            if err:
                st.error(f"Nepavyko sukurti paskyros: {err}")
            else:
                st.success("Paskyra sukurta. Jei reikia — patvirtink el. pašte.")

    # --- Magic link ---
    with tabs[1]:
        with st.form("magic_form", clear_on_submit=False):
            email2 = st.text_input("El. paštas (atsiųsime vienkartinę nuorodą)", key="magic_email")
            send = st.form_submit_button("Siųsti magic link")
        if send:
            err = send_magic_link(supabase, email2)
            if err:
                st.error(f"Nepavyko išsiųsti: {err}")
            else:
                st.success("Nuoroda išsiųsta. Patikrink el. paštą.")

    return False
