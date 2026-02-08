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
    if "supabase" not in st.secrets:
        st.error("❌ Nerasti Supabase secrets")
        st.stop()
    return create_client(
        st.secrets["supabase"]["url"],
        st.secrets["supabase"]["anon_key"]
    )

supabase = get_supabase()

# =========================
# Login
# =========================
def login(email: str, password: str) -> bool:
    try:
        supabase.auth.sign_in_with_password({"email": email, "password": password})
        return True
    except Exception:
        return False

def logout():
    supabase.auth.sign_out()
    st.session_state.clear()
    st.rerun()

if "authenticated" not in st.session_state:
    st.title("🔐 Prisijungimas")
    email = st.text_input("El. paštas")
    password = st.text_input("Slaptažodis", type="password")
    if st.button("Prisijungti"):
        if email and password and login(email, password):
            st.session_state["authenticated"] = True
            st.session_state["email"] = email
            st.rerun()
        else:
            st.error("❌ Neteisingi duomenys")
    st.stop()

st.success(f"Prisijungta kaip **{st.session_state['email']}**")
if st.button("🚪 Atsijungti"):
    logout()

# =========================
# Konfigūracija
# =========================
TABLE = "biudzetas"
CURRENCY = "€"
LT_MONTHS = ["Sausis","Vasaris","Kovas","Balandis","Gegužė","Birželis",
             "Liepa","Rugpjūtis","Rugsėjis","Spalis","Lapkritis","Gruodis"]

def ym_label(ym: str) -> str:
    y, m = ym.split("-")
    return f"{y} m. {LT_MONTHS[int(m)-1]}"

def money(v: float) -> str:
    return f"{v:,.2f} {CURRENCY}".replace(",", " ")

# =========================
# Naujo įrašo formos funkcija
# =========================
def insert_row(d: date, typ: str, cat: str, merch: str, desc: str, amount: float):
    payload = {
        "id": str(uuid.uuid4()),
        "user_email": st.session_state["email"],
        "data": d.isoformat(),
        "tipas": typ,
        "kategorija": cat or "Nežinoma",
        "prekybos_centras": merch or "",
        "aprasymas": desc or "",
        "suma_eur": float(amount)
    }
    res = supabase.table(TABLE).insert(payload).execute()
    if getattr(res, "error", None):
        st.error(f"Įrašyti nepavyko: {res.error}")
        return False
    return True

def entry_form():
    st.subheader("📝 Naujas įrašas")
    with st.form("entry_form"):
        c1, c2, c3 = st.columns([1,1,1])
        with c1:
            dval = st.date_input("Data", value=date.today())
        with c2:
            tval = st.selectbox("Tipas", ["Išlaidos","Pajamos"])
        with c3:
            aval = st.number_input(f"Suma ({CURRENCY})", min_value=0.0, step=1.0, format="%.2f")
        c4, c5 = st.columns([1,1])
        with c4:
            cat = st.text_input("Kategorija", placeholder="pvz., Maistas / Alga")
        with c5:
            merch = st.text_input("Prekybos centras", placeholder="nebūtina")
        desc = st.text_input("Aprašymas", placeholder="nebūtina")
        submitted = st.form_submit_button("💾 Išsaugoti")
    if submitted:
        ok = insert_row(dval, tval, cat, merch, desc, aval)
        if ok:
            st.success("Įrašyta!")
            st.experimental_rerun()

# =========================
# Duomenų užklausos
# =========================
@st.cache_data(ttl=300)
def fetch_user_data() -> pd.DataFrame:
    data = supabase.table(TABLE).select("*").eq("user_email", st.session_state["email"]).order("data", desc=True).execute().data or []
    df = pd.DataFrame(data)
    if not df.empty:
        df["data"] = pd.to_datetime(df["data"]).dt.date
        df["suma_eur"] = pd.to_numeric(df["suma_eur"], errors="coerce").fillna(0.0)
    return df

def to_excel_bytes(df: pd.DataFrame) -> bytes:
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Duomenys")
    bio.seek(0)
    return bio.read()

def delete_row(row_id):
    res = supabase.table(TABLE).delete().eq("id", row_id).execute()
    if getattr(res, "error", None):
        st.error(f"Trinti nepavyko: {res.error}")
        return False
    return True

# =========================
# Main
# =========================
st.title("💶 Asmeninis biudžetas")

entry_form()

df_user = fetch_user_data()

# =========================
# Filtrai
# =========================
st.subheader("🔎 Filtrai")
unique_years = sorted({d.year for d in df_user["data"]}, reverse=True) if not df_user.empty else []
years_filter = st.selectbox("Metai", ["Visi"] + [str(y) for y in unique_years])
months_filter = st.selectbox("Mėnesiai", ["Visi"] + LT_MONTHS)

df_filtered = df_user.copy()
if years_filter != "Visi":
    df_filtered = df_filtered[df_filtered["data"].apply(lambda d: d.year==int(years_filter))]
if months_filter != "Visi":
    df_filtered = df_filtered[df_filtered["data"].apply(lambda d: LT_MONTHS[d.month-1]==months_filter)]

# =========================
# KPI
# =========================
s_inc = df_filtered.loc[df_filtered["tipas"]=="Pajamos","suma_eur"].sum()
s_exp = df_filtered.loc[df_filtered["tipas"]=="Išlaidos","suma_eur"].sum()
s_bal = s_inc - s_exp

st.subheader("📊 Suvestinė")
c1, c2, c3 = st.columns(3)
c1.metric("Pajamos", money(s_inc))
c2.metric("Išlaidos", money(s_exp))
c3.metric("Balansas", money(s_bal))

# =========================
# Excel parsisiuntimas
# =========================
if not df_filtered.empty:
    xlsb = to_excel_bytes(df_filtered)
    st.download_button(
        "⬇️ Parsisiųsti Excel",
        data=xlsb,
        file_name="biudzetas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# =========================
# Lentelė su trynimu
# =========================
st.subheader("📋 Įrašai")
for idx, row in df_filtered.sort_values("data", ascending=False).iterrows():
    c1, c2 = st.columns([8,1])
    with c1:
        st.write(f"{row['data']} | {row['tipas']} | {row['kategorija']} | {row['prekybos_centras']} | {row['aprasymas']} | {money(row['suma_eur'])}")
    with c2:
        if st.button("🗑️ Ištrinti", key=f"del_{row['id']}"):
            if delete_row(row['id']):
                st.success("Įrašas ištrintas!")
                st.experimental_rerun()

# =========================
# Diagramos
# =========================
st.subheader("📈 Diagramos")

# Išlaidos pagal kategorijas
if not df_filtered.empty and df_filtered[df_filtered["tipas"]=="Išlaidos"].shape[0]>0:
    fig = px.pie(df_filtered[df_filtered["tipas"]=="Išlaidos"], names="kategorija", values="suma_eur",
                 title="Išlaidos pagal kategorijas", hole=0.5)
    st.plotly_chart(fig, use_container_width=True)

# Pajamos vs Išlaidos per mėnesį
if not df_filtered.empty:
    df_monthly = df_filtered.groupby([df_filtered["data"].apply(lambda d: d.strftime("%Y-%m")),"tipas"])["suma_eur"].sum().reset_index()
    df_monthly_pivot = df_monthly.pivot(index="data", columns="tipas", values="suma_eur").fillna(0)
    fig2 = px.line(df_monthly_pivot, y=["Pajamos","Išlaidos"], labels={"value":"Suma (€)","data":"Mėnuo"}, title="Pajamos vs Išlaidos per mėnesį")
    st.plotly_chart(fig2, use_container_width=True)
