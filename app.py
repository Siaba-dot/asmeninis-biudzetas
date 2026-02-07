# -*- coding: utf-8 -*-
# Asmeninis biudžetas — vieno failo Streamlit aplikacija be išorinių importų (auth integruotas)
# Skirta veikti be jokių papildomų modulių/importų iš kitų failų.
# Pastaba: jei nori debug prieš UI, naudok print(), o ne st.write(), nes
# st.set_page_config PRIVALO būti pirmoji Streamlit komanda.

import os
import sys
from datetime import datetime, date
from io import BytesIO

import pandas as pd
import streamlit as st

# ------------------------------------------------------------
# (Ne Streamlit) diagnostika į LOGUS (saugiai prieš UI)
# ------------------------------------------------------------
print("DEBUG VERSION MARKER:", "v2026-02-07-3")
print("DEBUG __file__:", __file__)
print("DEBUG CWD:", os.getcwd())
try:
    print("DEBUG listdir(__dir__):", os.listdir(os.path.dirname(os.path.abspath(__file__)))[:50])
except Exception as _e:
    print("DEBUG listdir exception:", repr(_e))
print("DEBUG sys.path head:", sys.path[:3])

# ------------------------------------------------------------
# PIRMA Streamlit komanda: puslapio konfigūracija
# ------------------------------------------------------------
st.set_page_config(
    page_title="Asmeninis biudžetas",
    page_icon="💶",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ------------------------------------------------------------
# Minimalus CSS – kompaktiškas išdėstymas, mažesni viršutiniai tarpai
# ------------------------------------------------------------
st.markdown(
    """
    <style>
      header {visibility: hidden;} /* paslepia viršutinę juostą */
      .block-container {padding-top: 1rem; padding-bottom: 1rem; max-width: 1400px;}
      /* tamsesnė/„neon“ nuotaika be perdėto ryškumo */
      .stMetric {background: #111; border-radius: 8px; padding: 0.75rem; border: 1px solid #222;}
      .stButton>button {background:#1f2937; color:#e5e7eb; border:1px solid #374151;}
      .stButton>button:hover {background:#111827; border-color:#4b5563;}
      .stDownloadButton>button {background:#1f2937; color:#e5e7eb; border:1px solid #374151;}
      .stDownloadButton>button:hover {background:#111827; border-color:#4b5563;}
      .css-1dp5vir edgvbvh3, .st-emotion-cache-16txtl3 {padding-top:0rem !important;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------
# Autentifikacija (integruota čia, be jokių kitų failų)
# ------------------------------------------------------------
def _init_auth_state():
    if "auth" not in st.session_state:
        st.session_state.auth = {"is_authenticated": False, "user_email": None, "ts": None}

def render_auth_ui():
    st.markdown("### Prisijungimas")
    with st.form("login_form", clear_on_submit=False):
        email = st.text_input("El. paštas", placeholder="pvz., vardas@pastas.lt")
        password = st.text_input("Slaptažodis", type="password", placeholder="••••••••")
        submitted = st.form_submit_button("Prisijungti", use_container_width=True)

    # DEMO logika (pakeisk į tikrą – pvz., prieš DB ar supabase)
    VALID = {
        "sigita@example.com": "123456",
        "demo@demo.lt": "demo",
    }

    if submitted:
        if not email or not password:
            st.error("Įvesk el. paštą ir slaptažodį.")
            return
        if email in VALID and password == VALID[email]:
            st.session_state.auth = {
                "is_authenticated": True,
                "user_email": email,
                "ts": datetime.utcnow().isoformat(),
            }
            st.success("Sėkmingai prisijungta ✅")
            st.rerun()
        else:
            st.error("Neteisingi prisijungimo duomenys.")

def sign_out():
    st.session_state.auth = {"is_authenticated": False, "user_email": None, "ts": None}
    st.experimental_rerun()

# ------------------------------------------------------------
# Biudžeto duomenų valdymas
# ------------------------------------------------------------
def _init_budget_state():
    if "budget_df" not in st.session_state:
        st.session_state.budget_df = pd.DataFrame(
            columns=["Data", "Tipas", "Kategorija", "Aprašymas", "Suma (€)"]
        )

def add_transaction_row(dt: date, ttype: str, category: str, note: str, amount: float):
    row = {
        "Data": dt.strftime("%Y-%m-%d"),
        "Tipas": ttype,  # "Pajamos" arba "Išlaidos"
        "Kategorija": category.strip(),
        "Aprašymas": note.strip(),
        "Suma (€)": float(f"{float(amount):.2f}"),  # 2 skaitmenys po kablelio
    }
    st.session_state.budget_df = pd.concat(
        [st.session_state.budget_df, pd.DataFrame([row])],
        ignore_index=True,
    )

def compute_summary(df: pd.DataFrame):
    if df.empty:
        return 0.0, 0.0, 0.0
    pajamos = df.loc[df["Tipas"] == "Pajamos", "Suma (€)"].sum()
    islaidos = df.loc[df["Tipas"] == "Išlaidos", "Suma (€)"].sum()
    balansas = round(pajamos - islaidos, 2)
    return round(pajamos, 2), round(islaidos, 2), balansas

# ------------------------------------------------------------
# UI komponentai
# ------------------------------------------------------------
def render_topbar():
    left, mid, right = st.columns([1.2, 2, 1])
    with left:
        st.markdown("## 💶 Asmeninis biudžetas")
    with mid:
        st.caption("")
    with right:
        user = st.session_state.auth.get("user_email")
        st.caption(f"Prisijungta: **{user}**" if user else "")
        st.button("Atsijungti", on_click=sign_out, use_container_width=True)

def render_budget_form():
    st.markdown("### Naujas įrašas")
    c1, c2, c3, c4, c5 = st.columns([1.1, 1, 1.2, 2, 1.1])
    with c1:
        dt = st.date_input("Data", value=datetime.today(), format="YYYY-MM-DD")
    with c2:
        ttype = st.selectbox("Tipas", ["Pajamos", "Išlaidos"], index=1)
    with c3:
        category = st.text_input("Kategorija", placeholder="pvz., Maistas, Nuoma, Alga")
    with c4:
        note = st.text_input("Aprašymas", placeholder="Trumpas paaiškinimas")
    with c5:
        amount = st.number_input("Suma (€)", min_value=0.00, value=0.00, step=0.10, format="%.2f")

    c6, c7 = st.columns([1, 1])
    with c6:
        if st.button("➕ Pridėti", use_container_width=True):
            if amount <= 0:
                st.warning("Suma turi būti didesnė už 0.")
            elif not category.strip():
                st.warning("Įvesk kategoriją.")
            else:
                add_transaction_row(dt, ttype, category, note, amount)
                st.success("Įrašas pridėtas.")
                st.rerun()
    with c7:
        if st.button("🧹 Išvalyti visus įrašus", use_container_width=True):
            st.session_state.budget_df = st.session_state.budget_df.iloc[0:0].copy()
            st.rerun()

def render_budget_table_and_summary():
    st.markdown("### Įrašai")
    df = st.session_state.budget_df
    if df.empty:
        st.info("Dar nėra įrašų. Pridėk pirmą įrašą viršuje.")
    else:
        st.dataframe(
            df.sort_values(by="Data", ascending=False),
            use_container_width=True,
            hide_index=True,
        )

    pajamos, islaidos, balansas = compute_summary(df)
    st.markdown("---")
    s1, s2, s3 = st.columns(3)
    with s1:
        st.metric("Pajamos", f"{pajamos:,.2f} €")
    with s2:
        st.metric("Išlaidos", f"{islaidos:,.2f} €")
    with s3:
        st.metric("Balansas", f"{balansas:,.2f} €", delta=f"{(pajamos - islaidos):,.2f} €")

def render_export():
    st.markdown("### Eksportas")
    df = st.session_state.budget_df
    if df.empty:
        st.caption("Nėra ką eksportuoti.")
        return

    # CSV
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Atsisiųsti CSV",
        data=csv_bytes,
        file_name=f"biudzetas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    # Excel (bandome su openpyxl; jei nėra – rodom žinutę)
    try:
        with BytesIO() as output:
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name="Biudžetas", index=False)
            st.download_button(
                "⬇️ Atsisiųsti Excel",
                data=output.getvalue(),
                file_name=f"biudzetas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
    except Exception as e:
        st.caption("Excel eksportui reikia `openpyxl`. Jei nematai mygtuko – pridėk `openpyxl` į requirements.txt.")

# ------------------------------------------------------------
# Pagrindinė funkcija
# ------------------------------------------------------------
def main():
    _init_auth_state()

    if not st.session_state.auth["is_authenticated"]:
        render_auth_ui()
        return

    _init_budget_state()
    render_topbar()

    with st.container():
        form_col, table_col = st.columns([1.05, 1.95])
        with form_col:
            render_budget_form()
            st.markdown("---")
            render_export()
        with table_col:
            render_budget_table_and_summary()

# ------------------------------------------------------------
# Įėjimo taškas
# ------------------------------------------------------------
if __name__ == "__main__":
    main()

  
  
