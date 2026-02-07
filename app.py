import os
import io
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
from typing import List, Optional
from supabase import create_client, Client

# =========================
# KONFIGŪRACIJA
# =========================
TABLE = "biudzetas"
COL_DATE = "data"
COL_TYPE = "tipas"
COL_MERCHANT = "prekybos_centras"
COL_CATEGORY = "kategorija"
COL_DESC = "aprasymas"
COL_AMOUNT = "suma_eur"

CURRENCY = "€"
DEFAULT_MONTHS_TREND = 12
SHOW_ENTRY_FORM = True
SHOW_EXPORT_XLSX = True

# =========================
# PAGE CONFIG + STILIUS
# =========================
st.set_page_config(
    page_title="Asmeninis biudžetas",
    page_icon="💶",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# =========================
# Supabase kliento inicializacija
# =========================
@st.cache_resource(show_spinner=False)
def get_supabase() -> Client:
    if "supabase" not in st.secrets or not isinstance(st.secrets["supabase"], dict):
        st.error("❌ Secrets nerasta sekcija [supabase].")
        st.stop()
    url = st.secrets["supabase"].get("url")
    key = st.secrets["supabase"].get("anon_key")
    if not url or not key:
        st.error("❌ Trūksta [supabase] reikšmių.")
        st.stop()
    return create_client(url, key)

supabase: Client = get_supabase()

# =========================
# LOGIN
# =========================
def _has_local_auth() -> bool:
    return "auth" in st.secrets and isinstance(st.secrets["auth"], dict) and isinstance(st.secrets["auth"].get("users"), list)

def _check_local_credentials(email: str, password: str) -> bool:
    try:
        for u in st.secrets["auth"]["users"]:
            if u.get("email") == email and u.get("password") == password:
                return True
    except Exception:
        pass
    return False

def login_ui() -> bool:
    if _has_local_auth():
        if st.session_state.get("auth_ok"):
            return True
        st.subheader("🔐 Prisijungimas")
        with st.form("login_form_local", border=False):
            email = st.text_input("El. paštas")
            pwd = st.text_input("Slaptažodis", type="password")
            submitted = st.form_submit_button("Prisijungti")
        if submitted:
            if _check_local_credentials(email, pwd):
                st.session_state["auth_ok"] = True
                st.session_state["auth_user_email"] = email
                st.experimental_rerun()
            else:
                st.error("Neteisingi duomenys.")
        return False
    else:
        access = st.session_state.get("sb_access_token")
        refresh = st.session_state.get("sb_refresh_token")
        if access and refresh:
            try:
                supabase.auth.set_session(access_token=access, refresh_token=refresh)
            except Exception:
                pass
        if supabase.auth.get_session().session:
            return True
        st.subheader("🔐 Prisijungimas")
        with st.form("login_form_sb", border=False):
            email = st.text_input("El. paštas")
            pwd = st.text_input("Slaptažodis", type="password")
            submitted = st.form_submit_button("Prisijungti")
        if submitted:
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": pwd})
                if res and res.session:
                    st.session_state["sb_access_token"] = res.session.access_token
                    st.session_state["sb_refresh_token"] = res.session.refresh_token
                    st.experimental_rerun()
                else:
                    st.error("Neteisingi duomenys.")
            except Exception as e:
                st.error(f"Prisijungti nepavyko: {e}")
        return False

def logout_ui():
    if _has_local_auth():
        if st.sidebar.button("Atsijungti"):
            st.session_state.pop("auth_ok", None)
            st.session_state.pop("auth_user_email", None)
            st.experimental_rerun()
    else:
        if st.sidebar.button("Atsijungti"):
            try:
                supabase.auth.sign_out()
            except Exception:
                pass
            for k in ("sb_access_token", "sb_refresh_token"):
                st.session_state.pop(k, None)
            st.experimental_rerun()

# =========================
# Pagalbinės funkcijos
# =========================
LT_MONTHS = ["Sausis","Vasaris","Kovas","Balandis","Gegužė","Birželis",
             "Liepa","Rugpjūtis","Rugsėjis","Spalis","Lapkritis","Gruodis"]

def ym_label(ym: str) -> str:
    y, m = ym.split("-")
    return f"{y} m. {LT_MONTHS[int(m)-1]}"

def money(v: float) -> str:
    return f"{v:,.2f} {CURRENCY}".replace(",", " ")

# =========================
# DB funkcijos
# =========================
@st.cache_data(show_spinner=False, ttl=300)
def fetch_months() -> List[str]:
    data = supabase.table(TABLE).select(COL_DATE).order(COL_DATE).execute().data or []
    seen, months = set(), []
    for row in data:
        dval = row.get(COL_DATE)
        if not dval: 
            continue
        d = pd.to_datetime(dval).to_pydatetime()
        ym = f"{d.year:04d}-{d.month:02d}"
        if ym not in seen:
            seen.add(ym)
            months.append(ym)
    months.sort()
    return months

@st.cache_data(show_spinner=False, ttl=300)
def fetch_month_df(ym: str) -> pd.DataFrame:
    y, m = map(int, ym.split("-"))
    start = date(y, m, 1).isoformat()
    end = date(y + (m==12), (m%12)+1, 1).isoformat()
    data = supabase.table(TABLE).select(f"id,{COL_DATE},{COL_TYPE},{COL_MERCHANT},{COL_CATEGORY},{COL_DESC},{COL_AMOUNT}").gte(COL_DATE, start).lt(COL_DATE, end).order(COL_DATE, desc=True).execute().data or []
    df = pd.DataFrame(data)
    if not df.empty:
        df[COL_DATE] = pd.to_datetime(df[COL_DATE]).dt.date
        df[COL_AMOUNT] = pd.to_numeric(df[COL_AMOUNT], errors="coerce").fillna(0.0)
    return df

def insert_row(when: date, typ: str, category: str, merchant: str, desc: str, amount: float) -> bool:
    payload = {
        COL_DATE: when.isoformat(),
        COL_TYPE: typ,
        COL_CATEGORY: (category or "").strip() or "Nežinoma",
        COL_MERCHANT: (merchant or "").strip(),
        COL_DESC: (desc or "").strip(),
        COL_AMOUNT: float(amount)
    }
    try:
        res = supabase.table(TABLE).insert(payload).execute()
        if getattr(res, "error", None):
            st.warning(f"Įrašyti nepavyko: {res.error}")
            return False
        return bool(res.data)
    except Exception as e:
        st.warning(f"Įrašyti nepavyko: {e}")
        return False

def to_excel_bytes(df: pd.DataFrame, sheet_name="Duomenys") -> bytes:
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    bio.seek(0)
    return bio.read()

# =========================
# DIAGRAMOS
# =========================
def plot_monthly_trend(df: pd.DataFrame):
    if df.empty: return None
    agg = df.groupby(["tipas"], as_index=False)[COL_AMOUNT].sum()
    fig = go.Figure()
    for t in ["Pajamos","Išlaidos"]:
        val = agg.loc[agg["tipas"]==t, COL_AMOUNT].sum() if t in agg["tipas"].values else 0
        fig.add_trace(go.Bar(name=t, x=[1], y=[val]))
    fig.update_layout(title="Pajamos vs Išlaidos", yaxis_title=f"Suma ({CURRENCY})", xaxis=dict(showticklabels=False))
    return fig

# =========================
# ĮVEDIMO FORMA
# =========================
def entry_form():
    if not SHOW_ENTRY_FORM: return
    st.subheader("📝 Naujas įrašas")
    with st.form("entry_form"):
        dval = st.date_input("Data", value=date.today())
        tval = st.selectbox("Tipas", ["Išlaidos","Pajamos"])
        aval = st.number_input(f"Suma ({CURRENCY})", min_value=0.0, step=1.0, format="%.2f")
        cat = st.text_input("Kategorija", placeholder="pvz., Maistas / Alga", value="")
        merch = st.text_input("Prekybos centras", placeholder="nebūtina", value="")
        desc = st.text_input("Aprašymas", placeholder="nebūtina", value="")
        submitted = st.form_submit_button("💾 Išsaugoti")
        if submitted:
            ok = insert_row(dval, tval, cat, merch, desc, aval)
            if ok:
                st.success("Įrašyta.")
            else:
                st.warning("Įrašas neįrašytas.")

# =========================
# PAGRINDINĖ FUNKCIJA
# =========================
def main():
    if not login_ui(): 
        st.stop()
    
    logout_ui()
    
    st.title("💶 Asmeninis biudžetas")
    
    months = fetch_months()
    selected_month = months[-1] if months else None
    
    entry_form()
    
    if not selected_month:
        st.info("Pasirinkite mėnesį arba įveskite duomenis.")
        st.stop()
    
    df_month = fetch_month_df(selected_month)
    
    s_inc = float(df_month.loc[df_month[COL_TYPE]=="Pajamos", COL_AMOUNT].sum()) if not df_month.empty else 0
    s_exp = float(df_month.loc[df_month[COL_TYPE]=="Išlaidos", COL_AMOUNT].sum()) if not df_month.empty else 0
    s_bal = s_inc - s_exp
    
    st.subheader("📊 Suvestinė")
    st.metric("Pajamos", money(s_inc))
    st.metric("Išlaidos", money(s_exp))
    st.metric("Balansas", money(s_bal))
    
    fig_trend = plot_monthly_trend(df_month)
    if fig_trend:
        st.plotly_chart(fig_trend, use_container_width=True)
    
    if SHOW_EXPORT_XLSX and not df_month.empty:
        xlsb = to_excel_bytes(df_month, sheet_name=selected_month)
        st.download_button(
            "⬇️ Parsisiųsti Excel",
            data=xlsb,
            file_name=f"biudzetas_{selected_month}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

if __name__ == "__main__":
    main()
