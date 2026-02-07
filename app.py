# app.py
import streamlit as st
from datetime import date, timedelta
from supabase import Client
from supabase_client import get_supabase, current_user
from auth import render_auth_ui, sign_out
import pandas as pd

# -------------------------
# Puslapio nustatymai
# -------------------------
st.set_page_config(page_title="Asmeninis biudžetas", layout="wide")


# -------------------------
# Naudingos funkcijos
# -------------------------
def format_eur_lt(value: float) -> str:
    """
    LT/ES draugiškas valiutos formatas:
    - tūkstančių skyriklis: tarpas
    - dešimtainis kablelis: kablelis
    Pvz.: 1 234,50 €
    """
    try:
        s = f"{float(value):,.2f}"
    except Exception:
        s = "0.00"
    s = s.replace(",", " ").replace(".", ",")
    return f"{s} €"


def insert_transaction(
    supabase: Client,
    user_id: str,
    ttype: str,
    amount: float,
    category: str,
    note: str,
    txn_date_val: date,
):
    payload = {
        "user_id": user_id,
        "type": ttype,
        "amount": round(float(amount), 2),  # DB stulpelis numeric(12,2)
        "category": (category or "").strip() or "Uncategorized",
        "note": (note or "").strip() or None,
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
    return res.data or []


def delete_transaction(supabase: Client, row_id: str):
    return supabase.table("transactions").delete().eq("id", row_id).execute()


def render_rows_with_delete(rows: list[dict], supabase: Client):
    """
    Rodo sąrašą su eilutiniais Delete mygtukais.
    Grąžina True, jei kas nors buvo ištrinta (persiųsim refresh).
    """
    deleted_any = False
    for r in rows:
        with st.container(border=True):
            c1, c2, c3, c4, c5, c6 = st.columns([1, 1, 1, 1, 3, 0.5])
            c1.write(str(r.get("txn_date", "")))
            c2.write("🟢 Pajamos" if r.get("type") == "income" else "🔴 Išlaidos")
            c3.write(format_eur_lt(r.get("amount", 0.0)))
            c4.write(r.get("category", ""))
            c5.write(r.get("note") or "")

            btn_key = f"del_{r.get('id')}"
            if c6.button("🗑️", key=btn_key, help="Trinti šį įrašą"):
                try:
                    delete_transaction(supabase, r["id"])
                    st.success("Įrašas ištrintas")
                    deleted_any = True
                except Exception as e:
                    st.error(f"Nepavyko ištrinti: {e}")
    return deleted_any


# -------------------------
# Supabase klientas
# -------------------------
supabase = get_supabase()

# -------------------------
# Auth „siena“
# -------------------------
is_authed = render_auth_ui(supabase)
if not is_authed:
    st.stop()

# Patikimai gauname user'į. Jei nėra — pilnas logout ir sustabdymas.
user = current_user(supabase)
if not user:
    # Saugo nuo „pusiau atsijungus“ būsenų
    sign_out(supabase)
    st.rerun()
    st.stop()

# -------------------------
# Antraštė ir Atsijungimas
# -------------------------
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
        st.stop()

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
        txn_date_val = st.date_input("Data", value=date.today(), format="YYYY/MM/DD")
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
            st.rerun()
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
    f_from = st.date_input("Nuo", value=default_from, key="f_from", format="YYYY/MM/DD")
with fc2:
    f_to = st.date_input("Iki", value=default_to, key="f_to", format="YYYY/MM/DD")
with fc3:
    f_type = st.selectbox("Tipas", options=["visi", "income", "expense"], index=0, key="f_type")
with fc4:
    f_category = st.text_input("Kategorija (ieškoti)", placeholder="pvz.: %maistas%", key="f_category")
with fc5:
    reload_btn = st.button("Atnaujinti", use_container_width=True)

# Valdomas persikrovimas po įterpimo ar „Atnaujinti“
st.session_state["refresh_key"] = st.session_state.get("refresh_key", 0)
if reload_btn:
    st.session_state["refresh_key"] += 1

_ = st.session_state["refresh_key"]  # priklausomybė Streamlit

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

# -------------------------
# Atvaizdavimas + suvestinės
# -------------------------
if rows:
    # Suvestinės
    try:
        df = pd.DataFrame(rows)
        total_income = float(df.loc[df["type"] == "income", "amount"].sum()) if "type" in df and "amount" in df else 0.0
        total_expense = float(df.loc[df["type"] == "expense", "amount"].sum()) if "type" in df and "amount" in df else 0.0
    except Exception:
        total_income = sum(float(r.get("amount", 0.0)) for r in rows if r.get("type") == "income")
        total_expense = sum(float(r.get("amount", 0.0)) for r in rows if r.get("type") == "expense")

    balance = total_income - total_expense

    s1, s2, s3 = st.columns(3)
    s1.metric("Pajamos", format_eur_lt(total_income))
    s2.metric("Išlaidos", format_eur_lt(total_expense))
    s3.metric("Balansas", format_eur_lt(balance))

    st.caption("Naujausi įrašai")
    got_deleted = render_rows_with_delete(rows, supabase)
    if got_deleted:
        st.session_state["refresh_key"] += 1
        st.rerun()
else:
    st.info("Įrašų nerasta pagal pasirinktus filtrus.")
