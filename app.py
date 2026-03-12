import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, timedelta
from supabase import create_client
from supabase.client import Client
import io

st.set_page_config(page_title="💶 Asmeninis biudžetas", layout="wide")

# ======================================================
# Supabase
# ======================================================
@st.cache_resource(show_spinner=False)
def get_supabase() -> Client:
    return create_client(
        st.secrets["supabase"]["url"],
        st.secrets["supabase"]["anon_key"]
    )

supabase = get_supabase()
TABLE = "biudzetas"
CURRENCY = "€"

# ======================================================
# AUTH (Supabase email/password + signup + magic link)
# ======================================================
def _store_session(session) -> None:
    if session is None:
        st.session_state.pop("sb_session", None)
        return
    st.session_state["sb_session"] = {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
    }

def _restore_session() -> bool:
    s = st.session_state.get("sb_session")
    if not s:
        return False
    try:
        supabase.auth.set_session(s["access_token"], s["refresh_token"])
        supabase.auth.get_user()
        return True
    except Exception:
        st.session_state.pop("sb_session", None)
        return False

def login(email: str, password: str):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        _store_session(res.session)
        return True, ""
    except Exception as e:
        return False, str(e)

def signup(email: str, password: str):
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        try:
            if getattr(res, "session", None) is not None:
                _store_session(res.session)
        except Exception:
            pass
        return True, ""
    except Exception as e:
        return False, str(e)

def send_magic_link(email: str):
    try:
        supabase.auth.sign_in_with_otp({"email": email, "shouldCreateUser": True})
        return True, ""
    except Exception as e:
        return False, str(e)

def logout():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    st.session_state.clear()
    st.rerun()

_restore_session()

if "authenticated" not in st.session_state:
    try:
        u = supabase.auth.get_user()
        if u and getattr(u, "user", None) and getattr(u.user, "email", None):
            st.session_state["authenticated"] = True
            st.session_state["email"] = u.user.email
    except Exception:
        pass

if "authenticated" not in st.session_state:
    st.title("🔐 Prisijungimas")

    tabs = st.tabs(["El. paštas + slaptažodis", "Magic link"])

    with tabs[0]:
        email = st.text_input("El. paštas", key="login_email")
        password = st.text_input("Slaptažodis", type="password", key="login_pwd")

        c1, c2 = st.columns(2)

        if c1.button("Prisijungti"):
            ok, err = login(email.strip(), password)
            if ok:
                st.session_state["authenticated"] = True
                st.session_state["email"] = email.strip()
                st.rerun()
            else:
                st.error("❌ Neteisingi duomenys arba nepatvirtintas el. paštas.")
                st.caption(f"Techninė klaida: {err}")

        if c2.button("Sukurti paskyrą"):
            ok, err = signup(email.strip(), password)
            if ok:
                st.success("✅ Paskyra sukurta. Jei įjungtas Confirm email — patvirtink laiške prieš pirmą prisijungimą.")
                st.info("Jei laiškas neateina, pabandyk 'Magic link' arba testui laikinai išjunk Confirm email.")
            else:
                st.error("❌ Nepavyko sukurti paskyros.")
                st.caption(f"Techninė klaida: {err}")

    with tabs[1]:
        email2 = st.text_input("El. paštas (atsiųsime vienkartinę nuorodą)", key="magic_email")
        if st.button("Siųsti magic link"):
            ok, err = send_magic_link(email2.strip())
            if ok:
                st.success("✅ Nuoroda išsiųsta. Patikrink el. paštą (ir Spam).")
            else:
                st.error("❌ Nepavyko išsiųsti.")
                st.caption(f"Techninė klaida: {err}")

    st.stop()

USER_EMAIL = st.session_state["email"]
st.sidebar.success(f"👤 {USER_EMAIL}")
if st.sidebar.button("🚪 Atsijungti"):
    logout()

# ======================================================
# HELPERS
# ======================================================
def money(x: float) -> str:
    try:
        return f"{float(x):,.2f} {CURRENCY}".replace(",", " ")
    except Exception:
        return f"0.00 {CURRENCY}"

def safe_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default

def add_month_start(dt: pd.Timestamp, n: int) -> pd.Timestamp:
    return (pd.Timestamp(dt).to_period("M") + n).to_timestamp()

