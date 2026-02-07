# app.py
import streamlit as st
from datetime import date, timedelta
from supabase import Client
from supabase_client import get_supabase, current_user
from auth import render_auth_ui, sign_out
import pandas as pd

st.set_page_config(page_title="Asmeninis biudžetas", layout="wide")


# -------------------------
# Helperiai
# -------------------------
def insert_transaction(supabase: Client, user_id: str, ttype: str, amount: float, category: str, note: str, txn_date_val: date):
    payload = {
        "user_id": user_id,
        "type": ttype,
        "amount": round(float(amount), 2),
        "category": category.strip() if category else "Uncategorized",
        "note": note.strip() if note else None,
        "txn_date": str(txn_date_val),
    }
    res = supabase.table("transactions").insert(payload).execute()
    return res


def fetch_transactions(
    supabase: Client,
    user_id: str,
    date_from: date | None = None,
    date_to: date | None = None,
    ttype: str | None = None,
    category: str | None = None,
):
    q = supabase.table("transactions").select("*").eq("user_id", user_id)

    if date_from:
        q = q.gte("txn_date", str(date_from))
    if date_to:
        q = q.lte("txn_date", str(date_to))
    if ttype and ttype in ("income", "expense"):
        q = q.eq("type", ttype)
    if category and category.strip():
        q = q.ilike("category", category.strip())

    q = q.order("txn_date", desc=True).order("created_at", desc=True)
    res = q.execute()
    data = res.data or []
    return data


def delete_transaction(supabase: Client, row_id: str):
    return supabase.table("transactions").delete().eq("id", row_id).execute()


# -------------------------
# App
# -------------------------
supabase = get_supabase()

# Auth siena
is_authed = render_auth_ui(supabase)
if not is_authed:
    st.stop()

user = current_user(supabase)
if not user:
    st.warning("Sesija pasibaigė. Prisijunk iš naujo.")
    st.rerun()

# Header
left, right = st.columns([1, 1])
with left:
    st.title("Asmeninis biudžetas")
    st.caption(f"Prisijungta kaip: **{user.email}**")
with right:
    st.write("")
    st.write("")
    if st.button("Atsijungti", use_container_width=True):
        sign_out(supabase)
        st.rerun()

st.divider()

# -------------------------
# Įvedimo forma (CREATE)
# -------------------------
st.subheader("➕ Pridėti įrašą")

with st.form("add_txn", clear_on_submit=True):
    c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
    with c1:
        ttype = st.selectbox("Tipas", ["expense", "income"], index=0)
    with c2:
        amount = st.number_input("Suma", min_value=0.00, step=0.10, format="%.2f")
    with c3:
        txn_date_val = st.date_input("Data", value=date.today())
    with c4:
        category = st.text_input("Kategorija", placeholder="Pvz.: Maistas, Transportas, Atlyginimas")
    note = st.text_input("Pastaba", placeholder="(nebūtina)")
    submitted = st.form_submit_button("Išsaugoti", use_container_width=True)

if submitted:
    if amount <= 0:
        st.error("Suma turi būti > 0.")
    else:
        try:
            insert_transaction(supabase, user.id, ttype, amount, category, note, txn_date_val)
            st.success("Įrašas pridėtas ✅")
            st.session_state["refresh_key"] = st.session_state.get("refresh_key", 0) + 1
        except Exception as e:
            st.error(f"Nepavyko įrašyti: {e}")

st.divider()

# -------------------------
# Filtrai + sąrašas (READ)
# -------------------------
st.subheader("📋 Įrašų sąrašas")

# Numatyti filtrai: paskutinės 30 dienų
default_from = date.today() - timedelta(days=30)
default_to = date.today()

fc1, fc2, fc3, fc4, fc5 = st.columns([1, 1, 1, 1, 1])
with fc1:
    f_from = st.date_input("Nuo", value=default_from, key="f_from")
with fc2:
    f_to = st.date_input("Iki", value=default_to, key="f_to")
with fc3:
    f_type = st.selectbox("Tipas", options=["visi", "income", "expense"], index=0, key="f_type")
with fc4:
    f_category = st.text_input("Kategorija (ieškoti)", placeholder="pvz.: %maistas%", key="f_category")
with fc5:
    reload_btn = st.button("Atnaujinti", use_container_width=True)

# Kad lentelė persikrautų po įterpimo ar „Atnaujinti“
st.session_state["refresh_key"] = st.session_state.get("refresh_key", 0)
if reload_btn:
    st.session_state["refresh_key"] += 1

_ = st.session_state["refresh_key"]  # prikabinam, kad Streamlit matytų priklausomybę

ttype_filter = None if f_type == "visi" else f_type
category_filter = f_category if f_category else None

try:
    rows = fetch_transactions(
        supabase,
        user_id=user.id,
        date_from=f_from,
        date_to=f_to,
        ttype=ttype_filter,
        category=category_filter,
    )
except Exception as e:
    rows = []
    st.error(f"Nepavyko nuskaityti įrašų: {e}")

# Rodom lentelę
if rows:
    df = pd.DataFrame(rows)
    # tvarkingi stulpeliai rodyme
    show_cols = ["txn_date", "type", "amount", "category", "note", "created_at", "id"]
    df = df[[c for c in show_cols if c in df.columns]].copy()

    # Suvestinės juosta
    total_income = float(df.loc[df["type"] == "income", "amount"].sum()) if "type" in df and "amount" in df else 0.0
    total_expense = float(df.loc[df["type"] == "expense", "amount"].sum()) if "type" in df and "amount" in df else 0.0
    balance = total_income - total_expense

    s1, s2, s3 = st.columns(3)
    s1.metric("Pajamos", f"{total_income:,.2f} €")
    s2.metric("Išlaidos", f"{total_expense:,.2f} €")
    s3.metric("Balansas", f"{balance:,.2f} €")

    st.dataframe(df.drop(columns=["id"]), use_container_width=True, hide_index=True)

    # Paprastas trynimas per ID (įvesk ID iš df; vėliau padarysim mygtuką eilutėje)
    with st.expander("🗑️ Ištrinti įrašą (pagal ID)"):
        del_id = st.text_input("Įvesk įrašo ID (iš lentelės)", placeholder="uuid")
        if st.button("Trinti", type="primary"):
            if del_id.strip():
                try:
                    delete_transaction(supabase, del_id.strip())
                    st.success("Įrašas ištrintas")
                    st.session_state["refresh_key"] += 1
                    st.rerun()
                except Exception as e:
                    st.error(f"Nepavyko ištrinti: {e}")
            else:
                st.warning("Įvesk teisingą ID.")
else:
    st.info("Įrašų nerasta pagal pasirinktus filtrus.")
