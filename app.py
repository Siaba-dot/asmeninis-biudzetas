import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from datetime import date
from supabase import create_client
from supabase.client import Client
import io

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
        else:
            st.warning("Įrašas neįrašytas.")

# =========================
# Duomenų užklausos
# =========================
@st.cache_data(ttl=300)
def fetch_months() -> list:
    data = supabase.table(TABLE).select("data").order("data").execute().data or []
    months = sorted({f"{pd.to_datetime(r['data']).year:04d}-{pd.to_datetime(r['data']).month:02d}" for r in data})
    return months

@st.cache_data(ttl=300)
def fetch_month_df(ym: str) -> pd.DataFrame:
    y, m = map(int, ym.split("-"))
    start = date(y, m, 1).isoformat()
    end = date(y + (m==12), (m % 12)+1, 1).isoformat()
    data = supabase.table(TABLE).select("*").gte("data", start).lt("data", end).execute().data or []
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

# =========================
# Main
# =========================
st.title("💶 Asmeninis biudžetas")

entry_form()

months = fetch_months()
if not months:
    st.info("Nėra duomenų")
    st.stop()

selected_month = st.selectbox("Pasirink mėnesį", months, format_func=ym_label)
df_month = fetch_month_df(selected_month)

# Suvestinė
if not df_month.empty:
    s_inc = df_month.loc[df_month["tipas"]=="Pajamos","suma_eur"].sum()
    s_exp = df_month.loc[df_month["tipas"]=="Išlaidos","suma_eur"].sum()
    s_bal = s_inc - s_exp
    st.subheader("📊 Suvestinė")
    c1, c2, c3 = st.columns(3)
    c1.metric("Pajamos", money(s_inc))
    c2.metric("Išlaidos", money(s_exp))
    c3.metric("Balansas", money(s_bal))

    # Parsisiuntimo Excel
    xlsb = to_excel_bytes(df_month)
    st.download_button(
        "⬇️ Parsisiųsti Excel",
        data=xlsb,
        file_name=f"biudzetas_{selected_month}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# Diagramos – pavyzdys
if not df_month.empty:
    fig = px.pie(df_month[df_month["tipas"]=="Išlaidos"], names="kategorija", values="suma_eur",
                 title="Išlaidos pagal kategorijas", hole=0.5)
    st.plotly_chart(fig, use_container_width=True)