# ======================================================
# KPI UI
# ======================================================
def render_kpi_card(title: str, value: str, subtitle: str = "", tone: str = "neutral"):
    st.markdown(
        f"""
        <div class="kpi-card {tone}">
            <div class="kpi-title">{title}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

st.markdown(
    """
    <style>
    .kpi-card {
        border-radius: 20px;
        padding: 20px 22px;
        min-height: 145px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.10);
        border: 1px solid rgba(255,255,255,0.08);
        background: linear-gradient(145deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
        backdrop-filter: blur(6px);
        transition: all 0.2s ease-in-out;
        margin-bottom: 10px;
    }

    .kpi-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 14px 34px rgba(0,0,0,0.14);
    }

    .kpi-title {
        font-size: 0.95rem;
        font-weight: 600;
        opacity: 0.85;
        margin-bottom: 14px;
        letter-spacing: 0.2px;
    }

    .kpi-value {
        font-size: 2rem;
        font-weight: 800;
        line-height: 1.1;
        margin-bottom: 10px;
    }

    .kpi-subtitle {
        font-size: 0.88rem;
        opacity: 0.78;
        line-height: 1.35;
    }

    .kpi-card.positive {
        background: linear-gradient(135deg, rgba(22,163,74,0.22), rgba(22,163,74,0.08));
        border: 1px solid rgba(34,197,94,0.25);
    }

    .kpi-card.negative {
        background: linear-gradient(135deg, rgba(220,38,38,0.22), rgba(220,38,38,0.08));
        border: 1px solid rgba(239,68,68,0.25);
    }

    .kpi-card.neutral {
        background: linear-gradient(135deg, rgba(59,130,246,0.18), rgba(99,102,241,0.08));
        border: 1px solid rgba(96,165,250,0.22);
    }

    .kpi-card.warning {
        background: linear-gradient(135deg, rgba(245,158,11,0.22), rgba(245,158,11,0.08));
        border: 1px solid rgba(251,191,36,0.25);
    }

    div[data-testid="stHorizontalBlock"] > div:has(.kpi-card) {
        padding-top: 2px;
    }

    .scenario-box {
        border-radius: 18px;
        padding: 14px 16px;
        margin-bottom: 10px;
        border: 1px solid rgba(255,255,255,0.08);
        background: linear-gradient(145deg, rgba(255,255,255,0.04), rgba(255,255,255,0.02));
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ======================================================
# DATA
# ======================================================
@st.cache_data(ttl=60, show_spinner=False)
def fetch_user_data(email: str) -> pd.DataFrame:
    data = (
        supabase.table(TABLE)
        .select("*")
        .eq("user_email", email)
        .order("data", desc=False)
        .execute()
        .data
        or []
    )
    df = pd.DataFrame(data)
    if df.empty:
        return df

    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df = df.dropna(subset=["data"])
    df["suma_eur"] = pd.to_numeric(df["suma_eur"], errors="coerce").fillna(0.0)

    for col in ["kategorija", "prekybos_centras", "aprasymas", "tipas"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)

    df["year"] = df["data"].dt.year
    df["month"] = df["data"].dt.to_period("M").astype(str)
    df["month_ts"] = df["data"].dt.to_period("M").dt.to_timestamp()
    return df

def insert_row(d, tipas, kategorija, prekyba, aprasymas, suma):
    supabase.table(TABLE).insert({
        "user_email": USER_EMAIL,
        "data": d.isoformat(),
        "tipas": tipas,
        "kategorija": (kategorija or "").strip() or "Nežinoma",
        "prekybos_centras": (prekyba or "").strip(),
        "aprasymas": (aprasymas or "").strip(),
        "suma_eur": float(suma)
    }).execute()
    st.cache_data.clear()
    st.rerun()

def delete_row(row_id):
    supabase.table(TABLE).delete().eq("id", row_id).execute()
    st.cache_data.clear()
    st.rerun()

def update_row(row_id, d, tipas, kategorija, prekyba, aprasymas, suma):
    supabase.table(TABLE).update({
        "data": d.isoformat(),
        "tipas": tipas,
        "kategorija": (kategorija or "").strip() or "Nežinoma",
        "prekybos_centras": (prekyba or "").strip(),
        "aprasymas": (aprasymas or "").strip(),
        "suma_eur": float(suma),
    }).eq("id", row_id).execute()
    st.cache_data.clear()
    st.rerun()

# ======================================================
# UI: Header + entry
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
            suma = st.number_input(f"Suma ({CURRENCY})", min_value=0.0, step=1.0, format="%.2f")

        c4, c5 = st.columns(2)
        with c4:
            kategorija = st.text_input("Kategorija", placeholder="pvz. Maistas / Alga")
        with c5:
            prekyba = st.text_input("Prekybos vieta (nebūtina)", placeholder="pvz. Maxima / Degalinė")

        aprasymas = st.text_input("Aprašymas (nebūtina)", placeholder="pvz. pietūs / nuoma / priedas")

        if st.form_submit_button("💾 Išsaugoti"):
            insert_row(d, tipas, kategorija, prekyba, aprasymas, suma)

# ======================================================
# LOAD
# ======================================================
df = fetch_user_data(USER_EMAIL)
if df.empty:
    st.info("Kol kas nėra įrašų. Įvesk pirmą operaciją ir viskas pradės gyventi.")
    st.stop()

# ======================================================
# FILTERS
# ======================================================
st.subheader("🔎 Filtrai")

years = ["Visi"] + sorted(df["year"].unique().tolist())
months = ["Visi"] + sorted(df["month"].unique().tolist())

c1, c2, c3, c4 = st.columns([1, 1.2, 1, 1.2])
with c1:
    year_filter = st.selectbox("Metai", years)
with c2:
    month_filter = st.selectbox("Mėnuo", months)
with c3:
    type_filter = st.selectbox("Tipas", ["Visi", "Pajamos", "Išlaidos"])
with c4:
    cat_filter = st.text_input("Kategorija (paieška)", placeholder="pvz. maist")

df_f = df.copy()
if year_filter != "Visi":
    df_f = df_f[df_f["year"] == year_filter]
if month_filter != "Visi":
    df_f = df_f[df_f["month"] == month_filter]
if type_filter != "Visi":
    df_f = df_f[df_f["tipas"] == type_filter]
if cat_filter.strip():
    df_f = df_f[df_f["kategorija"].str.contains(cat_filter.strip(), case=False, na=False)]

# ======================================================
# KPI
# ======================================================
income = df_f[df_f["tipas"] == "Pajamos"]["suma_eur"].sum()
expense = df_f[df_f["tipas"] == "Išlaidos"]["suma_eur"].sum()
balance = income - expense

st.subheader("📊 KPI")

savings_rate = None
if income > 0:
    savings_rate = (income - expense) / income

exp_daily = df_f[df_f["tipas"] == "Išlaidos"].copy()

days_available = None
avg_daily_expense = None
end_date = None

df_time = df.copy()
if year_filter != "Visi":
    df_time = df_time[df_time["year"] == year_filter]
if month_filter != "Visi":
    df_time = df_time[df_time["month"] == month_filter]

calendar_days = None
min_day = None
max_day = None

if month_filter != "Visi":
    p = pd.Period(month_filter, freq="M")
    min_day = p.start_time.date()
    if not df_time.empty:
        max_day = df_time["data"].max().date()
    else:
        max_day = min_day
    calendar_days = (max_day - min_day).days + 1

elif year_filter != "Visi":
    y = int(year_filter)
    min_day = date(y, 1, 1)
    max_day = date(y, 12, 31)
    calendar_days = (max_day - min_day).days + 1

else:
    if not df_time.empty:
        min_day = df_time["data"].min().date()
        max_day = df_time["data"].max().date()
        calendar_days = (max_day - min_day).days + 1

if (calendar_days is not None) and (calendar_days > 0) and (not exp_daily.empty):
    avg_daily_expense = exp_daily["suma_eur"].sum() / calendar_days

    if avg_daily_expense > 0 and balance > 0:
        days_available = balance / avg_daily_expense
        end_date = date.today() + timedelta(days=int(days_available))

income_tone = "positive" if income > 0 else "neutral"
expense_tone = "negative" if expense > 0 else "neutral"
balance_tone = "positive" if balance > 0 else ("negative" if balance < 0 else "neutral")

if savings_rate is None:
    savings_tone = "neutral"
elif savings_rate < 0:
    savings_tone = "negative"
elif savings_rate < 0.15:
    savings_tone = "warning"
else:
    savings_tone = "positive"

c1, c2, c3 = st.columns(3)
with c1:
    render_kpi_card("💰 Pajamos", money(income), "Visos pajamos pagal pasirinktą filtrą", income_tone)
with c2:
    render_kpi_card("💸 Išlaidos", money(expense), "Visos išlaidos pagal pasirinktą filtrą", expense_tone)
with c3:
    render_kpi_card("📈 Balansas", money(balance), "Pajamos minus išlaidos", balance_tone)

c4, c5, c6 = st.columns(3)
with c4:
    render_kpi_card(
        "🎯 Sutaupymo norma",
        f"{(savings_rate*100):.1f} %" if savings_rate is not None else "—",
        "Kiek pajamų lieka po išlaidų",
        savings_tone
    )

with c5:
    if days_available is not None and end_date is not None:
        render_kpi_card(
            "🛟 Finansinė pagalvė",
            f"{days_available:.0f} d.",
            f"iki {end_date.isoformat()} • ~{money(avg_daily_expense)}/d.",
            "positive" if days_available >= 30 else "warning"
        )
    else:
        render_kpi_card(
            "🛟 Finansinė pagalvė",
            "—",
            "Nepakanka duomenų skaičiavimui",
            "neutral"
        )

with c6:
    render_kpi_card(
        "📅 Vid. dienos išlaidos",
        money(avg_daily_expense) if avg_daily_expense is not None else "—",
        "Skaičiuojama pagal pasirinktą laikotarpį",
        "warning" if avg_daily_expense is not None else "neutral"
    )

# ======================================================
# SMART INSIGHTS (NO AI)
# ======================================================
st.subheader("🔍 Smart insight: kur bėga pinigai (be DI)")

with st.expander("⚙️ Insight nustatymai", expanded=False):
    small_cap = st.slider("„Smulkios išlaidos“ riba (€)", 1, 50, 10, 1)
    spike_pct = st.slider("„Šuolio“ riba vs praeitas mėnuo (%)", 5, 80, 20, 5)
    lookback_months = st.slider("Vidurkio laikotarpis (mėn.)", 2, 12, 6, 1)

current_month = month_filter if month_filter != "Visi" else sorted(df["month"].unique().tolist())[-1]

cur = df[df["month"] == current_month].copy()
cur_exp = cur[cur["tipas"] == "Išlaidos"].copy()
cur_inc = cur[cur["tipas"] == "Pajamos"].copy()

cur_period = pd.Period(current_month, freq="M")
prev_month = str(cur_period - 1)
prev = df[df["month"] == prev_month].copy()
prev_exp = prev[prev["tipas"] == "Išlaidos"].copy()

insights = []

if not cur_exp.empty:
    top_cat = (
        cur_exp.groupby("kategorija")["suma_eur"].sum()
        .sort_values(ascending=False)
        .head(5)
    )
    top_cat_str = ", ".join([f"{k}: {money(v)}" for k, v in top_cat.items()])
    insights.append(f"**Top kategorijos ({current_month})**: {top_cat_str}")

if not cur_exp.empty:
    small = cur_exp[cur_exp["suma_eur"] <= float(small_cap)]
    if not small.empty:
        insights.append(
            f"**Smulkios išlaidos (≤ {small_cap} €)**: {int(len(small))} kartų, suma **{money(small['suma_eur'].sum())}**."
        )

if (not cur_exp.empty) and (not prev_exp.empty):
    cur_cat = cur_exp.groupby("kategorija")["suma_eur"].sum()
    prev_cat = prev_exp.groupby("kategorija")["suma_eur"].sum()
    joined = pd.concat([cur_cat, prev_cat], axis=1)
    joined.columns = ["cur", "prev"]
    joined = joined.fillna(0.0)

    joined2 = joined[joined["prev"] > 0].copy()
    if not joined2.empty:
        joined2["pct"] = (joined2["cur"] - joined2["prev"]) / joined2["prev"]
        spikes = joined2[joined2["pct"] >= (spike_pct / 100.0)].sort_values("pct", ascending=False).head(5)
        if not spikes.empty:
            parts = []
            for k, row in spikes.iterrows():
                parts.append(f"{k}: {money(row['cur'])} (buvo {money(row['prev'])}, +{row['pct']*100:.0f}%)")
            insights.append(f"**Šuoliai vs {prev_month}**: " + "; ".join(parts))

if not cur_exp.empty and "prekybos_centras" in cur_exp.columns:
    cur_exp["prekybos_centras"] = cur_exp["prekybos_centras"].replace("", "Nežinoma")
    by_merch = cur_exp.groupby("prekybos_centras").agg(cnt=("suma_eur", "size"), total=("suma_eur", "sum"))
    repeat = by_merch[by_merch["cnt"] >= 3].sort_values("total", ascending=False).head(5)
    if not repeat.empty:
        parts = [f"{idx}: {int(r.cnt)} kart., {money(r.total)}" for idx, r in repeat.iterrows()]
        insights.append("**Pasikartojančios vietos (3+ kartai)**: " + "; ".join(parts))

cur_income = cur_inc["suma_eur"].sum()
cur_expense = cur_exp["suma_eur"].sum()
if cur_income > 0:
    rate = (cur_income - cur_expense) / cur_income
    if rate < 0:
        insights.append(f"⚠️ **{current_month}**: išlaidos viršija pajamas (sutaupymo norma {rate*100:.1f}%).")
    elif rate < 0.15:
        insights.append(f"⚠️ **{current_month}**: sutaupymo norma žema ({rate*100:.1f}%).")
    else:
        insights.append(f"✅ **{current_month}**: sutaupymo norma {rate*100:.1f}% – kryptis gera.")

all_months = sorted(df["month"].unique().tolist())
cur_idx = all_months.index(current_month) if current_month in all_months else None
if cur_idx is not None:
    start_idx = max(0, cur_idx - lookback_months)
    lookback_list = all_months[start_idx:cur_idx]
    if lookback_list:
        base = df[(df["month"].isin(lookback_list)) & (df["tipas"] == "Išlaidos")]["suma_eur"].sum() / len(lookback_list)
        cur_total = df[(df["month"] == current_month) & (df["tipas"] == "Išlaidos")]["suma_eur"].sum()
        if base > 0:
            diff = (cur_total - base) / base
            if diff >= (spike_pct / 100.0):
                insights.append(
                    f"⚠️ **Bendrai išlaidos** {current_month}: {money(cur_total)}. "
                    f"Tai ~{diff*100:.0f}% daugiau nei tavo {len(lookback_list)} mėn. vidurkis ({money(base)})."
                )

if insights:
    for s in insights:
        st.markdown(f"- {s}")
else:
    st.info("Dar per mažai duomenų insightams.")

# ======================================================
# TABLE: edit + delete
# ======================================================
st.subheader("📋 Įrašai (redagavimas / trynimas)")

if df_f.empty:
    st.info("Pagal pasirinktus filtrus įrašų nėra.")
else:
    with st.container(height=420, border=True):
        for _, r in df_f.sort_values("data", ascending=False).iterrows():
            title = f"{r['data'].date()} | {r['tipas']} | {r['kategorija']} | {money(r['suma_eur'])}"
            with st.expander(title, expanded=False):
                colA, colB, colC, colD = st.columns([1.1, 1.1, 1.2, 1.2])

                with colA:
                    new_d = st.date_input("Data", value=r["data"].date(), key=f"d_{r['id']}")
                with colB:
                    new_t = st.selectbox(
                        "Tipas",
                        ["Pajamos", "Išlaidos"],
                        index=0 if r["tipas"] == "Pajamos" else 1,
                        key=f"t_{r['id']}"
                    )
                with colC:
                    new_s = st.number_input(
                        f"Suma ({CURRENCY})",
                        min_value=0.0,
                        step=1.0,
                        value=float(r["suma_eur"]),
                        format="%.2f",
                        key=f"s_{r['id']}"
                    )
                with colD:
                    new_k = st.text_input("Kategorija", value=r["kategorija"], key=f"k_{r['id']}")

                new_p = st.text_input("Prekybos vieta", value=r.get("prekybos_centras", ""), key=f"p_{r['id']}")
                new_a = st.text_input("Aprašymas", value=r.get("aprasymas", ""), key=f"a_{r['id']}")

                b1, b2 = st.columns([1, 1])
                with b1:
                    if st.button("💾 Išsaugoti pakeitimus", key=f"save_{r['id']}"):
                        update_row(r["id"], new_d, new_t, new_k, new_p, new_a, new_s)

                with b2:
                    if st.button("🗑️ Ištrinti įrašą", key=f"del_{r['id']}"):
                        delete_row(r["id"])

# ======================================================
# CHARTS
# ======================================================
st.subheader("📈 Analitika")

df_all = df.sort_values("data").copy()
df_all["signed"] = df_all["suma_eur"].where(df_all["tipas"] == "Pajamos", -df_all["suma_eur"])

daily = df_all.groupby("data", as_index=False)["signed"].sum()
daily = daily.sort_values("data")
daily["balansas"] = daily["signed"].cumsum()

fig_bal = px.line(daily, x="data", y="balansas", title="Kaupiamasis balansas (visa istorija)")
st.plotly_chart(fig_bal, use_container_width=True)

if not df_f.empty:
    tmp = df_f.copy()
    tmp["ym_sort"] = tmp["data"].dt.to_period("M").dt.to_timestamp()
    tmp["ym"] = tmp["data"].dt.to_period("M").astype(str)

    monthly = (
        tmp.groupby(["ym_sort", "ym", "tipas"], as_index=False)["suma_eur"]
        .sum()
        .sort_values("ym_sort")
    )

    fig_bar = px.bar(
        monthly,
        x="ym",
        y="suma_eur",
        color="tipas",
        barmode="group",
        title="Pajamos vs Išlaidos (pagal filtrą)"
    )
    fig_bar.update_xaxes(type="category")
    st.plotly_chart(fig_bar, use_container_width=True)

exp_f = df_f[df_f["tipas"] == "Išlaidos"].copy()
if not exp_f.empty:
    cat_sum = exp_f.groupby("kategorija", as_index=False)["suma_eur"].sum().sort_values("suma_eur", ascending=True)

    fig_cat = px.bar(
        cat_sum,
        x="suma_eur",
        y="kategorija",
        orientation="h",
        title="Išlaidos pagal kategorijas"
    )
    st.plotly_chart(fig_cat, use_container_width=True)
    st.dataframe(cat_sum.sort_values("suma_eur", ascending=False), use_container_width=True, hide_index=True)

# ======================================================
# PREDICTION / WHAT-IF SCENARIO
# ======================================================
st.subheader("🔮 Ateities scenarijus / Prediction")

# Mėnesinis pagrindas
monthly_all = (
    df.groupby(["month_ts", "month", "tipas"], as_index=False)["suma_eur"]
    .sum()
    .sort_values("month_ts")
)

income_monthly = (
    monthly_all[monthly_all["tipas"] == "Pajamos"][["month_ts", "month", "suma_eur"]]
    .rename(columns={"suma_eur": "income"})
)

expense_monthly = (
    monthly_all[monthly_all["tipas"] == "Išlaidos"][["month_ts", "month", "suma_eur"]]
    .rename(columns={"suma_eur": "expense"})
)

month_base = pd.merge(income_monthly, expense_monthly, on=["month_ts", "month"], how="outer").fillna(0.0)
month_base["net"] = month_base["income"] - month_base["expense"]
month_base = month_base.sort_values("month_ts").reset_index(drop=True)

if month_base.empty:
    st.info("Prediction blokui kol kas per mažai duomenų.")
else:
    with st.expander("⚙️ Scenarijaus nustatymai", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            scenario_lookback = st.slider("Bazės laikotarpis (mėn.)", 1, min(12, max(1, len(month_base))), min(6, len(month_base)))
        with c2:
            scenario_horizon = st.slider("Prognozės horizontas (mėn.)", 3, 60, 12, 1)
        with c3:
            one_time_boost = st.number_input("Vienkartinė suma pradžioje (€)", min_value=0.0, value=0.0, step=100.0, format="%.2f")

        recent = month_base.tail(scenario_lookback).copy()

        base_income = safe_float(recent["income"].mean())
        base_expense = safe_float(recent["expense"].mean())

        if base_income < 0:
            base_income = 0.0
        if base_expense < 0:
            base_expense = 0.0

        st.markdown(
            f"""
            <div class="scenario-box">
                <b>Bazinė prognozė skaičiuojama pagal paskutinių {scenario_lookback} mėn. vidurkį:</b><br>
                Vid. mėnesio pajamos: <b>{money(base_income)}</b><br>
                Vid. mėnesio išlaidos: <b>{money(base_expense)}</b><br>
                Vid. mėnesio likutis: <b>{money(base_income - base_expense)}</b>
            </div>
            """,
            unsafe_allow_html=True
        )

        c4, c5 = st.columns(2)
        with c4:
            monthly_income_change = st.number_input("Papildomos / mažesnės mėnesio pajamos (€)", value=0.0, step=50.0, format="%.2f")
        with c5:
            recurring_extra_saving = st.number_input("Papildomas taupymas kas mėn. (€)", min_value=0.0, value=0.0, step=50.0, format="%.2f")

        expense_categories = ["Jokių pakeitimų"] + sorted(
            df[df["tipas"] == "Išlaidos"]["kategorija"].replace("", "Nežinoma").unique().tolist()
        )

        c6, c7, c8 = st.columns([1.5, 1, 1.2])
        with c6:
            reduce_category = st.selectbox("Kurią kategoriją mažinti scenarijuje", expense_categories)
        with c7:
            reduce_pct = st.slider("Mažinimas (%)", 0, 100, 0, 5)
        with c8:
            released_monthly_after = st.number_input("Papildoma laisva suma po X mėn. (€)", min_value=0.0, value=0.0, step=50.0, format="%.2f")

        release_start_month = st.slider("Po kiek mėn. ta suma atsiras", 1, 60, 12, 1)

    # Kategorijos bazė per paskutinius N mėn.
    recent_month_labels = recent["month"].tolist()
    cat_recent = df[(df["tipas"] == "Išlaidos") & (df["month"].isin(recent_month_labels))].copy()
    category_cut_monthly = 0.0

    if reduce_category != "Jokių pakeitimų" and not cat_recent.empty:
        target_cat = reduce_category
        cat_recent["kategorija"] = cat_recent["kategorija"].replace("", "Nežinoma")
        cat_total = cat_recent[cat_recent["kategorija"] == target_cat]["suma_eur"].sum()
        category_avg_monthly = cat_total / max(1, scenario_lookback)
        category_cut_monthly = category_avg_monthly * (reduce_pct / 100.0)

    scenario_income = max(0.0, base_income + monthly_income_change)
    scenario_expense = max(0.0, base_expense - category_cut_monthly)
    scenario_net_before_extra = scenario_income - scenario_expense
    scenario_net_after_extra = scenario_net_before_extra + recurring_extra_saving

    current_total_balance = float(
        df["suma_eur"].where(df["tipas"] == "Pajamos", -df["suma_eur"]).sum()
    )
    scenario_start_balance = current_total_balance + one_time_boost

    # Projekcija
    last_hist_month = df["month_ts"].max()
    proj_rows = []
    running_balance = scenario_start_balance

    for i in range(1, scenario_horizon + 1):
        proj_month_ts = add_month_start(last_hist_month, i)
        extra_release = released_monthly_after if i >= release_start_month else 0.0
        proj_net = scenario_net_after_extra + extra_release
        running_balance += proj_net

        proj_rows.append({
            "Mėnuo": proj_month_ts.strftime("%Y-%m"),
            "Prognozuojamos pajamos": scenario_income,
            "Prognozuojamos išlaidos": scenario_expense,
            "Papildomas taupymas": recurring_extra_saving,
            "Atsilaisvinusi suma": extra_release,
            "Mėnesio likutis": proj_net,
            "Prognozuojamas balansas": running_balance
        })

    proj_df = pd.DataFrame(proj_rows)

    # Tikslai
    annual_expense_now = scenario_expense * 12
    reserve_3m = scenario_expense * 3
    reserve_6m = scenario_expense * 6
    reserve_12m = scenario_expense * 12

    def months_to_target(target: float, start_balance: float, monthly_gain: float, release_amt: float, release_month: int, horizon: int = 240):
        bal = start_balance
        for m in range(1, horizon + 1):
            bal += monthly_gain + (release_amt if m >= release_month else 0.0)
            if bal >= target:
                return m
        return None

    m_to_3 = months_to_target(reserve_3m, scenario_start_balance, scenario_net_after_extra, released_monthly_after, release_start_month)
    m_to_6 = months_to_target(reserve_6m, scenario_start_balance, scenario_net_after_extra, released_monthly_after, release_start_month)
    m_to_12 = months_to_target(reserve_12m, scenario_start_balance, scenario_net_after_extra, released_monthly_after, release_start_month)

    final_12 = proj_df.iloc[min(11, len(proj_df)-1)]["Prognozuojamas balansas"] if not proj_df.empty else scenario_start_balance
    final_24 = proj_df.iloc[min(23, len(proj_df)-1)]["Prognozuojamas balansas"] if len(proj_df) >= 1 else scenario_start_balance
    final_last = proj_df.iloc[-1]["Prognozuojamas balansas"] if not proj_df.empty else scenario_start_balance

    # Prediction KPI
    c1, c2, c3 = st.columns(3)
    with c1:
        render_kpi_card(
            "📦 Startinis balansas",
            money(scenario_start_balance),
            "Dabartinis bendras balansas + vienkartinė suma",
            "neutral" if scenario_start_balance >= 0 else "negative"
        )
    with c2:
        render_kpi_card(
            "📈 Prognozuojamas mėn. likutis",
            money(scenario_net_after_extra),
            "Po pajamų / išlaidų / kategorijos mažinimo / papildomo taupymo",
            "positive" if scenario_net_after_extra > 0 else ("warning" if scenario_net_after_extra == 0 else "negative")
        )
    with c3:
        render_kpi_card(
            f"🎯 Po {scenario_horizon} mėn.",
            money(final_last),
            "Prognozuojamas balansas horizonto pabaigoje",
            "positive" if final_last >= scenario_start_balance else "warning"
        )

    c4, c5, c6 = st.columns(3)
    with c4:
        render_kpi_card(
            "🛟 3 mėn. pagalvė",
            money(reserve_3m),
            f"Pasieksi per {m_to_3} mėn." if m_to_3 is not None else "Per prognozės ribas nepasiekiama",
            "positive" if m_to_3 is not None else "warning"
        )
    with c5:
        render_kpi_card(
            "🛟 6 mėn. pagalvė",
            money(reserve_6m),
            f"Pasieksi per {m_to_6} mėn." if m_to_6 is not None else "Per prognozės ribas nepasiekiama",
            "positive" if m_to_6 is not None else "warning"
        )
    with c6:
        render_kpi_card(
            "🛟 12 mėn. pagalvė",
            money(reserve_12m),
            f"Pasieksi per {m_to_12} mėn." if m_to_12 is not None else "Per prognozės ribas nepasiekiama",
            "positive" if m_to_12 is not None else "warning"
        )

    st.markdown(
        f"""
        <div class="scenario-box">
            <b>Scenarijaus santrauka</b><br>
            • Po 12 mėn. prognozuojamas balansas: <b>{money(final_12)}</b><br>
            • Po 24 mėn. prognozuojamas balansas: <b>{money(final_24 if len(proj_df) >= 24 else final_last)}</b><br>
            • Kategorijos mažinimo efektas: <b>{money(category_cut_monthly)}/mėn.</b><br>
            • Papildomas taupymas: <b>{money(recurring_extra_saving)}/mėn.</b><br>
            • Papildoma laisva suma nuo {release_start_month}-o mėn.: <b>{money(released_monthly_after)}/mėn.</b>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Scenarijaus grafikas
    hist_monthly_balance = month_base.copy()
    hist_monthly_balance["kumul"] = hist_monthly_balance["net"].cumsum()
    hist_plot = hist_monthly_balance[["month", "month_ts", "kumul"]].copy()
    hist_plot["tipas_linijos"] = "Istorinis balansas"
    hist_plot.rename(columns={"month": "label", "kumul": "balansas"}, inplace=True)

    proj_plot = proj_df.copy()
    proj_plot["month_ts"] = pd.to_datetime(proj_plot["Mėnuo"] + "-01")
    proj_plot["label"] = proj_plot["Mėnuo"]
    proj_plot["balansas"] = proj_plot["Prognozuojamas balansas"]
    proj_plot["tipas_linijos"] = "Prognozė"

    combo_plot = pd.concat(
        [
            hist_plot[["label", "month_ts", "balansas", "tipas_linijos"]],
            proj_plot[["label", "month_ts", "balansas", "tipas_linijos"]],
        ],
        ignore_index=True
    ).sort_values("month_ts")

    fig_proj = px.line(
        combo_plot,
        x="label",
        y="balansas",
        color="tipas_linijos",
        markers=True,
        title="Istorinis balansas + ateities prognozė"
    )
    fig_proj.update_xaxes(type="category")
    st.plotly_chart(fig_proj, use_container_width=True)

    # What-if per kategoriją
    st.markdown("#### 🧪 Kiek duotų kategorijos sumažinimas?")
    if not cat_recent.empty:
        cat_avg = (
            cat_recent.assign(kategorija=cat_recent["kategorija"].replace("", "Nežinoma"))
            .groupby("kategorija", as_index=False)["suma_eur"]
            .sum()
        )
        cat_avg["Vid. mėn. suma"] = cat_avg["suma_eur"] / max(1, scenario_lookback)
        cat_avg["Jei mažinčiau 10%"] = cat_avg["Vid. mėn. suma"] * 0.10
        cat_avg["Jei mažinčiau 20%"] = cat_avg["Vid. mėn. suma"] * 0.20
        cat_avg["Jei mažinčiau 30%"] = cat_avg["Vid. mėn. suma"] * 0.30

        display_cat_avg = cat_avg[["kategorija", "Vid. mėn. suma", "Jei mažinčiau 10%", "Jei mažinčiau 20%", "Jei mažinčiau 30%"]].sort_values("Vid. mėn. suma", ascending=False)
        st.dataframe(display_cat_avg, use_container_width=True, hide_index=True)

    st.markdown("#### 📅 Prognozės lentelė")
    st.dataframe(proj_df, use_container_width=True, hide_index=True)

# ======================================================
# EXPORT
# ======================================================
st.subheader("⬇️ Eksportas (pagal pasirinktus filtrus)")

bio = io.BytesIO()
with pd.ExcelWriter(bio, engine="openpyxl") as writer:
    df_f.drop(columns=[c for c in ["year", "month", "month_ts"] if c in df_f.columns], errors="ignore").to_excel(writer, index=False)
bio.seek(0)

st.download_button(
    "Parsisiųsti Excel",
    data=bio.read(),
    file_name="biudzetas.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
