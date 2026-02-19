import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
from supabase import create_client
from supabase.client import Client
import io
import requests

st.set_page_config(page_title="💶 Asmeninis biudžetas", layout="wide")

TABLE = "biudzetas"
CURRENCY = "€"

# === ĮRAŠYK SAVO EDGE FUNCTION URL ===
# Jei tavo Supabase URL yra https://abcxyz.supabase.co, tai PROJECT_REF = abcxyz
FUNCTION_URL = "https://<PROJECT_REF>.functions.supabase.co/delete-account"


# ======================================================
# Supabase client
# ======================================================
@st.cache_resource(show_spinner=False)
def get_supabase() -> Client:
    return create_client(
        st.secrets["supabase"]["url"],
        st.secrets["supabase"]["anon_key"]
    )

supabase = get_supabase()


# ======================================================
# AUTH helpers
# ======================================================
def _store_session(session) -> None:
    if session is None:
        st.session_state.pop("sb_session", None)
        return
    st.session_state["sb_session"] = {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
    }

def _get_access_token():
    s = st.session_state.get("sb_session")
    return s.get("access_token") if s else None

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

def login(email: str, password: str) -> tuple[bool, str]:
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        _store_session(res.session)
        return True, ""
    except Exception as e:
        return False, str(e)

def signup(email: str, password: str) -> tuple[bool, str]:
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        # jei confirm email OFF, kartais gaunasi session iškart
        try:
            if getattr(res, "session", None) is not None:
                _store_session(res.session)
        except Exception:
            pass
        return True, ""
    except Exception as e:
        return False, str(e)

def send_magic_link(email: str) -> tuple[bool, str]:
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


# ======================================================
# Restore session if possible + mark authenticated
# ======================================================
_restore_session()

if "authenticated" not in st.session_state:
    try:
        u = supabase.auth.get_user()
        if u and getattr(u, "user", None) and getattr(u.user, "email", None):
            st.session_state["authenticated"] = True
            st.session_state["email"] = u.user.email
    except Exception:
        pass


# ======================================================
# LOGIN UI
# ======================================================
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


# ======================================================
# Sidebar + Delete account
# ======================================================
USER_EMAIL = st.session_state["email"]
st.sidebar.success(f"👤 {USER_EMAIL}")

if st.sidebar.button("🚪 Atsijungti"):
    logout()

with st.sidebar.expander("⚠️ Paskyros ištrynimas"):
    st.write("Šis veiksmas ištrins paskyrą ir VISUS tavo duomenis duomenų bazėje. Atšaukti neįmanoma.")
    typed = st.text_input("Įrašyk DELETE patvirtinimui", key="delete_confirm")

    if st.button("🗑️ Ištrinti paskyrą", disabled=(typed != "DELETE")):
        token = _get_access_token()
        if not token:
            st.error("Nėra aktyvios sesijos. Prisijunk iš naujo.")
            st.stop()

        if "<PROJECT_REF>" in FUNCTION_URL:
            st.error("FUNCTION_URL dar neįrašytas. Įrašyk savo projekto ref į URL.")
            st.stop()

        r = requests.post(
            FUNCTION_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={"confirm": "DELETE"},
            timeout=30,
        )

        if r.status_code == 200:
            st.success("Paskyra ištrinta. Viso gero 👋")
            st.session_state.clear()
            st.rerun()
        else:
            st.error(f"Nepavyko ištrinti ({r.status_code}).")
            st.code(r.text)


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

    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df = df.dropna(subset=["data"])
    df["suma_eur"] = pd.to_numeric(df["suma_eur"], errors="coerce").fillna(0.0)

    for col in ["kategorija", "prekybos_centras", "aprasymas", "tipas"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)

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
# UI
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
k1, k2, k3, k4 = st.columns(4)
k1.metric("Pajamos", money(income))
k2.metric("Išlaidos", money(expense))
k3.metric("Balansas", money(balance))

savings_rate = None
if income > 0:
    savings_rate = (income - expense) / income
k4.metric("Sutaupymo norma", f"{(savings_rate*100):.1f} %" if savings_rate is not None else "—")


# ======================================================
# TABLE: edit + delete
# ======================================================
st.subheader("📋 Įrašai (redagavimas / trynimas)")

if df_f.empty:
    st.info("Pagal pasirinktus filtrus įrašų nėra.")
else:
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

df_all = df.sort_values("data").copy()
df_all["signed"] = df_all["suma_eur"].where(df_all["tipas"] == "Pajamos", -df_all["suma_eur"])
df_all["balansas"] = df_all["signed"].cumsum()

fig_bal = px.line(df_all, x="data", y="balansas", title="Kaupiamasis balansas (visa istorija)")
st.plotly_chart(fig_bal, use_container_width=True)


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


