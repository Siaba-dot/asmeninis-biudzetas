# ======================================================
# TABLE: edit + delete
# ======================================================
st.subheader("📋 Įrašai (redagavimas / trynimas)")

# --- PRIDĖTA: scroll konteinerio stilius (tik UI) ---
st.markdown("""
<style>
.records-scrollbox {
    max-height: 420px;      /* ~10 įrašų (uždaryti expanderiai). Jei reikia – koreguok */
    overflow-y: auto;
    padding-right: 10px;    /* kad scrollbar neužliptų ant turinio */
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 10px;
    padding: 8px;
}
</style>
""", unsafe_allow_html=True)

if df_f.empty:
    st.info("Pagal pasirinktus filtrus įrašų nėra.")
else:
    # --- PRIDĖTA: atidarom scroll konteinerį ---
    st.markdown('<div class="records-scrollbox">', unsafe_allow_html=True)

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

    # --- PRIDĖTA: uždarom scroll konteinerį ---
    st.markdown('</div>', unsafe_allow_html=True)
