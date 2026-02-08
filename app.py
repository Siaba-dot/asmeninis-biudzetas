import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
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
# AUTH (Supabase email/password login)
# ======================================================
def login(email, password) -> bool:
    try:
        supabase.auth.sign_in_with_password({"email": email, "password": password})
        return True
    except Exception:
        return False

def logout():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
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

    # stabilūs tipai (kad nelūžtų nei .dt, nei plotly)
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df = df.dropna(subset=["data"])
    df["suma_eur"] = pd.to_numeric(df["suma_eur"], errors="coerce").fillna(0.0)

    # tekstai
    for col in ["kategorija", "prekybos_centras", "aprasymas", "tipas"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)

    # periodai
    df["year"] = df["data"].dt.year
    df["month"] = df["data"].dt.to_period("M").astype(str)
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
    st.info("Kol kas nėra įrašų. Įvesk pirmą operaciją ir viskas pradės „gyventi“.")
    st.stop()

# ======================================================
# FILTERS: whole / year / month + optional type/category
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
# KPI (100% from transactions)
# ======================================================
income = df_f[df_f["tipas"] == "Pajamos"]["suma_eur"].sum()
expense = df_f[df_f["tipas"] == "Išlaidos"]["suma_eur"].sum()
balance = income - expense

st.subheader("📊 KPI")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Pajamos", money(income))
k2.metric("Išlaidos", money(expense))
k3.metric("Balansas", money(balance))

# santaupų norma (be DI, gryna matematika)
savings_rate = None
if income > 0:
    savings_rate = (income - expense) / income
k4.metric("Sutaupymo norma", f"{(savings_rate*100):.1f} %" if savings_rate is not None else "—")

# ======================================================
# SMART INSIGHTS (NO AI)
# ======================================================
st.subheader("🔍 Smart insight: kur bėga pinigai (be DI)")

# konfigūruojami slenksčiai
with st.expander("⚙️ Insight nustatymai", expanded=False):
    small_cap = st.slider("„Smulkios išlaidos“ riba (€)", 1, 50, 10, 1)
    spike_pct = st.slider("„Šuolio“ riba vs praeitas mėnuo (%)", 5, 80, 20, 5)
    lookback_months = st.slider("Vidurkio laikotarpis (mėn.)", 2, 12, 6, 1)

# helper: pasirinktas mėnuo insightams
# jei filtruojamas konkretus mėnuo -> imame jį
# jei ne -> imame paskutinį turimą mėnesį
current_month = month_filter if month_filter != "Visi" else sorted(df["month"].unique().tolist())[-1]

cur = df[df["month"] == current_month].copy()
cur_exp = cur[cur["tipas"] == "Išlaidos"].copy()
cur_inc = cur[cur["tipas"] == "Pajamos"].copy()

# previous month
cur_period = pd.Period(current_month, freq="M")
prev_month = str(cur_period - 1)
prev = df[df["month"] == prev_month].copy()
prev_exp = prev[prev["tipas"] == "Išlaidos"].copy()

insights = []

# 1) Top kategorijos pagal SUMĄ (ne %)
if not cur_exp.empty:
    top_cat = (
        cur_exp.groupby("kategorija")["suma_eur"].sum()
        .sort_values(ascending=False)
        .head(5)
    )
    top_cat_str = ", ".join([f"{k}: {money(v)}" for k, v in top_cat.items()])
    insights.append(f"**Top kategorijos ({current_month})**: {top_cat_str}")

# 2) Smulkios, bet dažnos išlaidos
if not cur_exp.empty:
    small = cur_exp[cur_exp["suma_eur"] <= float(small_cap)]
    if not small.empty:
        insights.append(
            f"**Smulkios išlaidos (≤ {small_cap} €)**: {int(len(small))} kartų, suma **{money(small['suma_eur'].sum())}**."
        )

# 3) „Šuoliai“ vs praeitas mėnuo (kategorijose)
if (not cur_exp.empty) and (not prev_exp.empty):
    cur_cat = cur_exp.groupby("kategorija")["suma_eur"].sum()
    prev_cat = prev_exp.groupby("kategorija")["suma_eur"].sum()
    joined = pd.concat([cur_cat, prev_cat], axis=1)
    joined.columns = ["cur", "prev"]
    joined = joined.fillna(0.0)

    # tik kur prev > 0 (kad nepūstų nuo nulio)
    joined2 = joined[joined["prev"] > 0].copy()
    if not joined2.empty:
        joined2["pct"] = (joined2["cur"] - joined2["prev"]) / joined2["prev"]
        spikes = joined2[joined2["pct"] >= (spike_pct / 100.0)].sort_values("pct", ascending=False).head(5)
        if not spikes.empty:
            parts = []
            for k, row in spikes.iterrows():
                parts.append(f"{k}: {money(row['cur'])} (buvo {money(row['prev'])}, +{row['pct']*100:.0f}%)")
            insights.append(f"**Šuoliai vs {prev_month}**: " + "; ".join(parts))

# 4) „Kur nuolat bėga“: pasikartojančios prekybos vietos (3+ kartai per mėnesį)
if not cur_exp.empty and "prekybos_centras" in cur_exp.columns:
    cur_exp["prekybos_centras"] = cur_exp["prekybos_centras"].replace("", "Nežinoma")
    by_merch = cur_exp.groupby("prekybos_centras").agg(cnt=("suma_eur", "size"), total=("suma_eur", "sum"))
    repeat = by_merch[by_merch["cnt"] >= 3].sort_values("total", ascending=False).head(5)
    if not repeat.empty:
        parts = [f"{idx}: {int(r.cnt)} kart., {money(r.total)}" for idx, r in repeat.iterrows()]
        insights.append("**Pasikartojančios vietos (3+ kartai)**: " + "; ".join(parts))

