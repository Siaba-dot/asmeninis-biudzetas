# -*- coding: utf-8 -*-
# Asmeninis biudžetas — vieno failo Streamlit aplikacija be išorinių importų (auth integruotas)
# Sukurta taip, kad veiktų Streamlit Cloud be papildomų kelių ar paketų.

import os
import sys
from datetime import datetime
import streamlit as st
import pandas as pd

# ------------------------------------------------------------
# Puslapio konfigūracija (kompaktiškas išdėstymas, nėra nereikalingų tarpų)
# ------------------------------------------------------------
st.set_page_config(
    page_title="Asmeninis biudžetas",
    page_icon="💶",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Minimalus CSS, kad "viršus" būtų glaustesnis
st.markdown(
    """
    <style>
      .stAppDeployButton, header {visibility: hidden;}
      .block-container {padding-top: 1rem; padding-bottom: 1rem; max-width: 1400px;}
      .st-emotion-cache-ue6h4q {padding-top: 0rem;} /* kartais reikalinga Cloud'e */
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------
# Autentifikacija (integruota vietoje importo from auth)
# ------------------------------------------------------------
def _init_auth_state():
    if "auth" not in st.session_state:
        st.session_state.auth = {
            "is_authenticated": False,
            "user_email": None,
            "ts": None,
        }

def render_auth_ui():
    """Paprastas prisijungimas. Vėliau galėsi pakeisti į savo logiką (DB, API, OAuth)."""
    st.markdown("### Prisijungimas")
    with st.form("login_form", clear_on_submit=False):
        email = st.text_input("El. paštas", placeholder="pvz., vardas@pastas.lt")
        password = st.text_input("Slaptažodis", type="password", placeholder="••••••••")
        submitted = st.form_submit_button("Prisijungti", use_container_width=True)

    # DEMO tikslams – paprastas tikrinimas (pakeisk į savo)
    VALID_EMAILS = {
        # Pakeisk savo kredencialais ar prisijungimų sąrašu. Jei nenori slaptažodžio – komentuok eilutes žemiau.
        "sigita@example.com": "123456",
        "demo@demo.lt": "demo",
    }

    if submitted:
        if email.strip() == "" or password.strip() == "":
            st.error("Įvesk el. paštą ir slaptažodį.")
            return

        if email in VALID_EMAILS and password == VALID_EMAILS[email]:
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
    st.session_state.auth = {
        "is_authenticated": False,
        "user_email": None,
        "ts": None,
    }
    st.experimental_rerun()

# ------------------------------------------------------------
# Asmeninio biudžeto logika (paprastas pavyzdys)
# ------------------------------------------------------------
def _init_budget_state():
    if "budget_df" not in st.session_state:
        # Minimalus pavyzdinis DataFrame
        st.session_state.budget_df = pd.DataFrame(
            columns=["Data", "Tipas", "Kategorija", "Aprašymas", "Suma (€)"]
        )

def add_transaction_row(date, ttype, category, note, amount):
    row = {
        "Data": date.strftime("%Y-%m-%d") if isinstance(date, datetime) else str(date),
        "Tipas": ttype,  # "Pajamos" arba "Išlaidos"
        "Kategorija": category,
        "Aprašymas": note,
        "Suma (€)": round(float(amount), 2),
    }
    st.session_state.budget_df = pd.concat(
        [st.session_state.budget_df, pd.DataFrame([row])], ignore_index=True
    )

def compute_summary(df: pd.DataFrame):
    if df.empty:
        return 0.0, 0.0, 0.0
    pajamos = df.loc[df["Tipas"] == "Pajamos", "Suma (€)"].sum()
    islaidos = df.loc[df["Tipas"] == "Išlaidos", "Suma (€)"].sum()
    balansas = round(pajamos - islaidos, 2)
    return round(pajamos, 2), round(islaidos, 2), balansas

# ------------------------------------------------------------
# UI blokai
# ------------------------------------------------------------
def render_topbar():
    left, mid, right = st.columns([1.2, 2, 1])
    with left:
        st.markdown("## 💶 Asmeninis biudžetas")
    with mid:
        st.write("")
    with right:
        user = st.session_state.auth.get("user_email")
        st.caption(f"Prisijungta: **{user}**")
        st.button("Atsijungti", on_click=sign_out, use_container_width=True)

def render_budget_form():
    st.markdown("### Įrašas")
    c1, c2, c3, c4, c5 = st.columns([1.2, 1, 1.2, 2, 1])
    default_date = datetime.today()
    with c1:
        date = st.date_input("Data", value=default_date)
    with c2:
        ttype = st.selectbox("Tipas", ["Pajamos", "Išlaidos"], index=1)
    with c3:
        category = st.text_input("Kategorija", placeholder="pvz., Maistas, Nuoma, Alga")
    with c4:
        note = st.text_input("Aprašymas", placeholder="Trumpas paaiškinimas")
    with c5:
        amount = st.number_input("Suma (€)", min_value=0.00, value=0.00, step=0.10, format="%.2f")

    c6, _ = st.columns([1, 3])
    with c6:
        if st.button("➕ Pridėti", use_container_width=True):
            if amount <= 0:
                st.warning("Suma turi būti didesnė už 0.")
            elif category.strip() == "":
                st.warning("Įvesk kategoriją.")
            else:
                add_transaction_row(date, ttype, category.strip(), note.strip(), amount)
                st.success("Įrašas pridėtas.")
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
        delta = pajamos - islaidos
        st.metric("Balansas", f"{balansas:,.2f} €", delta=f"{delta:,.2f} €")

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

    # Excel
    from io import BytesIO
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Biudžetas", index=False)
    st.download_button(
        "⬇️ Atsisiųsti Excel",
        data=output.getvalue(),
        file_name=f"biudzetas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

# ------------------------------------------------------------
# App paleidimas
# ------------------------------------------------------------
def main():
    _init_auth_state()

    if not st.session_state.auth["is_authenticated"]:
        # Prisijungimo ekranas
        render_auth_ui()
        return

    # Autentifikuotas ekranas
    _init_budget_state()
    render_topbar()

    with st.container():
        form_col, table_col = st.columns([1.1, 1.9])
        with form_col:
            render_budget_form()
            render_export()
        with table_col:
            render_budget_table_and_summary()

if __name__ == "__main__":
    main()

