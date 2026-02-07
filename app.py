import streamlit as st
from dataclasses import dataclass
from datetime import date
from typing import List, Dict, Optional

# ============
# PUSLAPIO NUSTATYMAI (kompaktiškas, tamsus)
# ============
st.set_page_config(
    page_title="Asmeninis biudžetas",
    page_icon="💶",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Minimalios paraštės + tamsi neon stilistika
st.markdown(
    """
    <style>
    :root {
        --bg: #0f1226;
        --bg-2: #15183a;
        --text: #e9e9f1;
        --muted: #a1a6d3;
        --neon-1: #7affb2; /* žalsvai neon */
        --neon-2: #8b5cf6; /* violet neon */
        --warn: #ffd166;
        --danger: #ff5c7a;
    }
    html, body, [data-testid="stAppViewContainer"] {
        background: var(--bg);
        color: var(--text);
    }
    /* Kompaktiškas turinio konteineris */
    .block-container {
        padding-top: 0.6rem !important;
        padding-bottom: 0.6rem !important;
        max-width: 1100px !important;
    }
    /* Antraštės */
    h1, h2, h3 {
        color: var(--text);
        letter-spacing: .3px;
    }
    /* Topbar kortelė */
    .topbar {
        background: linear-gradient(135deg, rgba(139,92,246,0.18), rgba(122,255,178,0.08));
        border: 1px solid rgba(139,92,246,0.35);
        border-radius: 12px;
        padding: .6rem .8rem;
        box-shadow: 0 0 0 1px rgba(122,255,178,0.15) inset, 0 8px 24px rgba(0,0,0,0.35);
    }
    /* Label'ai ir select'ai kompaktiški */
    label, .stSelectbox label, .stRadio label {
        color: var(--muted) !important;
        font-weight: 500 !important;
        margin-bottom: .2rem !important;
    }
    .stSelectbox div[data-baseweb="select"] > div {
        background: var(--bg-2) !important;
        border: 1px solid rgba(139,92,246,0.4) !important;
        border-radius: 10px !important;
    }
    .stSelectbox div[data-baseweb="select"] span {
        color: var(--text) !important;
    }
    /* Skyrikliai */
    hr {
        border: none;
        height: 1px;
        background: linear-gradient(to right, rgba(139,92,246,.35), rgba(122,255,178,.25));
        margin: .6rem 0 .8rem 0;
    }
    /* Mažesni pranešimai */
    .stAlert {
        border-radius: 10px !important;
        border: 1px solid rgba(139,92,246,0.35) !important;
        background: rgba(139,92,246,0.08) !important;
    }
    /* Mažesni tarpai tarp stulpelių */
    .row-compact > div {
        padding-right: .35rem !important;
        padding-left: .35rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============
# PAGALBINĖ LOGIKA: LT mėnesių pavadinimai, raktai ir etiketės
# ============
LT_MONTHS = [
    "Sausis", "Vasaris", "Kovas", "Balandis", "Gegužė", "Birželis",
    "Liepa", "Rugpjūtis", "Rugsėjis", "Spalis", "Lapkritis", "Gruodis"
]

def month_key_from_ym(year: int, month: int) -> str:
    """Grąžina stabilų raktą YYYY-MM (pvz., 2026-02)."""
    return f"{year:04d}-{month:02d}"

def month_label_lt(key: str) -> str:
    """Paverčia 'YYYY-MM' į 'YYYY m. Mėnuo' (LT)."""
    y, m = key.split("-")
    m_i = int(m)
    return f"{y} m. {LT_MONTHS[m_i-1]}"

def build_months_range(last_n: int = 18, include_current: bool = True) -> List[str]:
    """Sukuria sąrašą raktų 'YYYY-MM' nuo (dabar - last_n-1) iki dabartinio (arba iki praeito)."""
    today = date.today()
    y = today.year
    m = today.month
    if not include_current:
        # eiti vienu atgal
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    keys = []
    for i in range(last_n):
        yy = y
        mm = m - (last_n - 1 - i)
        while mm <= 0:
            yy -= 1
            mm += 12
        keys.append(month_key_from_ym(yy, mm))
    return keys

# ============
# ATSARGINIS GUARD'AS SESIJOS REIKŠMEI
# ============
def ensure_session_value_in_options(session_key: str, options: List[str], default_value: Optional[str] = None) -> None:
    """
    Garantuoja, kad st.session_state[session_key] egzistuoja ir yra tarp options.
    Jei ne – nustato į default_value (arba options[0], jei default_value nepaduotas).
    """
    if not options:
        return
    if default_value is None:
        default_value = options[0]
    if session_key not in st.session_state:
        st.session_state[session_key] = default_value
    if st.session_state[session_key] not in options:
        st.session_state[session_key] = default_value

# ============
# TOPBAR'AS: SAUGUS, DINAMIŠKAS SELECTBOX
# ============
def render_topbar(months: List[str], *, title: str = "Mėnuo", state_key: str = "selected_month_key") -> str:
    """
    months: sąrašas stabilių raktų 'YYYY-MM'.
    state_key: sesijos raktas, kuriame laikome pasirinktą mėnesį (kaip 'YYYY-MM').

    Grąžina pasirinktą 'YYYY-MM'.
    """
    if not months:
        st.warning("Nėra galimų mėnesių.")
        return ""

    # 1) Užtikriname, kad sesijoje yra galiojanti reikšmė
    ensure_session_value_in_options(state_key, months, default_value=months[-1])  # default – naujausias paskutinis

    # 2) Apskaičiuojame indeksą pagal sesijos reikšmę
    try:
        idx = months.index(st.session_state[state_key])
    except ValueError:
        idx = len(months) - 1

    # 3) Žmogiškos etiketės
    labels: Dict[str, str] = {k: month_label_lt(k) for k in months}

    # 4) Rodymas: naudojame atskirą widget key, kad nekiltų Streamlit serializacijos konfliktas
    widget_key = f"{state_key}__widget"
    selected_key = st.selectbox(
        label=title,
        options=months,
        index=idx,
        format_func=lambda k: labels.get(k, k),
        key=widget_key,
        help="Pasirinkite mėnesį. Sąrašas saugomas kaip stabilūs 'YYYY-MM' raktai.",
    )

    # 5) Suvedame atgal į stabilų sesijos raktą (jei vartotojas pakeitė)
    if selected_key != st.session_state[state_key]:
        st.session_state[state_key] = selected_key

    return selected_key

# ============
# DEMO: DINAMINIAI FILTRAI (parodo, kad selectbox nekrenta keičiantis options)
# ============
@dataclass
class FilterState:
    tik_einami_metai: bool = False
    paskutiniu_men: int = 18

def sidebar_filters() -> FilterState:
    with st.sidebar:
        st.header("⚙️ Filtrai")
        tik_einami = st.checkbox("Rodyti tik einamuosius metus", value=False, help="Demonstracija: dinamiškai pakeičia 'options'")
        paskutiniu_men = st.slider("Rodyti paskutinių mėnesių skaičių", 6, 36, 18, 1)
        st.caption("Keiskite filtrus ir įsitikinkite, kad `selectbox` nekristų su ValueError.")
        return FilterState(tik_einami_metai=tik_einami, paskutiniu_men=paskutiniu_men)

# ============
# PAGRINDINIS TURINYS
# ============
def main():
    st.title("💶 Asmeninis biudžetas")

    # Filtrai (demonstraciniai – keičia options sąrašą)
    filt = sidebar_filters()

    # Paruošiame mėnesių sąrašą
    all_months = build_months_range(last_n=filt.paskutiniu_men, include_current=True)

    if filt.tik_einami_metai:
        y = date.today().year
        months = [k for k in all_months if k.startswith(f"{y}-")]
        # Jei po filtravimo nieko neliko, grįžtam prie viso sąrašo (kad nebūtų tuščia)
        months = months or all_months
    else:
        months = all_months

    # TOPBAR kortelė
    with st.container():
        st.markdown('<div class="topbar">', unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1.2, 1, 1], gap="small")
        with c1:
            selected_month = render_topbar(months, title="Mėnuo", state_key="selected_month_key")
        with c2:
            st.metric("Rodomų mėnesių sk.", len(months))
        with c3:
            st.metric("Pasirinktas", month_label_lt(selected_month) if selected_month else "—")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<hr/>", unsafe_allow_html=True)

    # Turinys – čia demonstruojame, kad pasirinkimas gyvas ir stabilus
    st.subheader("📊 Suvestinė")
    if not selected_month:
        st.info("Pasirinkite mėnesį viršuje.")
        return

    st.write(
        f"**Pasirinktas laikotarpis:** `{selected_month}`  →  **{month_label_lt(selected_month)}**"
    )

    # Čia dėtum savo ataskaitas / grafikus / lenteles pagal 'selected_month'
    # Pvz., imituojame apkaičiuotą biudžeto suvestinę:
    st.markdown("**Biudžeto (demo) suvestinė**")
    colA, colB, colC, colD = st.columns(4)
    colA.metric("Planas", "1 500,00 €")
    colB.metric("Faktas", "1 430,25 €")
    colC.metric("Skirtumas", "+69,75 €", delta="+4.65%")
    colD.metric("Likę", "420,00 €", delta="-180,00 €")

    # Debug blokas (jei reikės diagnozei)
    with st.expander("🧪 Debug (vidinė informacija)"):
        st.write("`months` sąrašas:", months)
        st.write("`selected_month_key` sesijoje:", st.session_state.get("selected_month_key"))
        st.write("Ar sesijos reikšmė yra tarp options?:", st.session_state.get("selected_month_key") in months)

if __name__ == "__main__":
    main()
