import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
from supabase import create_client
from supabase.client import Client
import io
import uuid

# =========================
# Supabase klientas
# =========================
@st.cache_resource(show_spinner=False)
def get_supabase() -> Client:
    return create_client(
        st.secrets["supabase"]["url"],
        st.secrets["supabase"]["anon_key"]
    )

supabase = get_supabase()

# =========================
# Login
# =========================
def login(email, password):
    try:
        supabase.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
        return True
    except:
        return False

def logout():
    supabase.auth.sign_out()
    st.session_state.clear()
    st.rerun()

if "auth" not in st.session_state:
    st.title("🔐 Prisijungimas")
    email = st.text_input("El. paštas")
    password = st.text_input("Slaptažodis", type="password")
    if st.button("Prisijungti"):
        if login(email, password):
            st.session_state.auth = True
            st.session_state.email = email
            st.rerun()
        else:
            st.error("❌ Blogi duomenys")
    st.stop()

st.success(f"Prisijungta: **{st.session_state.email}**")
if st.button("🚪 Atsijungti"):
    logout()

# =========================
# Konfigūracija
# =========================
TABLE = "biudzetas"
CURRENCY = "€"

def money(x):
    return f"{x:,.2f} €".replace(",", " ")

# =========================
# Duomenys
# =========================
@st.cache_data(ttl=60)
def fetch_data():
    data = (
        supabase.table(TABLE)
        .select("*")
        .eq("user_email", st.session_state.email)
        .order("data", desc=True)
        .execute()
        .data
        or []
    )
    df = pd.DataFrame(data)
    if not df.empty:
        df["data"] = pd.to_datetime(df["data"])
        df["suma_eur"] = pd.to_numeric(df["suma_eur"])
    return df

def insert_row(d, tipas, kat, merch, desc, suma):
    payload = {
        "id": str(uuid.uuid4()),
        "user_email": st.session_state.email,
        "data": d.isoformat(),
        "tipas": tipas,
        "kategorija": kat,
        "prekybos_centras": merch or "",
        "aprasymas": desc or "",
        "suma_eur": float(suma)
    }
    supabase.table(TABLE).insert(payload).execute()
    st.cache_data.clear()
    st.rerun()

def delete_row(row_id):
    supabase.table(TABLE).delete().eq("id", row_id).execute()
    st.cache_data.clear()
    st.rerun()

# =========================
# Įvedimas
# =========================
st.subheader("📝 Naujas įrašas")
with st.form("add"):
    d = st.date_input("Data", value=date.today())
    t = st.selectbox("Tipas", ["Išlaidos", "Pajamos"])
    s = st.number_input("Suma €", min_value=0.0)
    k = st.text_input("Kategorija")
    m = st.text_input("Prekybos centras")
    a = st.text_input("Aprašymas")
    if st.form_submit_button("💾 Išsaugoti"):
        insert_row(d, t, k, m, a, s)

# =========================
# Filtrai
# =========================
df = fetch_data()

st.subheader("🔎 Filtrai")
years = ["Visi"] + sorted(df["data"].dt.year.unique().astype(str).tolist()) if not df.empty else ["Visi"]
months = ["Visi"] + sorted(df["data"].dt.to_period("M").astype(str).unique().tolist()) if not df.empty else ["Visi"]

y = st.selectbox("Metai", years)
m = st.selectbox("Mėnuo", months)

df_f = df.copy()
if y != "Visi":
    df_f = df_f[df_f["data"].dt.year == int(y)]
if m != "Visi":
    df_f = df_f[df_f["data"].dt.to_period("M").astype(str) == m]

# =========================
# KPI
# =========================
inc = df_f[df_f["tipas"] == "Pajamos"]["suma_eur"].sum()
exp = df_f[df_f["tipas"] == "Išlaidos"]["suma_eur"].sum()

c1, c2, c3 = st.columns(3)
c1.metric("Pajamos", money(inc))
c2.metric("Išlaidos", money(exp))
c3.metric("Balansas", money(inc - exp))

# =========================
# Excel
# =========================
if not df_f.empty:
    bio = io.BytesIO()
    df_f.to_excel(bio, index=False)
    st.download_button(
        "⬇️ Parsisiųsti Excel",
        bio.getvalue(),
        file_name="biudzetas.xlsx"
    )

# =========================
# Lentelė + trynimas
# =========================
st.subheader("📋 Įrašai")

for _, r in df_f.iterrows():
    c1, c2 = st.columns([8,1])
    c1.write(f"{r['data'].date()} | {r['tipas']} | {r['kategorija']} | {money(r['suma_eur'])}")
    if c2.button("🗑️", key=r["id"]):
        delete_row(r["id"])

# =========================
# Diagramos
# =========================
st.subheader("📊 Diagramos")

if not df_f.empty:
    exp_df = df_f[df_f["tipas"] == "Išlaidos"]
    if not exp_df.empty:
        fig1 = px.pie(
            exp_df,
            names="kategorija",
            values="suma_eur",
            title="Išlaidos pagal kategorijas"
        )
        st.plotly_chart(fig1, use_container_width=True)

    ts = (
        df_f
        .groupby([df_f["data"].dt.to_period("M"), "tipas"])["suma_eur"]
        .sum()
        .reset_index()
    )
    ts["data"] = ts["data"].astype(str)

    fig2 = px.line(
        ts,
        x="data",
        y="suma_eur",
        color="tipas",
        title="Pajamos vs išlaidos per laiką"
    )
    st.plotly_chart(fig2, use_container_width=True)

