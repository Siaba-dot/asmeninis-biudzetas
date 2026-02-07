# =========================
# Login
# =========================
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔐 Prisijungimas")
    email = st.text_input("El. paštas")
    password = st.text_input("Slaptažodis", type="password")
    
    login_button = st.button("Prisijungti")
    if login_button:
        if email and password and login(email, password):
            st.session_state["authenticated"] = True
            st.session_state["email"] = email
        else:
            st.error("❌ Neteisingi duomenys")
    st.stop()

st.success(f"Prisijungta kaip **{st.session_state['email']}**")
if st.button("🚪 Atsijungti"):
    logout()

# =========================
# Pagrindiniai KPI
# =========================
months = fetch_months()
if months:
    selected_month = st.selectbox("Pasirink mėnesį", months, format_func=ym_label)
    df_month = fetch_month_df(selected_month)

    if not df_month.empty:
        s_inc = df_month.loc[df_month["tipas"]=="Pajamos","suma_eur"].sum()
        s_exp = df_month.loc[df_month["tipas"]=="Išlaidos","suma_eur"].sum()
        s_bal = s_inc - s_exp
        st.subheader("📊 Suvestinė")
        c1, c2, c3 = st.columns(3)
        c1.metric("Pajamos", money(s_inc))
        c2.metric("Išlaidos", money(s_exp))
        c3.metric("Balansas", money(s_bal))
else:
    st.info("Nėra duomenų")
