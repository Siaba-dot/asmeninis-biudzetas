import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
from supabase import create_client
from supabase.client import Client
import io

st.set_page_config(page_title="💶 Asmeninis biudžetas", layout="wide")

# ======================================================
# Supabase
# ======================================================
@st.cache_resource
def get_supabase() -> Client:
    return create_client(
        st.secrets["supabase"]["url"],
        st.secrets["supabase"]["anon_key"]
    )

supabase = get_supabase()
TABLE = "biudzetas"
CURRENCY = "€"

# ======================================================
# AUTH
# ======================================================
def login(email, password):
    try:
        supabase.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
        return True
    except Exception:
        return False

def logout():
    supabase.auth.sign_out()
    st.session_state.clear()
    st.stop()

if "authenticated" not in st.session_state:
    st.title("🔐 Prisijungimas")
    email = st.text_input("El. paštas")
    password = st.text_input("Slaptažodis", type="password")
    if st.button("Prisijungti"):
        if login(email, password):
            st.session_state["authenticated"] = True
            st.session_state["email"] = email
            st.success("Prisijungta")
            st.stop()
        else:
            st.error("Neteisingi duomenys")
    st.stop()

st.sidebar.success(f"👤 {st.session_state['email']}")
if st.sidebar.button("🚪 Atsijungti"):
    logout()

USER_EMAIL = st.session_state["email"]

# ======================================================
# DATA
# ======================================================
@st.cache_data
def fetch_user_data(email: str) -> pd.DataFrame:
    data = (
        supabase.table(TABLE)
        .select("*")
        .eq("user_email", email)
        .order("data")
        .execute()
        .data
        or []
    )
    df = pd.DataFrame(data)
    if df.empty:
        return df

    df["data"] = pd.to_datetime(df["data"])
    df["suma_eur"] = pd.to_numeric(df["suma_eur"], errors="coerce").fillna(0.0)
    df["year"] = df["data"].dt.year
    df["month"] = df["data"].dt.to_period("M").astype(str)
    return df

def insert_row(d, tipas, kategorija, prekyba, aprasymas, suma):
    supabase.table(TABLE).insert({
        "user_email": USER_EMAIL,
        "data": d.isoformat(),
        "tipas": tipas,
        "kategorija": kategorija,
        "prekybos_centras": prekyba,
        "aprasymas": aprasymas,
        "suma_eur": float(suma)
    }).execute()
    st.cache_data.clear()

def delete_row(row_id):
    supabase.table(TABLE).delete().eq("id", row_id).execute()
    st.cache_data.clear()

# ======================================================
# UI – ENTRY
# ======================================================
st.title("💶 Asmeninis biudžetas")

with st.expander("➕ Naujas įrašas", expanded=True):
    with st.form("entry"):
        c1, c2, c3 = st.columns(3)
        with c1:
            d = st.date_input("Data", date.today())
        with c2:
            tipas = st.selectbox("Tipas", ["Pajamos", "Išlaidos"])
        with c3:
            suma = st.number_input("Suma (€)", min_value=0.0, step=1.0)

        kategorija = st.text_input("Kategorija")
        prekyba = st.text_input("Prekybos vieta (nebūtina)")
        aprasymas = st.text_input("Aprašymas (nebūtina)")

        if st.form_submit_button("💾 Išsaugoti"):
            insert_row(d, tipas, kategorija, prekyba, aprasymas, suma)
            st.success("Įrašyta")

# ======================================================
# LOAD DATA
# ======================================================
df = fetch_user_data(USER_EMAIL)

if df.empty:
    st.info("Dar nėra įrašų")
    st.stop()

# ======================================================
# FILTERS
# ======================================================
st.subheader("🔎 Filtrai")

c1, c2 = st.columns(2)
with c1:
    year_filter = st.selectbox(
        "Metai",
        ["Visi"] + sorted(df["year"].unique().tolist())
    )
with c2:
    month_filter = st.selectbox(
        "Mėnuo",
        ["Visi"] + sorted(df["month"].unique().tolist())
    )

df_f = df.copy()
if year_filter != "Visi":
    df_f = df_f[df_f["year"] == year_filter]
if month_filter != "Visi":
    df_f = df_f[df_f["month"] == month_filter]

# ======================================================
# KPI
# ======================================================
income = df_f[df_f["tipas"] == "Pajamos"]["suma_eur"].sum()
expense = df_f[df_f["tipas"] == "Išlaidos"]["suma_eur"].sum()
balance = income - expense

st.subheader("📊 KPI")
k1, k2, k3 = st.columns(3)
k1.metric("Pajamos", f"{income:,.2f} €")
k2.metric("Išlaidos", f"{expense:,.2f} €")
k3.metric("Balansas", f"{balance:,.2f} €")

# ======================================================
# TABLE + DELETE
# ======================================================
st.subheader("📋 Įrašai")

for _, r in df_f.sort_values("data", ascending=False).iterrows():
    cols = st.columns([1.2, 1.2, 2, 1, 0.5])
    cols[0].write(r["data"].date())
    cols[1].write(r["tipas"])
    cols[2].write(r["kategorija"])
    cols[3].write(f"{r['suma_eur']:.2f} €")
    if cols[4].button("🗑️", key=r["id"]):
        delete_row(r["id"])
        st.stop()

# ======================================================
# CHARTS
# ======================================================
st.subheader("📈 Analitika")

df_cum = (
    df.sort_values("data")
      .assign(
          signed=lambda x: x["suma_eur"].where(
              x["tipas"] == "Pajamos", -x["suma_eur"]
          )
      )
)
df_cum["balansas"] = df_cum["signed"].cumsum()

fig_bal = px.line(
    df_cum,
    x="data",
    y="balansas",
    title="Kaupiamasis balansas"
)
st.plotly_chart(fig_bal, use_container_width=True)

df_exp = df_f[df_f["tipas"] == "Išlaidos"]
if not df_exp.empty:
    fig_cat = px.pie(
        df_exp,
        names="kategorija",
        values="suma_eur",
        title="Išlaidos pagal kategorijas"
    )
    st.plotly_chart(fig_cat, use_container_width=True)

# ======================================================
# EXPORT
# ======================================================
st.subheader("⬇️ Eksportas")

bio = io.BytesIO()
with pd.ExcelWriter(bio, engine="openpyxl") as writer:
    df_f.to_excel(writer, index=False)
bio.seek(0)

st.download_button(
    "Parsisiųsti Excel",
    data=bio.read(),
    file_name="biudzetas.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
