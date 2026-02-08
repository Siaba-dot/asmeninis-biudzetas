import streamlit as st
import pandas as pd
import plotly.express as px
import io
from datetime import date
from supabase import create_client
from supabase.client import Client
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
# Naujo įrašo funkcija
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

def update_row(row_id, d, typ, cat, merch, desc, amount):
    payload = {
        "data": d.isoformat(),
        "tipas": typ,
        "kategorija": cat or "Nežinoma",
        "prekybos_centras": merch or "",
        "aprasymas": desc or "",
        "suma_eur": float(amount)
    }
    res = supabase.table(TABLE).update(payload).eq("id", row_id).execute()
    if getattr(res, "error", None):
        st.error(f"Atnaujinti nepavyko: {res.error}")
        return False
    return True

def delete_row(row_id):
    res = supabase.table(TABLE).delete().eq("id", row_id).execute()
    if getattr(res, "error", None):
        st.error(f"Ištrinti nepavyko: {res.error}")
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
@st.cache_data(ttl=30)
def fetch_user_data():
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

# =========================
# Main
# =========================
st.title("💶 Asmeninis biudžetas")

entry_form()

df = fetch_user_data()

# Filtrai
st.subheader("🔎 Filtrai")
types = ["Visi"] + df["tipas"].unique().tolist() if not df.empty else ["Visi"]
categories = ["Visos"] + df["kategorija"].unique().tolist() if not df.empty else ["Visos"]

f_type = st.selectbox("Tipas", types)
f_cat = st.selectbox("Kategorija", categories)

df_filtered = df.copy()
if f_type != "Visi":
    df_filtered = df_filtered[df_filtered["tipas"] == f_type]
if f_cat != "Visos":
    df_filtered = df_filtered[df_filtered["kategorija"] == f_cat]

# Lentelė su redagavimu ir trynimu
st.subheader("📋 Įrašai")
for idx, row in df_filtered.iterrows():
    with st.expander(f"{row['data']} | {row['tipas']} | {row['kategorija']} | {row['suma_eur']} {CURRENCY}"):
        c1, c2, c3 = st.columns([1,1,1])
        with c1:
            dval = st.date_input("Data", value=row["data"], key=f"d_{row['id']}")
        with c2:
            tval = st.selectbox("Tipas", ["Išlaidos","Pajamos"], index=0 if row["tipas"]=="Išlaidos" else 1, key=f"t_{row['id']}")
        with c3:
            aval = st.number_input(f"Suma ({CURRENCY})", min_value=0.0, step=1.0, format="%.2f", value=row["suma_eur"], key=f"a_{row['id']}")
        c4, c5 = st.columns([1,1])
        with c4:
            cat = st.text_input("Kategorija", value=row["kategorija"], key=f"c_{row['id']}")
        with c5:
            merch = st.text_input("Prekybos centras", value=row["prekybos_centras"], key=f"m_{row['id']}")
        desc = st.text_input("Aprašymas", value=row["aprasymas"], key=f"dsc_{row['id']}")
        col_save, col_delete = st.columns(2)
        with col_save:
            if st.button("💾 Išsaugoti", key=f"save_{row['id']}"):
                update_row(row["id"], dval, tval, cat, merch, desc, aval)
                st.experimental_rerun()
        with col_delete:
            if st.button("🗑️ Ištrinti", key=f"del_{row['id']}"):
                delete_row(row["id"])
                st.experimental_rerun()

# KPI
st.subheader("📊 KPI")
s_inc = df.loc[df["tipas"]=="Pajamos","suma_eur"].sum() if not df.empty else 0.0
s_exp = df.loc[df["tipas"]=="Išlaidos","suma_eur"].sum() if not df.empty else 0.0
s_bal = s_inc - s_exp
c1, c2, c3 = st.columns(3)
c1.metric("Pajamos", money(s_inc))
c2.metric("Išlaidos", money(s_exp))
c3.metric("Balansas", money(s_bal))

# Excel parsisiuntimas
if not df.empty:
    xlsb = to_excel_bytes(df)
    st.download_button(
        "⬇️ Parsisiųsti Excel",
        data=xlsb,
        file_name=f"biudzetas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# Pajamos vs išlaidos per mėnesį
if not df.empty:
    st.subheader("📈 Pajamos vs Išlaidos per mėnesį")
    df_month = df.copy()
    df_month["ym"] = pd.to_datetime(df_month["data"]).dt.to_period("M")
    df_group = df_month.groupby(["ym","tipas"])["suma_eur"].sum().reset_index()
    fig = px.bar(df_group, x="ym", y="suma_eur", color="tipas", barmode="group",
                 labels={"ym":"Mėnuo", "suma_eur":f"Suma ({CURRENCY})","tipas":"Tipas"})
    st.plotly_chart(fig, use_container_width=True)

# Išlaidos pagal kategorijas
if not df.empty:
    st.subheader("🍔 Išlaidos pagal kategorijas")
    df_exp = df[df["tipas"]=="Išlaidos"]
    if not df_exp.empty:
        fig2 = px.pie(df_exp, names="kategorija", values="suma_eur", title="Išlaidos pagal kategorijas", hole=0.5)
        st.plotly_chart(fig2, use_container_width=True)
