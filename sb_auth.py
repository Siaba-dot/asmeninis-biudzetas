# sb_auth.py
import streamlit as st
from supabase import Client
from typing import Optional, Any, Tuple

# -----------------------------
# Session helpers
# -----------------------------
SESSION_KEY = "sb_session"

def get_session() -> Any:
    return st.session_state.get(SESSION_KEY)

def set_session(session: Any) -> None:
    """
    Save Supabase session into Streamlit session_state.
    Supports pydantic v1/v2 or dict.
    """
    if session is None:
        st.session_state.pop(SESSION_KEY, None)
        return

    # Try pydantic v2
    try:
        st.session_state[SESSION_KEY] = session.model_dump()
        return
    except Exception:
        pass

    # Try pydantic v1
    try:
        st.session_state[SESSION_KEY] = session.dict()
        return
    except Exception:
        pass

    # Already dict / plain object
    st.session_state[SESSION_KEY] = session

def clear_session_state() -> None:
    for k in [SESSION_KEY, "login_email", "login_pwd", "magic_email"]:
        st.session_state.pop(k, None)

def _get_tokens_from_session(sb_sess: Any) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract access_token and refresh_token from stored session.
    """
    if sb_sess is None:
        return None, None

    if isinstance(sb_sess, dict):
        return sb_sess.get("access_token"), sb_sess.get("refresh_token")

    # Object-like (pydantic model etc.)
    return getattr(sb_sess, "access_token", None), getattr(sb_sess, "refresh_token", None)

def restore_session_into_client(supabase: Client) -> bool:
    """
    IMPORTANT: Streamlit reruns the script; supabase client may lose auth state.
    This restores the session into the client using stored tokens.
    Returns True if restored and user is valid.
    """
    sb_sess = get_session()
    access_token, refresh_token = _get_tokens_from_session(sb_sess)

    if not access_token or not refresh_token:
        return False

    try:
        # supabase-py v2
        supabase.auth.set_session(access_token, refresh_token)
        supabase.auth.get_user()  # validate
        return True
    except Exception:
        # Session invalid/expired
        return False


# -----------------------------
# Auth actions
# -----------------------------
def sign_out(supabase: Client) -> None:
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    finally:
        clear_session_state()
        # optional cache clear
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
    """
    Creates user. If 'Confirm email' is ON in Supabase, user must confirm via email
    before password sign-in will succeed (often looks like "invalid login credentials").
    """
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        # Some configs may return session immediately; store it if exists.
        try:
            if getattr(res, "session", None) is not None:
                set_session(res.session)
        except Exception:
            pass
        return None
    except Exception as e:
        return str(e)

def send_magic_link(supabase: Client, email: str) -> Optional[str]:
    try:
        # shouldCreateUser=True allows new user creation via magic link
        supabase.auth.sign_in_with_otp({"email": email, "shouldCreateUser": True})
        return None
    except Exception as e:
        return str(e)


# -----------------------------
# UI
# -----------------------------
def render_auth_ui(supabase: Client) -> bool:
    """
    If already authenticated -> True
    Otherwise show auth UI -> False
    """

    # 0) Try restoring auth from Streamlit session_state into supabase client
    if restore_session_into_client(supabase):
        return True

    # 1) If client already has valid user (e.g., same run right after login)
    try:
        supabase.auth.get_user()
        return True
    except Exception:
        pass

    st.markdown("## Prisijungimas")

    tabs = st.tabs(["El. paštas + slaptažodis", "Magic link"])

    # --- Email + password tab ---
    with tabs[0]:
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("El. paštas", key="login_email")
            password = st.text_input("Slaptažodis", type="password", key="login_pwd")

            c1, c2, c3 = st.columns([1, 1, 1])
            btn_login = c1.form_submit_button("Prisijungti")
            btn_signup = c2.form_submit_button("Sukurti paskyrą")
            btn_logout = c3.form_submit_button("Atsijungti")

        if btn_logout:
            sign_out(supabase)
            st.rerun()

        if btn_login:
            err = sign_in_password(supabase, email.strip(), password)
            if err:
                # Supabase tyčia dažnai grąžina "invalid login credentials"
                st.error("Neteisingi duomenys arba nepatvirtintas el. paštas.")
                st.caption(f"Techninė klaida: {err}")
            else:
                st.rerun()

        if btn_signup:
            err = sign_up_password(supabase, email.strip(), password)
            if err:
                st.error("Nepavyko sukurti paskyros.")
                st.caption(f"Techninė klaida: {err}")
            else:
                st.success("Paskyra sukurta. Jei reikia — patvirtink el. pašte (jei įjungtas Confirm email).")

    # --- Magic link tab ---
    with tabs[1]:
        with st.form("magic_form", clear_on_submit=False):
            email2 = st.text_input("El. paštas (atsiųsime vienkartinę nuorodą)", key="magic_email")
            btn_send = st.form_submit_button("Siųsti magic link")

        if btn_send:
            err = send_magic_link(supabase, email2.strip())
            if err:
                st.error("Nepavyko išsiųsti magic link.")
                st.caption(f"Techninė klaida: {err}")
            else:
                st.success("Nuoroda išsiųsta. Patikrink el. paštą.")

    return False
