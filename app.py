import os
import io
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from datetime import date
from typing import List, Optional, Dict
from supabase import create_client, Client

# =========================
# KONFIGŪRA – tavo 'public.biudzetas'
# =========================
TABLE            = "biudzetas"
COL_DATE         = "data"               # DATE
COL_TYPE         = "tipas"              # 'Pajamos' | 'Išlaidos'
COL_MERCHANT     = "prekybos_centras"   # TEXT (NOT NULL DEFAULT '')
COL_CATEGORY     = "kategorija"         # TEXT
COL_DESC         = "aprasymas"          # TEXT (NOT NULL DEFAULT '')
COL_AMOUNT       = "suma_eur"           # NUMERIC(12,2)

CURRENCY         = "€"
DEFAULT_MONTHS_TREND = 12               # trendo langas (mėn.)
SHOW_ENTRY_FORM  = True                 # rodyti įvedimo formą
SHOW_EXPORT_XLSX = True                 # leisti mėnesio lentelės eksportą į Excel

# =========================
# PUSLAPIO NUSTATYMAI + STILIUS
# =========================
st.set_page_config(
    page_title="Asmeninis biudžetas",
    page_icon="💶",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Tamsus neon UI
st.markdown(
    """
    <style>
    :root { --bg:#0f1226; --bg2:#15183a; --text:#e9e9f1; --muted:#a1a6d3; --vio:#8b5cf6; --green:#7affb2; }
    [data-testid="stAppViewContainer"]{ background:var(--bg); color:var(--text); }
    .block-container{ padding-top:.6rem !important; padding-bottom:.6rem !important; max-width:1200px !important; }
    h1,h2,h3{ color:var(--text); letter-spacing:.3px; }
    .topbar{ background:linear-gradient(135deg, rgba(139,92,246,.18), rgba(122,255,178,.08));
             border:1px solid rgba(139,92,246,.35); border-radius:12px; padding:.6rem .8rem;
             box-shadow:0 0 0 1px rgba(122,255,178,.15) inset, 0 8px 24px rgba(0,0,0,.35); }
    label,.stSelectbox label{ color:var(--muted) !important; margin-bottom:.2rem !important; }
    .stSelectbox div[data-baseweb="select"]>div{ background:var(--bg2) !important; border:1px solid rgba(139,92,246,.4) !important; border-radius:10px !important; }
    .stSelectbox div[data-baseweb="select"] span{ color:var(--text) !important; }
    hr{ border:none; height:1px; background:linear-gradient(to right, rgba(139,92,246,.35), rgba(122,255,178,.25)); margin:.6rem 0 .8rem; }
    .stAlert{ border-radius:10px !important; border:1px solid rgba(139,92,246,.35) !important; background:rgba(139,92,246,.08) !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Plotly tema
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
# Supabase inicializacija: palaiko flat ir [supabase] sekciją
# =========================
@st.cache_resource(show_spinner=False)
def get_supabase() -> Client:
    # 1) Plokšti raktai
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_ANON_KEY")
    # 2) Sekcija [supabase]
    if (not url or not key) and "supabase" in st.secrets and isinstance(st.secrets["supabase"], dict):
        url = url or st.secrets["supabase"].get("url") or st.secrets["supabase"].get("SUPABASE_URL")
        key = key or st.secrets["supabase"].get("anon_key") or st.secrets["supabase"].get("SUPABASE_ANON_KEY")
    # 3) ENV fallback (lokaliam dev)
    url = url or os.environ.get("SUPABASE_URL")
    key = key or os.environ.get("SUPABASE_ANON_KEY")

    if not url or not key:
        st.error(
            "❌ Supabase konfigūracija nerasta.\n\n"
            "Palaikomi formatai (pasirink vieną):\n"
            "A) Secrets plokščiai:\n"
            '   SUPABASE_URL = "https://xxxxx.supabase.co"\n'
            '   SUPABASE_ANON_KEY = "ey..."\n'
            "B) Secrets sekcija:\n"
            "   [supabase]\n"
            '   url = "https://xxxxx.supabase.co"\n'
            '   anon_key = "ey..."\n"
        )
        st.stop()
    try:
        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ Nepavyko inicializuoti Supabase kliento: {e}")
        st.stop()

supabase: Client = get_supabase()

# =========================
# LT mėnesiai, formatas, guard
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
        default_value = options[-1]  # naujausias
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
# Auth (email + password) su sesijos išlaikymu
# =========================
def hydrate_session_from_state():
    access = st.session_state.get("sb_access_token")
    refresh = st.session_state.get("sb_refresh_token")
    if access and refresh:
        try:
            supabase.auth.set_session(access_token=access, refresh_token=refresh)
        except Exception:
            pass

def current_session():
    return supabase.auth.get_session().session

def login_ui() -> bool:
    hydrate_session_from_state()
    if current_session():
        return True
    st.subheader("🔐 Prisijungimas")
    with st.form("login_form", border=False):
        email = st.text_input("El. paštas")
        pwd = st.text_input("Slaptažodis", type="password")
        submitted = st.form_submit_button("Prisijungti", use_container_width=True)
    if submitted:
        try:
            res = supabase.auth.sign_in_with_password({"email": email, "password": pwd})
            if res and res.session:
                st.session_state["sb_access_token"]  = res.session.access_token
                st.session_state["sb_refresh_token"] = res.session.refresh_token
                st.experimental_rerun()
            else:
                st.error("Neteisingi duomenys.")
        except Exception as e:
            st.error(f"Prisijungti nepavyko: {e}")
    return False

def logout_ui():
    if st.sidebar.button("Atsijungti", use_container_width=True):
        try: supabase.auth.sign_out()
        except Exception: pass
        for k in ("sb_access_token","sb_refresh_token"):
            if k in st.session_state: del st.session_state[k]
        st.experimental_rerun()

# =========================
# DB užklausos
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
    # Paskutiniai N mėnesių nuo šiandien
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
# Diagramos
# =========================
def plot_monthly_trend(df: pd.DataFrame) -> Optional[go.Figure]:
    if df.empty:
        return None
    agg = df.groupby(["ym", COL_TYPE], as_index=False)[COL_AMOUNT].sum()
    # užpildom trūkstamas kombinacijas
    all_ym = sorted(agg["ym"].unique().tolist())
    for t in ["Pajamos","Išlaidos"]:
        if not ((agg[COL_TYPE] == t).any()):
            missing = pd.DataFrame({"ym": all_ym, COL_TYPE: t, COL_AMOUNT: 0.0})
            agg = pd.concat([agg, missing], ignore_index=True)
    pivot = agg.pivot(index="ym", columns=COL_TYPE, values=COL_AMOUNT).fillna(0.0).reset_index()
    pivot["Balansas"] = pivot.get("Pajamos", 0.0) - pivot.get("Išlaidos", 0.0)

    fig = go.Figure()
    if "Pajamos" in pivot:
        fig.add_trace(go.Scatter(x=pivot["ym"], y=pivot["Pajamos"], mode="lines+markers", name="Pajamos", line=dict(width=2)))
    if "Išlaidos" in pivot:
        fig.add_trace(go.Scatter(x=pivot["ym"], y=pivot["Išlaidos"], mode="lines+markers", name="Išlaidos", line=dict(width=2)))
    fig.add_trace(go.Bar(x=pivot["ym"], y=pivot["Balansas"], name="Balansas (stulpeliai)", opacity=0.35))
    fig.update_layout(
        title="Mėnesinis trendas (Pajamos / Išlaidos / Balansas)",
        xaxis_title="Mėnuo",
        yaxis_title=f"Suma ({CURRENCY})",
        barmode="overlay",
        hovermode="x unified",
        margin=dict(l=10, r=10, t=60, b=10),
        height=420,
    )
    return fig

def plot_expense_pie(df_month: pd.DataFrame) -> Optional[go.Figure]:
    if df_month.empty:
        return None
    exp = df_month[df_month[COL_TYPE] == "Išlaidos"]
    if exp.empty:
        return None
    grp = exp.groupby(COL_CATEGORY, as_index=False)[COL_AMOUNT].sum().sort_values(COL_AMOUNT, ascending=False)
    fig = px.pie(grp, names=COL_CATEGORY, values=COL_AMOUNT, hole=0.5, title="Išlaidų struktūra pagal kategorijas")
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=60, b=10))
    return fig

def plot_category_bars(df_month: pd.DataFrame, tlabel: str) -> Optional[go.Figure]:
    if df_month.empty:
        return None
    sub = df_month[df_month[COL_TYPE] == tlabel]
    if sub.empty:
        return None
    grp = sub.groupby(COL_CATEGORY, as_index=False)[COL_AMOUNT].sum().sort_values(COL_AMOUNT, ascending=True).tail(12)
    fig = px.bar(
        grp, x=COL_AMOUNT, y=COL_CATEGORY, orientation="h",
        title=f"Top kategorijos: {tlabel}",
        labels={COL_AMOUNT: f"Suma ({CURRENCY})", COL_CATEGORY: "Kategorija"},
    )
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=60, b=10), yaxis=dict(autorange="reversed"))
    return fig

def plot_merchant_bar(df_month: pd.DataFrame) -> Optional[go.Figure]:
    if df_month.empty:
        return None
    exp = df_month[df_month[COL_TYPE] == "Išlaidos"].copy()
    if exp.empty:
        return None
    exp[COL_MERCHANT] = exp[COL_MERCHANT].fillna("").replace("", "Nežinomas")
    grp = exp.groupby(COL_MERCHANT, as_index=False)[COL_AMOUNT].sum().sort_values(COL_AMOUNT, ascending=False).head(12)
    fig = px.bar(
        grp, x=COL_AMOUNT, y=COL_MERCHANT, orientation="h",
        title="Top 12 prekybos centrų pagal išlaidas",
        labels={COL_AMOUNT: f"Išlaidos ({CURRENCY})", COL_MERCHANT: "Prekybos centras"},
    )
    fig.update_layout(height=480, margin=dict(l=10, r=10, t=60, b=10), yaxis=dict(autorange="reversed"))
    return fig

# =========================
# Įvedimas + Excel eksportas
# =========================
def insert_row(when: date, typ: str, category: str, merchant: str, desc: str, amount: float) -> bool:
    payload = {
        COL_DATE: when.isoformat(),
        COL_TYPE: typ,                                              # 'Pajamos' | 'Išlaidos'
        COL_CATEGORY: (category or "").strip() or "Nežinoma",
        COL_MERCHANT: (merchant or "").strip(),                     # laikom tuščią, NOT NULL default ''
        COL_DESC: (desc or "").strip(),                             # NOT NULL default ''
        COL_AMOUNT: float(amount),
    }
    try:
        res = supabase.table(TABLE).insert(payload).execute()
        # unikalaus rakto atvejis (biudzetas_natural_key_uk)
        if getattr(res, "error", None):
            msg = str(res.error)
            if "biudzetas_natural_key_uk" in msg or "duplicate key value" in msg.lower():
                st.info("Toks įrašas jau egzistuoja (unikalumo apribojimas).")
                return False
        return bool(res.data)
    except Exception as e:
        msg = str(e).lower()
        if "biudzetas_natural_key_uk" in msg or "duplicate key value" in msg:
            st.info("Toks įrašas jau egzistuoja (unikalumo apribojimas).")
            return False
        st.error(f"Įrašyti nepavyko: {e}")
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

def to_excel_bytes(df: pd.DataFrame, sheet_name="Duomenys") -> bytes:
    if df.empty:
        return b""
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    bio.seek(0)
    return bio.read()

# =========================
# Pagrindinis
# =========================
def main():
    # Auth
    if not login_ui():
        st.stop()
    logout_ui()

    st.title("💶 Asmeninis biudžetas")

    # Mėnesiai
    months = fetch_months()

    # Topbar
    with st.container():
        st.markdown('<div class="topbar">', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns([1.4, 0.9, 1, 1], gap="small")
        with c1:
            selected_month = render_month_select(months, "Mėnuo", "selected_month_key")
        with c2:
            trend_window = st.slider("Trendo mėn.", 6, 36, DEFAULT_MONTHS_TREND, 1)
        with c3:
            st.metric("Mėnesių sk.", len(months))
        with c4:
            st.metric("Pasirinktas", ym_label(selected_month) if selected_month else "—")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<hr/>", unsafe_allow_html=True)

    # Įvedimas
    entry_form()

    st.markdown("<hr/>", unsafe_allow_html=True)

    if not selected_month:
        st.info("Pasirinkite mėnesį.")
        st.stop()

    # Suvestinė
    df_month = fetch_month_df(selected_month)
    s_inc = float(df_month.loc[df_month[COL_TYPE] == "Pajamos", COL_AMOUNT].sum()) if not df_month.empty else 0.0
    s_exp = float(df_month.loc[df_month[COL_TYPE] == "Išlaidos", COL_AMOUNT].sum()) if not df_month.empty else 0.0
    s_bal = s_inc - s_exp

    st.subheader("📊 Suvestinė")
    k1, k2, k3 = st.columns(3)
    k1.metric("Pajamos",  money(s_inc))
    k2.metric("Išlaidos", money(s_exp))
    k3.metric("Balansas", money(s_bal))

    # Diagramos
    st.markdown("## 📈 Diagramos")

    df_trend = fetch_trend_df(trend_window)
    fig_trend = plot_monthly_trend(df_trend)
    if fig_trend is None:
        st.info("Trendo grafiko nėra – trūksta duomenų pasirinktame laikotarpyje.")
    else:
        st.plotly_chart(fig_trend, use_container_width=True, theme=None)

    cL, cR = st.columns([1.1, 1], gap="large")
    with cL:
        fig_pie = plot_expense_pie(df_month)
        if fig_pie is None:
            st.info("Šiame mėnesyje išlaidų nėra – skritulinė diagrama neturi ką rodyti.")
        else:
            st.plotly_chart(fig_pie, use_container_width=True, theme=None)
    with cR:
        tabs = st.tabs(["Išlaidos (Top)", "Pajamos (Top)"])
        with tabs[0]:
            fig_c_exp = plot_category_bars(df_month, "Išlaidos")
            if fig_c_exp is None:
                st.info("Nerasta išlaidų kategorijų.")
            else:
                st.plotly_chart(fig_c_exp, use_container_width=True, theme=None)
        with tabs[1]:
            fig_c_inc = plot_category_bars(df_month, "Pajamos")
            if fig_c_inc is None:
                st.info("Nerasta pajamų kategorijų.")
            else:
                st.plotly_chart(fig_c_inc, use_container_width=True, theme=None)

    st.markdown("### 🛒 Išlaidos pagal prekybos centrą")
    fig_merch = plot_merchant_bar(df_month)
    if fig_merch is None:
        st.info("Šiame mėnesyje nėra išlaidų pagal prekybos centrus.")
    else:
        st.plotly_chart(fig_merch, use_container_width=True, theme=None)

    # Lentelė + Excel
    st.markdown("## 🧾 Operacijų sąrašas")
    if df_month.empty:
        st.info("Šiam mėnesiui operacijų nėra.")
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
            try:
                xlsb = to_excel_bytes(df_show, sheet_name=selected_month)
                st.download_button(
                    "⬇️ Parsisiųsti Excel",
                    data=xlsb,
                    file_name=f"biudzetas_{selected_month}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            except Exception as e:
                st.warning(f"Excel eksportas nepavyko: {e}")

    # Debug expander (jei reikės)
    # with st.expander("🧪 Debug"):
    #     st.write({"selected_month": selected_month, "months": months[:6], "trend_window": trend_window})

if __name__ == "__main__":
    main()
