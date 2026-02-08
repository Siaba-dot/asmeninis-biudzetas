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
        supabase.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
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

LT_MONTHS = [
    "Sausis","Vasaris","Kovas","Balandis","Gegužė","Birželis",
    "Liepa","Rugpjūtis","Rugsėjis","Spalis","Lapkritis","Gruodis"
]

def ym_label(ym: str) -> str:
    y, m = ym.split("-")
    return f"{y} m. {LT_MONTHS[int(m)-1]}"

def money(v: float) -> str:
    return f"{v:,.2f} {CURRENCY}".replace(",", " ")

# =========================
# Insert
# =========================
def insert_row(d, typ, cat, merch, desc, amount):
    payload = {
        "id": str(uuid.uuid4()),
        "data": d.isoformat(),
        "tipas": typ,
        "kategorija": cat or "Nežinoma",
        "prekybos_centras": merch or "",
        "aprasymas": desc or "",
        "suma_eur": float(amount)
    }

    supabase.table(TABLE).insert(payload).execute()
    return True

# =========================
# Naujo įrašo forma
# =========================
def entry_form():
    st.subheader("📝 Naujas įrašas")

    with st.form("entry_form"):
        c1, c2, c3 = st.columns(3)

        with c1:
            dval = st.date_input("Data", value=date.today())
        with c2:
            tval = st.selectbox("Tipas", ["Išlaidos", "Pajamos"])
        with c3:
            aval = st.number_input(
                f"Suma ({CURRENCY})",
                min_value=0.0,
                step=1.0,
                format="%.2f"
            )

        c4, c5 = st.columns(2)
        with c4:
            cat = st.text_input("Kategorija")
        with c5:
            merch = st.text_input("Prekybos centras (nebūtina)")

        desc = st.text_input("Aprašymas (nebūtina)")
        submitted = st.form_submit_button("💾 Išsaugoti")

    if submitted:
        insert_row(dval, tval, cat, merch, desc, aval)
        st.success("✅ Įrašyta")
        st.cache_data.clear()
        st.rerun()

# =========================
# Duomenų užklausos
# =========================
@st.cache_data(ttl=300)
def fetch_months():
    rows = supabase.table(TABLE).select("data").execute().data or []
    months = {
        f"{pd.to_datetime(r['data']).year:04d}-"
        f"{pd.to_datetime(r['data']).month:02d}"
        for r in rows
    }
    return sorted(months)

@st.cache_data(ttl=300)
def fetch_month_df(ym):
    y, m = map(int, ym.split("-"))
    start = date(y, m, 1).isoformat()
    end = date(y + (m == 12), (m % 12) + 1, 1).isoformat()

    rows = (
        supabase.table(TABLE)
        .select("*")
        .gte("data", start)
        .lt("data", end)
        .execute()
        .data
        or []
    )

    df = pd.DataFrame(rows)
    if not df.empty:
        df["data"] = pd.to_datetime(df["data"]).dt.date
        df["suma_eur"] = pd.to_numeric(df["suma_eur"])

    return df

# =========================
# Excel eksportas
# =========================
def to_excel_bytes(df: pd.DataFrame) -> bytes:
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Duomenys")
    bio.seek(0)
    return bio.read()

# =========================
# UI
# =========================
st.title("💶 Asmeninis biudžetas")

entry_form()

months = fetch_months()
if not months:
    st.info("Dar nėra duomenų")
    st.stop()

selected_month = st.selectbox(
    "📅 Pasirink mėnesį",
    months,
    format_func=ym_label
)

df_month = fetch_month_df(selected_month)

# =========================
# KPI
# =========================
if not df_month.empty:
    inc = df_month.loc[df_month["tipas"] == "Pajamos", "suma_eur"].sum()
    exp = df_month.loc[df_month["tipas"] == "Išlaidos", "suma_eur"].sum()

    st.subheader("📊 Suvestinė")
    c1, c2, c3 = st.columns(3)
    c1.metric("Pajamos", money(inc))
    c2.metric("Išlaidos", money(exp))
    c3.metric("Balansas", money(inc - exp))

    # Excel mygtukas
    st.download_button(
        label="⬇️ Parsisiųsti Excel",
        data=to_excel_bytes(df_month),
        file_name=f"biudzetas_{selected_month}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# =========================
# Lentelė
# =========================
st.subheader("📋 Įrašai")

if df_month.empty:
    st.info("Šiam mėnesiui įrašų nėra")
else:
    df_show = (
        df_month
        .sort_values("data", ascending=False)
        [["data", "tipas", "kategorija", "prekybos_centras", "aprasymas", "suma_eur"]]
    )

    st.dataframe(
        df_show,
        use_container_width=True,
        hide_index=True
    )

# =========================
# Diagrama
# =========================
if not df_month.empty:
    df_exp = df_month[df_month["tipas"] == "Išlaidos"]

    if not df_exp.empty:
        fig = px.pie(
            df_exp,
            names="kategorija",
            values="suma_eur",
            title="Išlaidos pagal kategorijas",
            hole=0.4
        )
        st.plotly_chart(fig, use_container_width=True)
