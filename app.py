import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
import uuid

# -------------------------
# KONFIGŪRACIJA
# -------------------------
st.set_page_config(page_title="Asmeninis biudžetas", layout="wide")

DATA_FILE = "data.csv"

# -------------------------
# USER
# -------------------------
if "user_id" not in st.session_state:
    st.session_state.user_id = "sigita"  # gali pakeisti į loginą vėliau

USER_ID = st.session_state.user_id

# -------------------------
# DUOMENYS
# -------------------------
def load_data():
    try:
        df = pd.read_csv(DATA_FILE, parse_dates=["data"])
    except FileNotFoundError:
        df = pd.DataFrame(
            columns=[
                "id", "user_id", "data",
                "tipas", "kategorija", "suma", "komentaras"
            ]
        )
    return df

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

df = load_data()
df_user = df[df["user_id"] == USER_ID].copy()

# -------------------------
# NAUJAS ĮRAŠAS
# -------------------------
st.sidebar.header("➕ Naujas įrašas")

with st.sidebar.form("new_entry"):
    data = st.date_input("Data", date.today())
    tipas = st.selectbox("Tipas", ["Pajamos", "Išlaidos"])
    kategorija = st.text_input("Kategorija")
    suma = st.number_input("Suma (€)", step=1.0)
    komentaras = st.text_input("Komentaras")
    submitted = st.form_submit_button("Pridėti")

    if submitted:
        new_row = {
            "id": str(uuid.uuid4()),
            "user_id": USER_ID,
            "data": pd.to_datetime(data),
            "tipas": tipas,
            "kategorija": kategorija,
            "suma": float(suma),
            "komentaras": komentaras
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        save_data(df)
        st.rerun()

# -------------------------
# FILTRAI
# -------------------------
st.header("📊 Biudžeto analizė")

df_user["year"] = df_user["data"].dt.year
df_user["month"] = df_user["data"].dt.to_period("M").astype(str)

period_type = st.selectbox(
    "Laikotarpis",
    ["Visas laikotarpis", "Metai", "Mėnesiai"]
)

if period_type == "Metai":
    year = st.selectbox("Metai", sorted(df_user["year"].unique()))
    df_f = df_user[df_user["year"] == year]

elif period_type == "Mėnesiai":
    month = st.selectbox("Mėnuo", sorted(df_user["month"].unique()))
    df_f = df_user[df_user["month"] == month]

else:
    df_f = df_user.copy()

# -------------------------
# KPI
# -------------------------
pajamos = df_f[df_f["tipas"] == "Pajamos"]["suma"].sum()
islaidos = df_f[df_f["tipas"] == "Išlaidos"]["suma"].sum()
balansas = pajamos - islaidos

c1, c2, c3 = st.columns(3)
c1.metric("💰 Pajamos", f"{pajamos:.2f} €")
c2.metric("💸 Išlaidos", f"{islaidos:.2f} €")
c3.metric("📈 Balansas", f"{balansas:.2f} €")

# -------------------------
# GRAFIKAI
# -------------------------
st.subheader("📈 Pajamos vs Išlaidos")

df_bar = (
    df_f.groupby(["month", "tipas"])["suma"]
    .sum()
    .reset_index()
)

fig_bar = px.bar(
    df_bar,
    x="month",
    y="suma",
    color="tipas",
    barmode="group"
)
st.plotly_chart(fig_bar, use_container_width=True)

# -------------------------
# KATEGORIJOS (SUMOS)
# -------------------------
st.subheader("📊 Išlaidos pagal kategorijas (€)")

df_cat = (
    df_f[df_f["tipas"] == "Išlaidos"]
    .groupby("kategorija")["suma"]
    .sum()
    .reset_index()
)

fig_cat = px.pie(
    df_cat,
    values="suma",
    names="kategorija",
    hole=0.4
)
st.plotly_chart(fig_cat, use_container_width=True)

# -------------------------
# BALANSO DINAMIKA
# -------------------------
st.subheader("📉 Balanso kitimas")

df_balance = df_user.sort_values("data").copy()
df_balance["signed"] = df_balance.apply(
    lambda r: r["suma"] if r["tipas"] == "Pajamos" else -r["suma"],
    axis=1
)
df_balance["balansas"] = df_balance["signed"].cumsum()

fig_balance = px.line(
    df_balance,
    x="data",
    y="balansas"
)
st.plotly_chart(fig_balance, use_container_width=True)

# -------------------------
# ĮRAŠŲ LENTELĖ (EDIT / DELETE)
# -------------------------
st.subheader("🗑️ Redaguoti / trinti įrašus")

for _, r in df_f.sort_values("data", ascending=False).iterrows():
    with st.expander(f"{r['data'].date()} | {r['tipas']} | {r['suma']} €"):
        col1, col2 = st.columns(2)

        with col1:
            if st.button("❌ Trinti", key=f"del_{r['id']}"):
                df = df[df["id"] != r["id"]]
                save_data(df)
                st.rerun()

        with col2:
            with st.form(f"edit_{r['id']}"):
                new_sum = st.number_input(
                    "Suma",
                    value=float(r["suma"]),
                    key=f"s_{r['id']}"
                )
                new_cat = st.text_input(
                    "Kategorija",
                    value=r["kategorija"],
                    key=f"k_{r['id']}"
                )
                save = st.form_submit_button("💾 Išsaugoti")

                if save:
                    df.loc[df["id"] == r["id"], "suma"] = new_sum
                    df.loc[df["id"] == r["id"], "kategorija"] = new_cat
                    save_data(df)
                    st.rerun()
