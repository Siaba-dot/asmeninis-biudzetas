import streamlit as st
from supabase_client import get_supabase
from auth import render_auth_ui, sign_out

st.set_page_config(page_title="Asmeninis biudžetas", layout="wide")

supabase = get_supabase()

# 1) Auth siena
is_authed = render_auth_ui(supabase)
if not is_authed:
    st.stop()

# 2) Jei prisijungęs – rodom programą
st.title("Asmeninis biudžetas")
user = supabase.auth.get_user().user
st.caption(f"Prisijungta kaip: {user.email}")

if st.button("Atsijungti"):
    sign_out(supabase)
    st.rerun()

# -- Čia tavo app logika (skaitymas/rašymas į lenteles su RLS) --
# pvz.:
# data = supabase.table("transactions").select("*").order("date", desc=True).execute()
# st.dataframe(data.data)
