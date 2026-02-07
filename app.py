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

# =========================
# KONFIGŪRACIJA
# =========================
TABLE            = "biudzetas"
COL_DATE         = "data"
COL_TYPE         = "tipas"
COL_MERCHANT     = "prekybos_centras"
COL_CATEGORY     = "kategorija"
COL_DESC         = "aprasymas"
COL_AMOUNT       = "suma_eur"

CURRENCY         = "€"
DEFAULT_MONTHS_TREND = 12
SHOW_ENTRY_FORM  = True
SHOW_EXPORT_XLSX = True

# =========================
# Streamlit puslapio nustatymai
# =========================
st.set_page_config(
    page_title="Asmeninis biudžetas",
    page_icon="💶",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Tamsus stilius
st.markdown("""
<style>
:root { --bg:#0f1226; --bg2:#15183a; --text:#e9e9f1; --muted:#a1a6d3; --vio:#8b5cf6; --green:#7affb2; }
[data-testid="stAppViewContainer"]{ background:var(--bg); color:var(--text); }
.block-container{ padding-top:.6rem !important; padding-bottom:.6rem !important; max-width:1200px !important; }
h1,h2,h3{ color:var(--text); letter-spacing:.3px; }
.topbar{ background:linear-gradient(135deg, rgba(139,92,246,.18), rgba(122,255,178,.08));
         border:1px solid rgba(139,92,246,.35); border-radius:12px; padding:.6rem .8rem;
         box-shadow:0 0 0 1 rgba(122,255,178,.15) inset, 0 8px 24px rgba(0,0,0,.35); }
label,.stSelectbox label{ color:var(--muted) !important; margin-bottom:.2rem !important; }
.stSelectbox div[data-baseweb="select"]>div{ background:var(--bg2) !important; border:1px solid rgba(139,92,246,.4) !important; border-radius:10px !important; }
.stSelectbox div[data-baseweb="select"] span{ color:var(--text) !important; }
hr{ border:none; height:1px; background:linear-gradient(to right, rgba(139,92,246,.35), rgba(122,255,178,.25)); margin:.6rem 0 .8rem; }
.stAlert{ border-radius:10px !important; border:1px solid rgba(139,92,246,.35) !important; background:rgba(139,92,246,.08) !important; }
</style>
""", unsafe_allow_html=True)

# Plotly tamsus neon template
pio.templates["neon_dark"] = go.layout.Template(
    layout=dict(
        paper_bgcolor="#0f1226",
        plot_bgcolor="#0f1226",
        font=dict(color="#e9e9f1", family="Inter, Segoe UI, system-ui"),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        colorway=["#7affb2","#8b5cf6","#66d9ff","#ffd166","#ff5c7a","#f472b6","#a3e635","#f59e0b","#22d3ee"],
        xaxis=dict(gridcolor="rgba(255,255,255,0.08)", zerolinecolor="rgba(255,255,255,0.08)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.08)", zerolinecolor="rgba(255,255,255,0.08)"),
    )
)
pio.templates.default = "neon_dark"

# =========================
# Supabase inicializacija
# =========================
@st.cache_resource(show_spinner=False)
def get_supabase() -> Client:
    if "supabase" not in st.secrets or not isinstance(st.secrets["supabase"], dict):
        st.error(
            "❌ Secrets nerasta sekcija [supabase].\n\n"
            "Pridėkite į Secrets (TOML):\n"
            "[supabase]\n"
            'url = "https://<tavo>.supabase.co"\n'
            'anon_key = "ey..."\n'
        )
        st.stop()

    url = st.secrets["supabase"].get("url")
    key = st.secrets["supabase"].get("anon_key")

    if not url or not key:
        st.error("❌ Trūksta [supabase] reikšmių.")
        st.stop()

    try:
        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ Nepavyko inicializuoti Supabase kliento: {e}")
        st.stop()

supabase: Client = get_supabase()

# =========================
# Lietuviški mėnesiai ir formatavimas
# =========================
LT_MONTHS = ["Sausis","Vasaris","Kovas","Balandis","Gegužė","Birželis",
             "Liepa","Rugpjūtis","Rugsėjis","Spalis","Lapkritis","Gruodis"]

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
# Įrašų funkcijos
# =========================
def insert_row(d: date, typ: str, cat: str, merch: str, desc: str, amount: float) -> bool:
    payload = {
        "data": d.isoformat(),
        "tipas": typ.strip(),
        "kategorija": (cat or "").strip() or "Nežinoma",
        "prekybos_centras": (merch or "").strip(),
        "aprasymas": (desc or "").strip(),
        "suma_eur": float(amount)
    }
    try:
        res = supabase.table(TABLE).insert(payload).execute()
        if getattr(res, "error", None):
            msg = str(res.error).lower()
            if "duplicate key" in msg:
                st.info("Toks įrašas jau egzistuoja (unikalumas).")
            else:
                st.error(f"Įrašyti nepavyko: {res.error}")
            return False
        return True
    except Exception as e:
        st.error(f"Nepavyko įrašyti: {e}")
        return False

def entry_form():
    if not SHOW_ENTRY_FORM:
        return
    st.subheader("📝 Naujas įrašas")
    with st.form("entry_form", border=False):
        c1, c2, c3 = st.columns([1.2, 1, 1])
        with c1:
            dval = st.date_input("Data", value=date.today())
        with c2:
            tval = st.selectbox("Tipas", ["Išlaidos","Pajamos"])
        with c3:
            aval = st.number_input(f"Suma ({CURRENCY})", min_value=0.0, step=1.0, format="%.2f")
        c4, c5 = st.columns([1, 1.6])
        with c4:
            cat = st.text_input("Kategorija", placeholder="pvz., Maistas / Alga", value="")
        with c5:
            merch = st.text_input("Prekybos centras", placeholder="nebūtina", value="")
        desc = st.text_input("Aprašymas", placeholder="nebūtina", value="")
        submitted = st.form_submit_button("💾 Išsaugoti", use_container_width=True)

    if submitted:
        ok = insert_row(dval, tval, cat, merch, desc, aval)
        if ok:
            st.success("Įrašyta.")
            fetch_months.clear(); fetch_month_df.clear(); fetch_trend_df.clear()
        else:
            st.warning("Įrašas neįrašytas.")

# =========================
# Duomenų iš DB gavimas
# =========================
@st.cache_data(show_spinner=False, ttl=300)
def fetch_months() -> List[str]:
    data = (
        supabase.table(TABLE)
        .select(COL_DATE)
        .order(COL_DATE, desc=False)
        .limit(100000)
        .execute()
        .data or []
    )
    seen, months = set(), []
    for row in data:
        dval = row.get(COL_DATE)
        if not dval:
            continue
        try:
            d = pd.to_datetime(dval).to_pydatetime()
        except Exception:
            continue
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
    data = (
        supabase.table(TABLE)
        .select(f"id,{COL_DATE},{COL_TYPE},{COL_MERCHANT},{COL_CATEGORY},{COL_DESC},{COL_AMOUNT}")
        .gte(COL_DATE, start).lt(COL_DATE, end)
        .order(COL_DATE, desc=True)
        .limit(50000)
        .execute()
        .data or []
    )
    df = pd.DataFrame(data)
    if not df.empty:
        df[COL_DATE] = pd.to_datetime(df[COL_DATE]).dt.date
        df[COL_AMOUNT] = pd.to_numeric(df[COL_AMOUNT], errors="coerce").fillna(0.0)
    return df

@st.cache_data(show_spinner=False, ttl=300)
def fetch_trend_df(last_n_months: int = DEFAULT_MONTHS_TREND) -> pd.DataFrame:
    today = date.today()
    y, m = today.year, today.month
    start_y = y
    start_m = m - (last_n_months - 1)
    while start_m <= 0:
        start_y -= 1
        start_m += 12
    start = date(start_y, start_m, 1).isoformat()
    end = date(y + (m==12), (m % 12) + 1, 1).isoformat()
    data = (
        supabase.table(TABLE)
        .select(f"{COL_DATE},{COL_TYPE},{COL_AMOUNT}")
        .gte(COL_DATE, start).lt(COL_DATE, end)
        .order(COL_DATE, desc=False)
        .limit(100000)
        .execute()
        .data or []
    )
    df = pd.DataFrame(data)
    if df.empty:
        return df
    df[COL_DATE] = pd.to_datetime(df[COL_DATE])
    df[COL_AMOUNT] = pd.to_numeric(df[COL_AMOUNT], errors="coerce").fillna(0.0)
    df["ym"] = df[COL_DATE].dt.to_period("M").astype(str)
    return df

# =========================
# Grafikai
# =========================
def plot_monthly_trend(df: pd.DataFrame):
    if df.empty:
        return None
    agg = df.groupby(["ym", COL_TYPE], as_index=False)[COL_AMOUNT].sum()
    all_ym = sorted(agg["ym"].unique().tolist())

    for t in ["Pajamos","Išlaidos"]:
        if not ((agg[COL_TYPE] == t).any()):
            missing = pd.DataFrame({"ym": all_ym, COL_TYPE: t, COL_AMOUNT: 0.0})
            agg = pd.concat([agg, missing], ignore_index=True)

    pivot = agg.pivot(index="ym", columns=COL_TYPE, values=COL_AMOUNT).fillna(0.0).reset_index()
    pivot["Balansas"] = pivot.get("Pajamos", 0.0) - pivot.get("Išlaidos", 0.0)

    fig = go.Figure()
    if "Pajamos" in pivot:
        fig.add_trace(go.Scatter(x=pivot["ym"], y=pivot["Pajamos"], mode="lines+markers", name="Pajamos"))
    if "Išlaidos" in pivot:
        fig.add_trace(go.Scatter(x=pivot["ym"], y=pivot["Išlaidos"], mode="lines+markers", name="Išlaidos"))
    fig.add_trace(go.Bar(x=pivot["ym"], y=pivot["Balansas"], name="Balansas", opacity=0.35))
    fig.update_layout(title="Mėnesinis trendas", xaxis_title="Mėnuo", yaxis_title=f"Suma ({CURRENCY})",
                      barmode="overlay", hovermode="x unified", margin=dict(l=10, r=10, t=60, b=10), height=420)
    return fig

def to_excel_bytes(df: pd.DataFrame, sheet_name="Duomenys") -> bytes:
    if df.empty:
        return b""
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    bio.seek(0)
    return bio.read()

# =========================
# Pagrindinis puslapis
# =========================
def main():
    st.title("💶 Asmeninis biudžetas")

    entry_form()

    months = fetch_months()
    if not months:
        st.info("Duomenų dar nėra.")
        st.stop()

    selected_month = render_month_select(months, "Mėnuo", "selected_month_key")

    df_month = fetch_month_df(selected_month)
    s_inc = float(df_month.loc[df_month[COL_TYPE] == "Pajamos", COL_AMOUNT].sum()) if not df_month.empty else 0.0
    s_exp = float(df_month.loc[df_month[COL_TYPE] == "Išlaidos", COL_AMOUNT].sum()) if not df_month.empty else 0.0
    s_bal = s_inc - s_exp

    st.subheader("📊 Suvestinė")
    k1, k2, k3 = st.columns(3)
    k1.metric("Pajamos",  money(s_inc))
    k2.metric("Išlaidos", money(s_exp))
    k3.metric("Balansas", money(s_bal))

    st.markdown("## 📈 Mėnesinis trendas")
    df_trend = fetch_trend_df(DEFAULT_MONTHS_TREND)
    fig_trend = plot_monthly_trend(df_trend)
    if fig_trend is None:
        st.info("Grafiko duomenų nėra.")
    else:
        st.plotly_chart(fig_trend, use_container_width=True, theme=None)

    st.markdown("## 🧾 Operacijų sąrašas")
    if df_month.empty:
        st.info("Šiam mėnesiui įrašų nėra.")
    else:
        df_show = df_month.rename(columns={
            COL_DATE: "Data",
            COL_TYPE: "Tipas",
            COL_CATEGORY: "Kategorija",
            COL_MERCHANT: "Prekybos centras",
            COL_DESC: "Aprašymas",
            COL_AMOUNT: f"Suma ({CURRENCY})"
        })
        st.dataframe(df_show, use_container_width=True, hide_index=True)
        if SHOW_EXPORT_XLSX:
            xlsb = to_excel_bytes(df_show, sheet_name=selected_month)
            st.download_button("⬇️ Parsisiųsti Excel", data=xlsb,
                               file_name=f"biudzetas_{selected_month}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               use_container_width=True)

if __name__ == "__main__":
    main()
