# sb_auth.py
import streamlit as st
from supabase import Client
from typing import Optional, Any

# --- Sesijos helperiai ---
def get_session():
    """Gauk dabartinę Supabase sesiją iš session_state (jei jau prisijungta)."""
    return st.session_state.get("sb_session")

def set_session(session):
    """
    Išsaugok sesiją į session_state.
    Jei tai pydantic modelis – konvertuojam į dict, kad vėliau netrūktų .get().
    """
    try:
        # Pydantic v2
        st.session_state["sb_session"] = session.model_dump()
    except Exception:
        try:
            # Pydantic v1
            st.session_state["sb_session"] = session.dict()
        except Exception:
            # Jei jau yra dict arba paprastas objektas – saugom tiesiogiai
            st.session_state["sb_session"] = session

def clear_session():
    # Minimaliai išvalom mūsų naudojamus raktus
    st.session_state.pop("sb_session", None)
    st.session_state.pop("refresh_key", None)
    st.session_state.pop("login_email", None)
    st.session_state.pop("login_pwd", None)
    st.session_state.pop("magic_email", None)

# --- Auth veiksmai ---
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

# --- Vidinis helperis: saugiai paimti access_token ---
def _get_token_from_session(sb_sess: Any):
    if sb_sess is None:
        return None
    # dict atvejis
    if isinstance(sb_sess, dict):
        return sb_sess.get("access_token")
    # pydantic modelis ar kitas objektas
    return getattr(sb_sess, "access_token", None)

# --- UI ---
def render_auth_ui(supabase: Client) -> bool:
    """
    Rodo login UI jei vartotojas NE prisijungęs.
    Grąžina True, jei prisijungta; False, jei dar reikia prisijungti.
    """
    # 1) Tiesioginis patikrinimas: jei get_user suveikia – esam prisijungę
    try:
        supabase.auth.get_user()
        return True
    except Exception:
        pass  # neturim galiojančios sesijos supabase kliente – rodysim UI

    # 2) Fallback: jei turim cache'intą sesiją – pabandykim vėl
    sb_sess = get_session()
    token = _get_token_from_session(sb_sess)
    if token:
        try:
            supabase.auth.get_user()
            return True
        except Exception:
            # Sesija pasibaigė ar neteisinga – išvalom ir rodome login UI
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