# 5) „Ar taupymo kryptis gera?“ – sutaupymo norma per mėnesį
cur_income = cur_inc["suma_eur"].sum()
cur_expense = cur_exp["suma_eur"].sum()
if cur_income > 0:
    rate = (cur_income - cur_expense) / cur_income
    if rate < 0:
        insights.append(f"⚠️ **{current_month}**: išlaidos viršija pajamas (sutaupymo norma {rate*100:.1f}%).")
    elif rate < 0.15:
        insights.append(f"⚠️ **{current_month}**: sutaupymo norma žema ({rate*100:.1f}%). Tikslui pasiekti reikės mažinti TOP kategorijas.")
    else:
        insights.append(f"✅ **{current_month}**: sutaupymo norma {rate*100:.1f}% – kryptis gera.")

# 6) Vidurkio palyginimas (paskutiniai N mėnesių) – „ar per daug išleidi šį mėn?“
# Naudojam visas išlaidas (ne filtruotas df_f), nes čia „asmeninis baseline“
all_months = sorted(df["month"].unique().tolist())
cur_idx = all_months.index(current_month) if current_month in all_months else None
if cur_idx is not None:
    start_idx = max(0, cur_idx - lookback_months)
    lookback_list = all_months[start_idx:cur_idx]  # prieš einamą
    if lookback_list:
        base = df[(df["month"].isin(lookback_list)) & (df["tipas"] == "Išlaidos")]["suma_eur"].sum() / len(lookback_list)
        cur_total = df[(df["month"] == current_month) & (df["tipas"] == "Išlaidos")]["suma_eur"].sum()
        if base > 0:
            diff = (cur_total - base) / base
            if diff >= (spike_pct / 100.0):
                insights.append(f"⚠️ **Bendrai išlaidos** {current_month}: {money(cur_total)}. Tai ~{diff*100:.0f}% daugiau nei tavo {len(lookback_list)} mėn. vidurkis ({money(base)}).")

if insights:
    for s in insights:
        st.markdown(f"- {s}")
else:
    st.info("Dar per mažai duomenų insightams. Įvesk daugiau įrašų arba pasirink konkretų mėnesį.")

# ======================================================
# TABLE: edit + delete (controlled, safe)
# ======================================================
st.subheader("📋 Įrašai (redagavimas / trynimas)")

if df_f.empty:
    st.info("Pagal pasirinktus filtrus įrašų nėra.")
else:
    # rodome „kortelėmis“, nes tai patikimiau nei masinis data_editor su DB
    for _, r in df_f.sort_values("data", ascending=False).iterrows():
        title = f"{r['data'].date()} | {r['tipas']} | {r['kategorija']} | {money(r['suma_eur'])}"
        with st.expander(title, expanded=False):
            colA, colB, colC, colD = st.columns([1.1, 1.1, 1.2, 1.2])

            with colA:
                new_d = st.date_input("Data", value=r["data"].date(), key=f"d_{r['id']}")
            with colB:
                new_t = st.selectbox("Tipas", ["Pajamos", "Išlaidos"],
                                     index=0 if r["tipas"] == "Pajamos" else 1,
                                     key=f"t_{r['id']}")
            with colC:
                new_s = st.number_input(f"Suma ({CURRENCY})", min_value=0.0, step=1.0,
                                        value=float(r["suma_eur"]), format="%.2f", key=f"s_{r['id']}")
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

# Kaupiamasis balansas (VISOS istorijos, nes tai „tiesa“)
df_all = df.sort_values("data").copy()
df_all["signed"] = df_all["suma_eur"].where(df_all["tipas"] == "Pajamos", -df_all["suma_eur"])
df_all["balansas"] = df_all["signed"].cumsum()

fig_bal = px.line(df_all, x="data", y="balansas", title="Kaupiamasis balansas (visa istorija)")
st.plotly_chart(fig_bal, use_container_width=True)

# Pajamos vs Išlaidos per mėnesius (pagal filtrus)
if not df_f.empty:
    tmp = df_f.copy()
    tmp["ym"] = tmp["data"].dt.to_period("M").astype(str)
    monthly = tmp.groupby(["ym", "tipas"])["suma_eur"].sum().reset_index()

    fig_bar = px.bar(
        monthly,
        x="ym",
        y="suma_eur",
        color="tipas",
        barmode="group",
        title="Pajamos vs Išlaidos (pagal filtrą)"
    )
    st.plotly_chart(fig_bar, use_container_width=True)

# Išlaidos pagal kategorijas: sumos + procentai (pagal filtrą)
exp_f = df_f[df_f["tipas"] == "Išlaidos"].copy()
if not exp_f.empty:
    cat_sum = exp_f.groupby("kategorija")["suma_eur"].sum().sort_values(ascending=False).reset_index()
    fig_pie = px.pie(cat_sum, names="kategorija", values="suma_eur", hole=0.45,
                     title="Išlaidos pagal kategorijas (sumos + %)")
    st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("**Išlaidos pagal kategorijas (sumos):**")
    st.dataframe(cat_sum, use_container_width=True, hide_index=True)

# ======================================================
# EXPORT
# ======================================================
st.subheader("⬇️ Eksportas (pagal pasirinktus filtrus)")

bio = io.BytesIO()
with pd.ExcelWriter(bio, engine="openpyxl") as writer:
    df_f.drop(columns=[c for c in ["year", "month"] if c in df_f.columns], errors="ignore").to_excel(writer, index=False)
bio.seek(0)

st.download_button(
    "Parsisiųsti Excel",
    data=bio.read(),
    file_name="biudzetas.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
