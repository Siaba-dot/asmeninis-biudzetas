# -*- coding: utf-8 -*-
# Asmeninis biudžetas — vieno failo Streamlit aplikacija
# Autentifikacija tik per st.secrets (be jokių jautrių duomenų kode).
# Palaikomi slaptažodžiai: plaintext (password) ARBA bcrypt hash (password_hash).

from datetime import datetime, date
from io import BytesIO

import streamlit as st
import pandas as pd

# ------------------------------------------------------------
# 1) PIRMA Streamlit komanda — puslapio konfigūracija
# ------------------------------------------------------------
st.set_page_config(
    page_title="Asmeninis biudžetas",
    page_icon="💶",
    layout="wide",
    initial_sidebar_state="expanded",  # Sidebar iškart atvertas filtrams
)

# ------------------------------------------------------------
# 2) Minimalus stilius — kompaktiškas, bet 'kvėpuojantis'
# ------------------------------------------------------------
st.markdown(
    """
    <style>
      header {visibility: hidden;}
      .block-container {padding-top: 1.2rem; padding-bottom: 1.2rem; max-width: 1600px;}
      .stMetric {background: #111; border-radius: 8px; padding: 0.75rem; border: 1px solid #222;}
      .stButton>button, .stDownloadButton>button {
        background:#1f2937; color:#e5e7eb; border:1px solid #374151;
      }
      .stButton>button:hover, .stDownloadButton>button:hover {
        background:#111827; border-color:#4b5563;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------
# 3) Autentifikacija per st.secrets
# ------------------------------------------------------------
def _read_users_from_secrets():
    """Grąžina vartotojų sąrašą iš st.secrets. Jei neranda, grąžina []."""
    try:
        users = st.secrets["auth"]["users"]
        if not isinstance(users, (list, tuple)):
            return []
        norm = []
        for u in users:
            if isinstance(u, dict):
                norm.append({
                    "email": str(u.get("email", "")).strip(),
                    "password": u.get("password"),           # plaintext (nebūtina)
                    "password_hash": u.get("password_hash"), # bcrypt (nebūtina)
                })
        return norm
    except Exception:
        return []

def _bcrypt_check(password, password_hash):
    """Tikrina bcrypt hash; jei bcrypt neįdiegtas, grąžina False."""
    try:
        import bcrypt
    except Exception:
        return False
    try:
        if isinstance(password, str):
            password = password.encode("utf-8")
        if isinstance(password_hash, str):
            password_hash = password_hash.encode("utf-8")
        return bcrypt.checkpw(password, password_hash)
    except Exception:
        return False

def _is_valid_credentials(email: str, password: str) -> bool:
    """Leidžia prisijungti, jei el. paštas + slaptažodis atitinka secrets (case-insensitive email)."""
    email = (email or "").strip().lower()
    password = (password or "")
    if not email or not password:
        return False

    for u in _read_users_from_secrets():
        u_email = (u.get("email") or "").strip().lower()

        # 1) bcrypt
        ph = u.get("password_hash")
        if u_email == email and ph and _bcrypt_check(password, ph):
            return True

        # 2) plaintext
        pw = u.get("password")
        if u_email == email and isinstance(pw, str) and pw == password:
            return True

    return False

def _init_auth_state():
    if "auth" not in st.session_state:
        st.session_state.auth = {"is_authenticated": False, "user_email": None, "ts": None}

def render_auth_ui():
    users = _read_users_from_secrets()
    if not users:
        st.error(
            "Nerasti prisijungimo duomenys `st.secrets`. "
            "Eik į *Manage app → Settings → Secrets* ir pridėk [auth].users sąrašą."
        )
        with st.expander("Pavyzdys (plaintext)", expanded=False):
            st.code(
                '''[auth]
users = [
  { email = "vardas@pastas.lt", password = "slaptazodis" }
]''',
                language="toml",
            )
        with st.expander("Pavyzdys (bcrypt)", expanded=False):
            st.code(
                '''[auth]
users = [
  { email = "vardas@pastas.lt", password_hash = "$2b$12$...." }
]''',
                language="toml",
            )
        return

    st.markdown("### Prisijungimas")
    with st.form("login_form", clear_on_submit=False):
        email = st.text_input("El. paštas", placeholder="pvz., vardas@pastas.lt")
        password = st.text_input("Slaptažodis", type="password", placeholder="••••••••")
        submitted = st.form_submit_button("Prisijungti", use_container_width=True)

    if submitted:
        if _is_valid_credentials(email, password):
            st.session_state.auth = {
                "is_authenticated": True,
                "user_email": (email or "").strip(),
                "ts": datetime.utcnow().isoformat(),
            }
            st.success("Sėkmingai prisijungta ✅")
            st.rerun()
        else:
            st.error("Neteisingi prisijungimo duomenys.")

def sign_out():
    st.session_state.auth = {"is_authenticated": False, "user_email": None, "ts": None}
    st.rerun()

# ------------------------------------------------------------
# 4) Biudžeto duomenys + mėnesio likučiai
# ------------------------------------------------------------
INCOME_CATS = [
    "Atlyginimas",
    "Avansas",
    "Papildomos pajamos",
    "Dovanos",
    "Kita (pajamos)",
]

EXPENSE_CATS = [
    "Kreditai",
    "Draudimas",
    "Paslaugos",
    "Maistas",
    "Transportas",
    "Nenumatytos išlaidos",
    "Dovanos",
    "Kita (išlaidos)",
]

def _init_budget_state():
    if "budget_df" not in st.session_state:
        st.session_state.budget_df = pd.DataFrame(
            columns=["Data", "Tipas", "Prekybos centras", "Kategorija", "Aprašymas", "Suma (€)"]
        )
    if "initial_balance" not in st.session_state:
        st.session_state.initial_balance = 0.00  # vienkartinis pirmam mėnesiui
    if "opening_overrides" not in st.session_state:
        st.session_state.opening_overrides = {}  # {'YYYY-MM': float}
    if "selected_month" not in st.session_state:
        # Jei nėra įrašų – šiandienos mėnuo
        st.session_state.selected_month = pd.Timestamp.today().to_period("M").strftime("%Y-%m")

def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Užtikrina stulpelius ir skaitinį 'Suma (€)' tipą."""
    needed = ["Data", "Tipas", "Prekybos centras", "Kategorija", "Aprašymas", "Suma (€)"]
    for col in needed:
        if col not in df.columns:
            df[col] = "" if col != "Suma (€)" else 0.0
    # Koercija į float
    try:
        df["Suma (€)"] = pd.to_numeric(df["Suma (€)"], errors="coerce").fillna(0.0).astype(float)
    except Exception:
        pass
    return df[needed]

def _month_key_from_str(s: str) -> str:
    dt = pd.to_datetime(s, errors="coerce")
    if pd.isna(dt):
        return ""
    return dt.to_period("M").strftime("%Y-%m")

def add_transaction_row(dt: date, ttype: str, store: str, category: str, note: str, amount: float):
    row = {
        "Data": dt.strftime("%Y-%m-%d"),
        "Tipas": ttype,
        "Prekybos centras": (store or "").strip(),
        "Kategorija": (category or "").strip(),
        "Aprašymas": (note or "").strip(),
        "Suma (€)": round(float(amount), 2),
    }
    st.session_state.budget_df = pd.concat(
        [st.session_state.budget_df, pd.DataFrame([row])],
        ignore_index=True,
    )
    st.session_state.budget_df = _ensure_columns(st.session_state.budget_df)

def compute_summary(df: pd.DataFrame):
    df = _ensure_columns(df)
    if df.empty:
        return 0.0, 0.0, 0.0
    pajamos = df.loc[df["Tipas"] == "Pajamos", "Suma (€)"].sum()
    islaidos = df.loc[df["Tipas"] == "Išlaidos", "Suma (€)"].sum()
    balansas = round(pajamos - islaidos, 2)
    return round(pajamos, 2), round(islaidos, 2), balansas

def compute_monthly_balances(df: pd.DataFrame, initial_balance: float, overrides: dict):
    """
    Grąžina:
      { 'YYYY-MM': {'pajamos': float, 'islaidos': float, 'opening': float, 'closing': float}, ... }
    opening: overrides.get(m, prev_closing) arba initial_balance pirmajam.
    """
    df = _ensure_columns(df)
    if df.empty:
        return {}

    tmp = df.copy()
    tmp["Data_dt"] = pd.to_datetime(tmp["Data"], errors="coerce")
    tmp = tmp.dropna(subset=["Data_dt"])
    if tmp.empty:
        return {}

    tmp["Mėnuo"] = tmp["Data_dt"].dt.to_period("M").astype(str)
    piv = tmp.pivot_table(index="Mėnuo", columns="Tipas", values="Suma (€)", aggfunc="sum", fill_value=0.0)
    for col in ["Pajamos", "Išlaidos"]:
        if col not in piv.columns:
            piv[col] = 0.0
    piv = piv.sort_index()

    result = {}
    prev_closing = None
    for m in piv.index.tolist():
        paj = float(piv.loc[m, "Pajamos"])
        isl = float(piv.loc[m, "Išlaidos"])

        if isinstance(overrides, dict) and m in overrides:
            opening = float(overrides[m])
        elif prev_closing is not None:
            opening = float(prev_closing)
        else:
            opening = float(initial_balance)

        closing = round(opening + paj - isl, 2)
        result[m] = {
            "pajamos": round(paj, 2),
            "islaidos": round(isl, 2),
            "opening": round(opening, 2),
            "closing": closing,
        }
        prev_closing = closing

    return result

def available_months(df: pd.DataFrame):
    df = _ensure_columns(df)
    if df.empty:
        today_m = pd.Timestamp.today().to_period("M").strftime("%Y-%m")
        return [today_m]
    m = df["Data"].apply(_month_key_from_str)
    months = sorted([x for x in m.unique() if x])
    return months or [pd.Timestamp.today().to_period("M").strftime("%Y-%m")]

# ------------------------------------------------------------
# 5) Filtrai (Sidebar)
# ------------------------------------------------------------
def _filters_ui(df: pd.DataFrame) -> pd.DataFrame:
    """Filtrai šoninėje juostoje: data, tipas, kategorijos, prekybos centrai, suma, paieška."""
    df = _ensure_columns(df).copy()
    df["Data_dt_full"] = pd.to_datetime(df["Data"], errors="coerce")

    # Datos ribos
    if df["Data_dt_full"].notna().any():
        min_d = df["Data_dt_full"].min().date()
        max_d = df["Data_dt_full"].max().date()
    else:
        today = datetime.today().date()
        min_d, max_d = today, today

    # Suma ribos
    amount_min_all = float(df["Suma (€)"].min()) if not df.empty else 0.0
    amount_max_all = float(df["Suma (€)"].max()) if not df.empty else 0.0
    if amount_max_all < amount_min_all:
        amount_max_all = amount_min_all

    cats_all = sorted([c for c in df["Kategorija"].dropna().unique() if str(c).strip() != ""])
    stores_all = sorted([s for s in df["Prekybos centras"].dropna().unique() if str(s).strip() != ""])

    with st.sidebar:
        st.markdown("## 🔎 Filtrai")

        # Laikotarpis
        start_end = st.date_input(
            "Laikotarpis",
            value=(min_d, max_d),
            min_value=min_d,
            max_value=max_d
        )
        if isinstance(start_end, tuple) and len(start_end) == 2:
            start_d, end_d = start_end
        else:
            start_d, end_d = min_d, max_d

        # Tipas
        tip_choice = st.radio("Tipas", ["Visi", "Pajamos", "Išlaidos"], horizontal=True)
        tipos = ["Pajamos", "Išlaidos"] if tip_choice == "Visi" else [tip_choice]

        # Kategorijos
        choose_cats = st.multiselect("Kategorijos", cats_all, default=cats_all)

        # Prekybos centrai
        choose_stores = st.multiselect("Prekybos centrai", stores_all, default=stores_all)

        # Suma
        slider_max = amount_max_all if amount_max_all > amount_min_all else amount_min_all
        amt_min, amt_max = st.slider(
            "Suma (€)",
            min_value=float(amount_min_all),
            max_value=float(slider_max),
            value=(float(amount_min_all), float(slider_max)),
            step=0.10
        )

        # Paieška aprašyme
        search_note = st.text_input("Paieška aprašyme", placeholder="pvz., čekis, dovana…")

    # ---- Taikome filtrus
    f = df.copy()
    f["Data_dt"] = pd.to_datetime(f["Data"], errors="coerce").dt.date
    f = f[(f["Data_dt"] >= start_d) & (f["Data_dt"] <= end_d)]

    if tipos:
        f = f[f["Tipas"].isin(tipos)]
    if choose_cats:
        f = f[f["Kategorija"].isin(choose_cats)]
    if choose_stores:
        f = f[f["Prekybos centras"].isin(choose_stores)]

    f = f[(f["Suma (€)"] >= amt_min) & (f["Suma (€)"] <= amt_max)]

    if search_note.strip():
        q = search_note.strip().lower()
        f = f[f["Aprašymas"].astype(str).str.lower().str.contains(q, na=False)]

    return f.drop(columns=["Data_dt", "Data_dt_full"], errors="ignore")

# ------------------------------------------------------------
# 6) UI komponentai
# ------------------------------------------------------------
def render_topbar(months):
    left, mid, right = st.columns([1.4, 2, 1.2])
    with left:
        st.markdown("## 💶 Asmeninis biudžetas")
    with mid:
        # Default – paskutinis žinomas mėnuo
        default_month = st.session_state.get("selected_month", months[-1])
        idx = months.index(default_month) if default_month in months else len(months) - 1
        st.selectbox(
            "Mėnuo",
            options=months,
            index=idx,
            key="selected_month",   # selectbox pats tvarko session_state
        )
    with right:
        user = st.session_state.auth.get("user_email")
        st.caption(f"Prisijungta: **{user}**" if user else "")
        if st.button("Atsijungti", use_container_width=True, key="btn_signout"):
            sign_out()

def render_balance_settings():
    st.markdown("### Likučio nustatymai")

    # Row 1: du įvedimai tame pačiame lygyje (vienas lizdinimo lygis)
    r1c1, r1c2 = st.columns([1, 1])

    with r1c1:
        if "initial_balance" not in st.session_state:
            st.session_state.initial_balance = 0.0

        st.number_input(
            "Pradinis likutis (pirmajam mėnesiui)",
            min_value=-1_000_000.0,
            max_value=1_000_000.0,
            step=10.0,
            key="initial_balance",  # be value=, nes key jau riša su session_state
            help="Naudojamas tik pirmam mėnesiui, jei nenurodytas perrašymas.",
        )

    with r1c2:
        cur_m = st.session_state.get("selected_month") or available_months(st.session_state.budget_df)[0]
        cur_val = float(st.session_state.opening_overrides.get(cur_m, 0.0))
        # Vietinis įvedimas (be key)
        override_val = st.number_input(
            f"Šio mėnesio pradžios likutis ({cur_m})",
            min_value=-1_000_000.0,
            max_value=1_000_000.0,
            step=10.0,
            value=cur_val,
            help="Jei nori priverstinai nurodyti šio mėnesio pradžią.",
        )

    # Row 2: mygtukai (kitas columns rinkinys tame pačiame lygyje)
    r2c1, r2c2 = st.columns([1, 1])
    with r2c1:
        if st.button("💾 Išsaugoti šio mėn. pradžią", use_container_width=True, key="btn_save_opening"):
            st.session_state.opening_overrides[cur_m] = float(override_val)
            st.success(f"Išsaugota {cur_m} pradžia: {override_val:.2f} €")
            st.rerun()
    with r2c2:
        if st.button("♻️ Pašalinti šio mėn. perrašymą", use_container_width=True, key="btn_clear_opening"):
            if cur_m in st.session_state.opening_overrides:
                st.session_state.opening_overrides.pop(cur_m, None)
                st.success(f"Pašalintas {cur_m} pradžios perrašymas")
                st.rerun()

def render_budget_form():
    st.markdown("### Naujas įrašas")

    c1, c2, c3, c4, c5, c6 = st.columns([1.0, 0.9, 1.2, 1.2, 2.2, 0.9])
    with c1:
        dt = st.date_input("Data", value=datetime.today(), format="YYYY-MM-DD")
    with c2:
        ttype = st.selectbox("Tipas", ["Pajamos", "Išlaidos"], index=1)
    with c3:
        cat_options = INCOME_CATS if ttype == "Pajamos" else EXPENSE_CATS
        category = st.selectbox("Kategorija", options=cat_options, index=0)
    with c4:
        store = st.text_input("Prekybos centras", placeholder="pvz., Rimi, Maxima, Lidl, Iki")
    with c5:
        note = st.text_input("Aprašymas", placeholder="Trumpas paaiškinimas (nebūtina)")
    with c6:
        amount = st.number_input("Suma (€)", min_value=0.00, value=0.00, step=0.10, format="%.2f")

    c7, c8 = st.columns([1, 1])
    with c7:
        if st.button("➕ Pridėti", use_container_width=True):
            if amount <= 0:
                st.warning("Suma turi būti didesnė už 0.")
            else:
                add_transaction_row(dt, ttype, store, category, note, amount)
                st.success("Įrašas pridėtas.")
                st.rerun()
    with c8:
        if st.button("🧹 Išvalyti visus įrašus", use_container_width=True):
            st.session_state.budget_df = st.session_state.budget_df.iloc[0:0].copy()
            st.rerun()

def render_month_header_and_metrics():
    df = _ensure_columns(st.session_state.budget_df)
    months = available_months(df)
    sel = st.session_state.get("selected_month", months[-1])  # NEperrašom atgal į session_state

    monthly = compute_monthly_balances(df, st.session_state.initial_balance, st.session_state.opening_overrides)

    # Jei pasirinktam mėnesiui nėra įrašų — suformuojam tuščią su atitinkamu opening
    if sel not in monthly:
        prev_months = sorted(monthly.keys())
        if prev_months:
            prev_closing = monthly[prev_months[-1]]["closing"]
        else:
            prev_closing = st.session_state.initial_balance
        opening = float(st.session_state.opening_overrides.get(sel, prev_closing))
        monthly[sel] = {"pajamos": 0.0, "islaidos": 0.0, "opening": round(opening, 2), "closing": round(opening, 2)}

    cur = monthly[sel]

    st.markdown("### Mėnesio suvestinė")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Pradžios likutis", f"{cur['opening']:,.2f} €")
    with c2:
        st.metric("Pajamos", f"{cur['pajamos']:,.2f} €")
    with c3:
        st.metric("Išlaidos", f"{cur['islaidos']:,.2f} €")
    with c4:
        st.metric("Pabaigos likutis", f"{cur['closing']:,.2f} €",
                  delta=f"{(cur['pajamos'] - cur['islaidos']):,.2f} €")

def render_budget_table_and_summary():
    st.markdown("### Įrašai")
    df = _ensure_columns(st.session_state.budget_df)
    if df.empty:
        st.info("Dar nėra įrašų. Pridėk pirmą įrašą viršuje.")
    else:
        st.dataframe(
            df.sort_values(by=["Data"], ascending=False),
            use_container_width=True,
            hide_index=True,
        )

    pajamos, islaidos, balansas = compute_summary(df)
    st.markdown("---")
    s1, s2, s3 = st.columns(3)
    with s1:
        st.metric("Viso pajamos", f"{pajamos:,.2f} €")
    with s2:
        st.metric("Viso išlaidos", f"{islaidos:,.2f} €")
    with s3:
        st.metric("Bendras balansas", f"{balansas:,.2f} €", delta=f"{(pajamos - islaidos):,.2f} €")

def render_charts():
    st.markdown("### Diagramos")
    df = _ensure_columns(st.session_state.budget_df)
    if df.empty:
        st.caption("Diagramos atsiras, kai įvesi bent vieną įrašą.")
        return

    # Filtrai dabar šoninėje juostoje:
    f = _filters_ui(df)
    st.divider()

    # 1) Išlaidos pagal kategoriją
    col1, col2 = st.columns(2)
    with col1:
        out_df = f[f["Tipas"] == "Išlaidos"].copy()
        if out_df.empty:
            st.caption("Nėra išlaidų šiame filtre.")
        else:
            grp = (
                out_df.groupby("Kategorija", dropna=False)["Suma (€)"]
                .sum()
                .sort_values(ascending=False)
                .reset_index()
            )
            grp = grp.rename(columns={"Suma (€)": "Suma"})
            grp = grp.set_index("Kategorija")
            st.subheader("Išlaidos pagal kategoriją (€)")
            st.bar_chart(grp)

    # 2) Išlaidos pagal prekybos centrą
    with col2:
        out_df2 = out_df.copy()
        if out_df2.empty:
            st.caption("Nėra išlaidų šiame filtre.")
        else:
            out_df2["Prekybos centras"] = out_df2["Prekybos centras"].apply(
                lambda x: x.strip() if isinstance(x, str) and x.strip() else "—"
            )
            grp2 = (
                out_df2.groupby("Prekybos centras", dropna=False)["Suma (€)"]
                .sum()
                .sort_values(ascending=False)
                .reset_index()
            )
            grp2 = grp2.rename(columns={"Suma (€)": "Suma"})
            grp2 = grp2.set_index("Prekybos centras")
            st.subheader("Išlaidos pagal prekybos centrą (€)")
            st.bar_chart(grp2)

    # 3) Mėnesio pajamos vs. išlaidos (visa laiko juosta)
    st.markdown("---")
    st.subheader("Mėnesio srautas: Pajamos vs. Išlaidos")
    tmp = df.copy()
    tmp["Data_dt"] = pd.to_datetime(tmp["Data"], errors="coerce")
    tmp = tmp.dropna(subset=["Data_dt"])
    if tmp.empty:
        st.caption("Pasirinktame filtre nėra duomenų.")
        return
    tmp["Mėnuo"] = tmp["Data_dt"].dt.to_period("M").astype(str)
    pivot = tmp.pivot_table(
        index="Mėnuo", columns="Tipas", values="Suma (€)", aggfunc="sum", fill_value=0.0
    ).sort_index()
    st.line_chart(pivot)

def render_export():
    st.markdown("### Eksportas")
    df = _ensure_columns(st.session_state.budget_df)
    if df.empty:
        st.caption("Nėra ką eksportuoti.")
        return

    # CSV
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Atsisiųsti CSV",
        data=csv_bytes,
        file_name=f"biudzetas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    # Excel (reikia openpyxl)
    try:
        with BytesIO() as output:
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name="Biudžetas", index=False)
            st.download_button(
                "⬇️ Atsisiųsti Excel",
                data=output.getvalue(),
                file_name=f"biudzetas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
    except Exception:
        st.caption("Excel eksportui reikia `openpyxl`. Įtrauk į requirements.txt, jei mygtukas neveikia.")

# ------------------------------------------------------------
# 7) App paleidimas
# ------------------------------------------------------------
def main():
    _init_auth_state()

    if not st.session_state.auth["is_authenticated"]:
        render_auth_ui()
        return

    _init_budget_state()

    # Mėnesių sąrašas ir viršutinė juosta
    months = available_months(st.session_state.budget_df)
    if "selected_month" not in st.session_state:
        st.session_state.selected_month = months[-1]
    render_topbar(months)

    # Pagrindinis išdėstymas: kairė (nustatymai, forma, eksportas), dešinė (suvestinė, lentelė, diagramos)
    with st.container():
        left, right = st.columns([1.05, 1.95])

        with left:
            render_balance_settings()
            st.markdown("---")
            render_budget_form()
            st.markdown("---")
            render_export()

        with right:
            render_month_header_and_metrics()
            st.markdown("---")
            render_budget_table_and_summary()
            st.markdown("---")
            render_charts()

if __name__ == "__main__":
    main()

 
   

