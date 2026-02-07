# -*- coding: utf-8 -*-
# Asmeninis biudžetas — vieno failo Streamlit aplikacija
# Autentifikacija tik per st.secrets (Secrets manager), be jokio jautraus kodo repo.

import os
import sys
from datetime import datetime, date
from io import BytesIO

import streamlit as st
import pandas as pd

# ------------------------------------------------------------
# PIRMA Streamlit komanda — puslapio konfigūracija
# ------------------------------------------------------------
st.set_page_config(
    page_title="Asmeninis biudžetas",
    page_icon="💶",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ------------------------------------------------------------
# Minimalus CSS — kompaktiškas išdėstymas
# ------------------------------------------------------------
st.markdown(
    """
    <style>
      header {visibility: hidden;}
      .block-container {padding-top: 1rem; padding-bottom: 1rem; max-width: 1400px;}
      .stMetric {background: #111; border-radius: 8px; padding: 0.75rem; border: 1px solid #222;}
      .stButton>button, .stDownloadButton>button {
        background:#1f2937; color:#e5e7eb; border:1px solid #374151;
      }
      .stButton>button:hover, .stDownloadButton>button:hover {
        background:#111827; border-color:#4b5563;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------
# Autentifikacija iš st.secrets
# Palaiko: plaintext password ARBA bcrypt password_hash (st.secrets)
# ------------------------------------------------------------
def _read_users_from_secrets():
    """Grąžina vartotojų sąrašą iš st.secrets. Jei nieko nėra, grąžina []."""
    try:
        users = st.secrets["auth"]["users"]
        if not isinstance(users, (list, tuple)):
            return []
        # normalizuojam raktus
        norm = []
        for u in users:
            if not isinstance(u, dict):
                continue
            norm.append({
                "email": str(u.get("email", "")).strip(),
                "password": u.get("password"),           # plaintext pasirinktinai
                "password_hash": u.get("password_hash"), # bcrypt hash pasirinktinai
            })
        return norm
    except Exception:
        return []

def _bcrypt_check(password, password_hash):
    """Patikrina bcrypt hash. Jei bcrypt nėra instaliuotas – grąžina False."""
    try:
        import bcrypt
    except Exception:
        return False
    try:
        if isinstance(password, str):
            password = password.encode("utf-8")
        if isinstance(password_hash, str):
            password_hash = password_hash.encode("utf-8")
        return bcrypt.checkpw(password, password_hash)
    except Exception:
        return False

def _is_valid_credentials(email: str, password: str) -> bool:
    """Leidžia prisijungti, jei atitinka plaintext arba bcrypt hash iš secrets."""
    email = (email or "").strip()
    password = (password or "")
    if not email or not password:
        return False

    users = _read_users_from_secrets()
    for u in users:
        if u.get("email") == email:
            # 1) bcrypt
            ph = u.get("password_hash")
            if ph and _bcrypt_check(password, ph):
                return True
            # 2) plaintext (jei pasirinkta)
            pw = u.get("password")
            if isinstance(pw, str) and pw == password:
                return True
    return False

def _init_auth_state():
    if "auth" not in st.session_state:
        st.session_state.auth = {"is_authenticated": False, "user_email": None, "ts": None}

def render_auth_ui():
    users = _read_users_from_secrets()
    if not users:
        st.error(
            "Nerasti prisijungimo duomenys `st.secrets`. "
            "Eik į *Manage app → Settings → Secrets* ir pridėk [auth].users sąrašą. "
            "Žr. README instrukciją arba kreipkis dėl pavyzdžio."
        )
        with st.expander("Greitas pavyzdys (plaintext)", expanded=False):
            st.code(
                '''[auth]
users = [
  { email = "vardas@pastas.lt", password = "slaptazodis" }
]''',
                language="toml",
            )
        with st.expander("Greitas pavyzdys (bcrypt)", expanded=False):
            st.code(
                '''[auth]
users = [
  { email = "vardas@pastas.lt", password_hash = "$2b$12$...." }
]''',
                language="toml",
            )
        return

    st.markdown("### Prisijungimas")
    with st.form("login_form", clear_on_submit=False):
        email = st.text_input("El. paštas", placeholder="pvz., vardas@pastas.lt")
        password = st.text_input("Slaptažodis", type="password", placeholder="••••••••")
        submitted = st.form_submit_button("Prisijungti", use_container_width=True)

    if submitted:
        if _is_valid_credentials(email, password):
            st.session_state.auth = {
                "is_authenticated": True,
                "user_email": email.strip(),
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
# Biudžeto logika
# ------------------------------------------------------------
def _init_budget_state():
    if "budget_df" not in st.session_state:
        st.session_state.budget_df = pd.DataFrame(
            columns=["Data", "Tipas", "Kategorija", "Aprašymas", "Suma (€)"]
        )

def add_transaction_row(dt: date, ttype: str, category: str, note: str, amount: float):
    row = {
        "Data": dt.strftime("%Y-%m-%d"),
        "Tipas": ttype,
        "Kategorija": (category or "").strip(),
        "Aprašymas": (note or "").strip(),
        "Suma (€)": round(float(amount), 2),
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
# UI
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
            elif not (category or "").strip():
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

    # Excel
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
    except Exception:
        st.caption("Excel eksportui reikia `openpyxl`. Įtrauk į requirements.txt, jei mygtukas neveikia.")

# ------------------------------------------------------------
# App
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

if __name__ == "__main__":
    main()
