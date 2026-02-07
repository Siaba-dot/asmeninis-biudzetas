import streamlit as st
from supabase import create_client
from supabase.client import Client

st.set_page_config(
    page_title="Mano saugi aplikacija",
    page_icon="🔐",
    layout="centered"
)

# ----------------------------
# Supabase klientas (cache)
# ----------------------------
@st.cache_resource(show_spinner=False)
def get_supabase() -> Client:
    if "supabase" not in st.secrets:
        st.error("❌ Nerasti Supabase secrets")
        st.stop()

    return create_client(
        st.secrets["supabase"]["url"],
        st.secrets["supabase"]["anon_key"]
    )

supabase = get_supabase()

# ----------------------------
# Login funkcija
# ----------------------------
def login(email: str, password: str) -> bool:
    try:
        supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        return True
    except Exception:
        return False

# ----------------------------
# Logout
# ----------------------------
def logout():
    supabase.auth.sign_out()
    st.session_state.clear()
    st.rerun()

# ----------------------------
# AUTH CHECK
# ----------------------------
if "authenticated" not in st.session_state:

    st.title("🔐 Prisijungimas")

    email = st.text_input("El. paštas")
    password = st.text_input("Slaptažodis", type="password")

    if st.button("Prisijungti"):
        if not email or not password:
            st.warning("Įvesk el. paštą ir slaptažodį")
        elif login(email, password):
            st.session_state["authenticated"] = True
            st.session_state["email"] = email
            st.rerun()
        else:
            st.error("❌ Neteisingi prisijungimo duomenys")

    st.stop()

# ----------------------------
# APP TURINYS (tik prisijungus)
# ----------------------------
st.success(f"Prisijungta kaip **{st.session_state['email']}**")

st.title("📊 Mano aplikacija")

st.write("Čia jau **TAVO duomenys**. Be login – niekas čia nepateks.")

# Pavyzdys – užklausa į DB
# response = supabase.table("mano_lentele").select("*").execute()
# st.dataframe(response.data)

st.divider()

if st.button("🚪 Atsijungti"):
    logout()
