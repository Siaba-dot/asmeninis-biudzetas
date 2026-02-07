# =========================
# Pradžia – tas pats kodas, kuris tave prijungė
# =========================

import os
import io
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from datetime import date
from typing import List, Optional
from supabase import create_client, Client

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
# Puslapio nustatymai + stilius
# =========================
st.set_page_config(page_title="Asmeninis biudžetas", page_icon="💶", layout="wide", initial_sidebar_state="collapsed")

# Plotly dark neon tema
pio.templates["neon_dark"] = go.layout.Template(
    layout=dict(
        paper_bgcolor="#0f1226",
        plot_bgcolor="#0f1226",
        font=dict(color="#e9e9f1"),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        colorway=["#7affb2","#8b5cf6","#66d9ff","#ffd166","#ff5c7a","#f472b6","#a3e635","#f59e0b","#22d3ee"],
        xaxis=dict(gridcolor="rgba(255,255,255,0.08)", zerolinecolor="rgba(255,255,255,0.08)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.08)", zerolinecolor="rgba(255,255,255,0.08)"),
    )
)
pio.templates.default = "neon_dark"

# =========================
# Supabase klientas (paliekam tą patį)
# =========================
@st.cache_resource(show_spinner=False)
def get_supabase() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["anon_key"]
    return create_client(url, key)

supabase: Client = get_supabase()

# =========================
# LT mėnesiai, formatavimas
# =========================
LT_MONTHS = ["Sausis","Vasaris","Kovas","Balandis","Gegužė","Birželis","Liepa","Rugpjūtis","Rugsėjis","Spalis","Lapkritis","Gruodis"]

def ym_label(ym: str) -> str:
    y, m = ym.split("-")
    return f"{y} m. {LT_MONTHS[int(m)-1]}"

def money(v: float) -> str:
    return f"{v:,.2f} {CURRENCY}".replace(",", " ")

def ensure_session_value_in_options(session_key: str, options: List[str], default_value: Optional[str] = None) -> None:
    if not options:
        return
    if default_value is None:
        default_value = options[-1]
    if session_key not in st.session_state:
        st.session_state[session_key] = default_value
    if st.session_state[session_key] not in options:
        st.session_state[session_key] = default_value

def render_month_select(months: List[str], title="Mėnuo", state_key="selected_month_key") -> str:
    if not months:
        st.warning("Nėra galimų mėnesių.")
        return ""
    ensure_session_value_in_options(state_key, months, default_value=months[-1])
    idx = months.index(st.session_state[state_key])
    labels = {k: ym_label(k) for k in months}
    widget_key = state_key + "__widget"
    selected = st.selectbox(title, options=months, index=idx, format_func=lambda k: labels.get(k, k), key=widget_key)
    if selected != st.session_state[state_key]:
        st.session_state[state_key] = selected
    return selected

# =========================
# DB užklausos
# =========================
@st.cache_data(show_spinner=False, ttl=300)
def fetch_months() -> List[str]:
    data = supabase.table(TABLE).select(COL_DATE).order(COL_DATE, desc=False).execute().data or []
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

@st.cache_data(show_spinner=False, ttl=180)
def fetch_month_df(ym: str) -> pd.DataFrame:
    y, m = map(int, ym.split("-"))
    start = date(y, m, 1).isoformat()
    end = date(y + (m==12), (m % 12) + 1, 1).isoformat()
    data = supabase.table(TABLE).select(f"id,{COL_DATE},{COL_TYPE},{COL_MERCHANT},{COL_CATEGORY},{COL_DESC},{COL_AMOUNT}").gte(COL_DATE, start).lt(COL_DATE, end).order(COL_DATE, desc=True).execute().data or []
    df = pd.DataFrame(data)
    if not df.empty:
        df[COL_DATE] = pd.to_datetime(df[COL_DATE]).dt.date
        df[COL_AMOUNT] = pd.to_numeric(df[COL_AMOUNT], errors="coerce").fillna(0.0)
    return df

