# app.py
import streamlit as st
from supabase_client import get_supabase, current_user
from auth import render_auth_ui, sign_out

st.set_page_config(page_title="Asmeninis biudžetas", layout="wide")

# 1) Inicijuojam Supabase
supabase = get_supabase()

# 2) Auth siena (jei neprisijungęs – rodys login UI ir stop'ins)
is_authed = render_auth_ui(supabase)
if not is_authed:
    st.stop()

# 3) Prisijungęs vartotojas
user = current_user(supabase)
if not user:
    st.warning("Sesija pasibaigė. Prisijunk iš naujo.")
    st.experimental_rerun()

# 4) Header + atsijungimas
left, right = st.columns([1, 1])
with left:
    st.title("Asmeninis biudžetas")
    st.caption(f"Prisijungta kaip: **{user.email}**")
with right:
    st.write("")
    st.write("")
    if st.button("Atsijungti", use_container_width=True):
        sign_out(supabase)
        st.rerun()

st.divider()

# 5) Čia – tavo programos turinys (stubas, kad matytum, jog auth veikia)
st.subheader("Pradinis skydelis")
st.info("Autentikacija sėkminga. Čia netrukus rodysime tavo biudžeto įrašus iš Supabase su RLS.")

# Pvz. – parodome dabartinį user ID (naudinga kuriant RLS politikomis valdomus įrašus)
st.code(f"Vartotojo ID: {user.id}", language="text")

# TODO (vėlesni žingsniai):
# - Suprojektuoti lenteles Supabase'e (pvz., `transactions`) ir įjungti RLS.
# - Pridėti CRUD UI (įvesti naują išlaidą/pajamą, sąrašas su filtravimu, sumos).
# - Ataskaitos (mėnesio suvestinė, kategorijos, grafikai).