# =========================
# Įvedimas naujo įrašo
# =========================
def insert_row(when: date, typ: str, category: str, merchant: str, desc: str, amount: float) -> bool:
    payload = {
        COL_DATE: when.isoformat(),
        COL_TYPE: typ,
        COL_CATEGORY: (category or "").strip() or "Nežinoma",
        COL_MERCHANT: (merchant or "").strip(),  # gali būti tuščias
        COL_DESC: (desc or "").strip(),
        COL_AMOUNT: float(amount),
    }
    try:
        res = supabase.table(TABLE).insert(payload).execute()
        if getattr(res, "error", None):
            return False
        return bool(res.data)
    except Exception:
        return False

def entry_form():
    if not SHOW_ENTRY_FORM:
        return
    st.subheader("📝 Naujas įrašas")
    with st.form("entry_form"):
        dval = st.date_input("Data", value=date.today())
        tval = st.selectbox("Tipas", ["Išlaidos","Pajamos"])
        aval = st.number_input(f"Suma ({CURRENCY})", min_value=0.0, step=1.0, format="%.2f")
        cat = st.text_input("Kategorija", placeholder="pvz., Maistas / Alga")
        merch = st.text_input("Prekybos centras (nebūtina)", placeholder="nebūtina")
        desc = st.text_input("Aprašymas (nebūtina)", placeholder="nebūtina")
        submitted = st.form_submit_button("💾 Išsaugoti")
    if submitted:
        ok = insert_row(dval, tval, cat, merch, desc, aval)
        if ok:
            st.success("Įrašyta.")
            fetch_months.clear(); fetch_month_df.clear()
        else:
            st.warning("Įrašas neįrašytas.")

# =========================
# Diagrama Pajamos vs Išlaidos
# =========================
def plot_monthly_trend(df: pd.DataFrame):
    if df.empty:
        return None
    agg = df.groupby(["tipas", "data"], as_index=False)[COL_AMOUNT].sum()
    df_pivot = agg.pivot(index="data", columns="tipas", values=COL_AMOUNT).fillna(0)
    df_pivot["Balansas"] = df_pivot.get("Pajamos", 0) - df_pivot.get("Išlaidos", 0)
    fig = go.Figure()
    if "Pajamos" in df_pivot:
        fig.add_trace(go.Scatter(x=df_pivot.index, y=df_pivot["Pajamos"], mode="lines+markers", name="Pajamos"))
    if "Išlaidos" in df_pivot:
        fig.add_trace(go.Scatter(x=df_pivot.index, y=df_pivot["Išlaidos"], mode="lines+markers", name="Išlaidos"))
    fig.add_trace(go.Bar(x=df_pivot.index, y=df_pivot["Balansas"], name="Balansas", opacity=0.35))
    fig.update_layout(title="Pajamos vs Išlaidos", xaxis_title="Data", yaxis_title=f"Suma ({CURRENCY})", barmode="overlay", height=400)
    return fig

# =========================
# Excel eksportas
# =========================
def to_excel_bytes(df: pd.DataFrame, sheet_name="Duomenys") -> bytes:
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    bio.seek(0)
    return bio.read()

# =========================
# Pagrindinis
# =========================
def main():
    # Auth (paliekam tavo ankstesnį)
    st.subheader("💶 Asmeninis biudžetas")
    months = fetch_months()
    selected_month = render_month_select(months)
    entry_form()
    if not selected_month:
        st.stop()
    df_month = fetch_month_df(selected_month)
    s_inc = float(df_month.loc[df_month[COL_TYPE]=="Pajamos", COL_AMOUNT].sum()) if not df_month.empty else 0
    s_exp = float(df_month.loc[df_month[COL_TYPE]=="Išlaidos", COL_AMOUNT].sum()) if not df_month.empty else 0
    s_bal = s_inc - s_exp
    st.metric("Pajamos", money(s_inc))
    st.metric("Išlaidos", money(s_exp))
    st.metric("Balansas", money(s_bal))
    fig_trend = plot_monthly_trend(df_month)
    if fig_trend:
        st.plotly_chart(fig_trend, use_container_width=True)
    if SHOW_EXPORT_XLSX and not df_month.empty:
        xlsb = to_excel_bytes(df_month, sheet_name=selected_month)
        st.download_button("⬇️ Parsisiųsti Excel", data=xlsb, file_name=f"biudzetas_{selected_month}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

if __name__ == "__main__":
    main()

