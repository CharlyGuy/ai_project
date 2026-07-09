"""
app.py — FightStrategist AI · UFC Insights Edition v2
------------------------------------------------------
Interface Streamlit "broadcast night" en 4 onglets :
  📋 Tale of the Tape (portraits photo + radar Plotly)
  🤖 Analyse Agent (live trace + rapport + baseline)
  ⚔️ Fight Simulator 3D (timeline play-by-play rejouée par le moteur Three.js)
  🏆 Classement ELO (rating dynamique du roster)

Sidebar : config API, Create-a-Fighter (combattant custom en session),
encart Méthodologie (honnêteté statistique).
"""
import os
import random

import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

from src.agent_loop import run_agent_stream, run_baseline
from src.assets import render_fighter_portrait
from src.fight3d_loader import load_fight3d_html
from src.tools import (get_betting_odds, get_elo_ratings, get_fighter_stats,
                       list_fighters, register_custom_fighter,
                       simulate_fight_playbyplay, get_live_updates)
from src.assets import get_fighter_photo

load_dotenv()

st.set_page_config(page_title="FightStrategist AI — UFC Insights", page_icon="🥊", layout="wide")

# --------------------------------------------------------------------------
# PALETTE MODERNE + GLASSMORPHISM DESIGN 2025
# --------------------------------------------------------------------------
# Palette contemporaine: gradients doux + couleurs vibrantes
DARK_BG = "#0F0F1E"
GLASS_LIGHT = "rgba(255, 255, 255, 0.08)"
GLASS_DARK = "rgba(20, 20, 35, 0.6)"
ACCENT_RED = "#FF1744"
ACCENT_BLUE = "#00D9FF"
ACCENT_PURPLE = "#9C27B0"
ACCENT_GOLD = "#FFD700"
TEXT_PRIMARY = "#F5F7FA"
TEXT_SECONDARY = "#B0B8C1"
SUCCESS_GREEN = "#2ECC71"
WARNING_ORANGE = "#FF9500"

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Poppins:wght@700;800;900&display=swap');

    * {{ font-family: 'Inter', sans-serif; }}

    .stApp {{
        background: linear-gradient(135deg, {DARK_BG} 0%, #1A1A2E 100%);
        color: {TEXT_PRIMARY};
    }}

    .stMainBlock, .stMainBlock * {{
        color: {TEXT_PRIMARY};
        letter-spacing: 0.5px;
    }}

    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg, rgba(15, 15, 30, 0.95) 0%, rgba(25, 25, 45, 0.95) 100%) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.05) !important;
    }}

    [data-testid="stSidebar"] * {{ color: {TEXT_PRIMARY} !important; }}

    /* TITRE PRINCIPAL */
    .fs-title {{
        text-align: center;
        font-size: 3.5rem;
        font-weight: 900;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(120deg, {ACCENT_RED}, {ACCENT_GOLD}, {ACCENT_BLUE});
        background-size: 200% auto;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.5rem;
        letter-spacing: -1px;
        animation: gradient-shift 3s ease infinite;
    }}

    @keyframes gradient-shift {{
        0%, 100% {{ background-position: 0% center; }}
        50% {{ background-position: 100% center; }}
    }}

    .fs-subtitle {{
        text-align: center;
        color: {TEXT_SECONDARY} !important;
        margin-top: 0.5rem;
        font-size: 0.95rem;
        letter-spacing: 2px;
        font-weight: 500;
    }}

    /* VS BADGE */
    .vs-badge {{
        text-align: center;
        font-size: 2.8rem;
        font-weight: 900;
        color: {ACCENT_RED} !important;
        padding-top: 1rem;
        font-family: 'Poppins', sans-serif;
        text-shadow: 0 0 30px rgba(255, 23, 68, 0.4);
        letter-spacing: -1px;
    }}

    /* TRACE BOX - Agent execution trace */
    .trace-box {{
        background: {GLASS_DARK};
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-left: 4px solid {ACCENT_RED};
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 0.75rem;
        font-size: 0.95rem;
        transition: all 0.3s ease;
    }}

    .trace-box:hover {{
        background: {GLASS_LIGHT};
        border-left-color: {ACCENT_BLUE};
        transform: translateX(4px);
    }}

    .trace-box code {{
        color: {ACCENT_GOLD} !important;
        background: rgba(255, 215, 0, 0.1);
        padding: 2px 6px;
        border-radius: 4px;
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
    }}

    .trace-thought {{ border-left-color: {ACCENT_BLUE} !important; }}
    .trace-action {{ border-left-color: {ACCENT_GOLD} !important; }}
    .trace-observation {{ border-left-color: {SUCCESS_GREEN} !important; }}

    /* ACCENT_GOLD BOX - Premium predictions */
    .gold-box {{
        background: linear-gradient(135deg, rgba(255, 215, 0, 0.15) 0%, rgba(255, 23, 68, 0.08) 100%);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 215, 0, 0.3);
        border-radius: 16px;
        padding: 1.5rem;
        text-align: center;
        font-size: 1.2rem;
        font-weight: 700;
        color: {ACCENT_GOLD} !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        box-shadow: 0 8px 32px rgba(255, 215, 0, 0.1);
        transition: all 0.3s ease;
    }}

    .gold-box:hover {{
        transform: translateY(-2px);
        box-shadow: 0 12px 48px rgba(255, 215, 0, 0.15);
    }}

    /* GAMEPLAN CARD */
    .gameplan-card {{
        background: {GLASS_DARK};
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 1.5rem;
        height: 100%;
        border-top: 3px solid {ACCENT_RED};
        transition: all 0.3s ease;
    }}

    .gameplan-card:hover {{
        border-color: rgba(255, 255, 255, 0.2);
        background: {GLASS_LIGHT};
        transform: translateY(-4px);
        box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3);
    }}

    .gameplan-card.blue {{ border-top-color: {ACCENT_BLUE}; }}

    .gameplan-card h4 {{
        text-transform: uppercase;
        font-family: 'Poppins', sans-serif;
        font-size: 1.1rem;
        letter-spacing: 1px;
        margin-bottom: 1rem;
    }}

    .gameplan-card li {{
        margin-bottom: 0.6rem;
        line-height: 1.6;
        font-size: 0.95rem;
    }}

    /* BASELINE BOX - LLM seul */
    .baseline-box {{
        background: {GLASS_DARK};
        backdrop-filter: blur(10px);
        border: 1px dashed rgba(255, 149, 0, 0.4);
        border-radius: 12px;
        padding: 1.25rem;
        color: {TEXT_SECONDARY} !important;
        transition: all 0.3s ease;
    }}

    .baseline-box:hover {{
        border-color: rgba(255, 149, 0, 0.6);
    }}

    .value-tag {{
        color: {ACCENT_GOLD} !important;
        font-weight: 700;
        padding: 2px 8px;
        background: rgba(255, 215, 0, 0.1);
        border-radius: 4px;
    }}

    .methodo {{
        font-size: 0.85rem;
        color: {TEXT_SECONDARY} !important;
        line-height: 1.6;
    }}

    /* BUTTONS */
    .stButton > button {{
        background: linear-gradient(135deg, {ACCENT_RED} 0%, #FF5252 100%);
        color: white !important;
        border: none;
        border-radius: 10px;
        font-weight: 600;
        font-size: 0.95rem;
        padding: 0.6rem 1.5rem !important;
        transition: all 0.3s ease;
        box-shadow: 0 4px 16px rgba(255, 23, 68, 0.3);
    }}

    .stButton > button:hover {{
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(255, 23, 68, 0.4);
    }}

    /* SELECTBOX & INPUT */
    .stSelectbox, .stTextInput, .stSlider {{
        background: {GLASS_DARK} !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 10px !important;
    }}

    /* TABS */
    [role="tab"] {{
        border-radius: 10px 10px 0 0 !important;
        font-weight: 600;
        transition: all 0.3s ease;
    }}

    [role="tab"][aria-selected="true"] {{
        border-bottom-color: {ACCENT_RED} !important;
        color: {ACCENT_RED} !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<p class="fs-title">🥊 FightStrategist AI</p>', unsafe_allow_html=True)
st.markdown('<p class="fs-subtitle">UFC Insights · Scouting agentique · Monte-Carlo · Fight Simulator 3D</p>',
            unsafe_allow_html=True)

# --------------------------------------------------------------------------
# SIDEBAR : config + Create-a-Fighter + Méthodologie
# --------------------------------------------------------------------------
# Ré-enregistre les combattants custom de la session à chaque rerun
# (le registre du module tools est réinitialisé quand le process redémarre).
for _cf in st.session_state.get("custom_fighters", []):
    register_custom_fighter(_cf)

with st.sidebar:
    st.header("⚙️ Configuration")
    env_key_present = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if env_key_present:
        st.success("Clé API détectée (.env)")
        api_key_input = None
    else:
        api_key_input = st.text_input("Clé API Anthropic", type="password", help="sk-ant-...")
        st.caption("Ou définis ANTHROPIC_API_KEY dans un .env.")

    with st.expander("🛠️ Créer un combattant custom"):
        with st.form("create_fighter"):
            c_name = st.text_input("Nom", value="")
            c_wc = st.selectbox("Catégorie", ["Heavyweight", "Light Heavyweight", "Middleweight",
                                              "Welterweight", "Lightweight", "Featherweight", "Bantamweight"],
                                index=4)
            c_stance = st.selectbox("Stance", ["Orthodox", "Southpaw", "Switch"])
            c_height = st.slider("Taille (cm)", 160, 210, 180)
            c_reach = st.slider("Allonge (cm)", 160, 220, 183)
            c_acc = st.slider("Précision de frappe (%)", 30, 70, 50)
            c_slpm = st.slider("Frappes / min", 1.0, 8.0, 4.0, 0.5)
            c_td = st.slider("Takedowns / 15 min", 0.0, 7.0, 1.5, 0.5)
            c_tdd = st.slider("Défense takedown (%)", 40, 100, 70)
            c_ko = st.slider("Taux de KO (%)", 0, 90, 40)
            c_sub = st.slider("Taux de soumission (%)", 0, 70, 20)
            c_chin = st.slider("Menton (1-10)", 1, 10, 7)
            c_cardio = st.slider("Cardio (1-10)", 1, 10, 7)
            c_power = st.slider("Puissance (1-10)", 1, 10, 7)
            c_tags = st.multiselect("Style", ["Striker", "Lutteur", "Grappler", "Kickboxeur",
                                              "Contre-attaquant", "Pression", "Finisher"],
                                    default=["Striker"])
            if st.form_submit_button("Créer le combattant"):
                if c_name.strip():
                    cf = {
                        "name": c_name.strip(), "weight_class": c_wc, "stance": c_stance,
                        "height_cm": c_height, "reach_cm": c_reach,
                        "striking_accuracy_pct": float(c_acc), "strikes_landed_per_min": float(c_slpm),
                        "takedown_avg_per_15min": float(c_td), "takedown_defense_pct": float(c_tdd),
                        "ko_rate_pct": float(c_ko), "submission_rate_pct": float(c_sub),
                        "chin_durability": float(c_chin), "cardio_rating": float(c_cardio),
                        "power_rating": float(c_power), "style_tags": ", ".join(c_tags) or "Custom",
                    }
                    existing = [f for f in st.session_state.get("custom_fighters", [])
                                if f["name"].lower() != cf["name"].lower()]
                    st.session_state["custom_fighters"] = existing + [cf]
                    register_custom_fighter(cf)
                    st.success(f"« {cf['name']} » ajouté aux menus — testez-le en 3D et à l'analyse !")
                else:
                    st.error("Donne-lui un nom.")

    st.markdown("---")
    st.markdown("**📊 Méthodologie**")
    st.markdown(
        '<div class="methodo">'
        "· Les probabilités du rapport sont <b>CALCULÉES par Monte-Carlo</b> (500 combats simulés), "
        "pas estimées par le LLM — l'agent peut les ajuster d'au plus <b>±10 pts</b> en justifiant.<br>"
        "· <b>Anti-leakage</b> : l'agent ne voit que des données antérieures au combat simulé "
        "(stats, historiques, notes de scouting) — jamais l'issue.<br>"
        "· Données réalistes mais <b>figées à but pédagogique</b> ; photos © UFC / Wikimedia, usage académique.",
        unsafe_allow_html=True,
    )
    st.markdown("---")
    st.caption("**Modèle :** `claude-haiku-4-5` · **Stack :** SQLite · RAG ChromaDB+MiniLM · "
               "MCP · Reason→Act→Observe · Monte-Carlo · Three.js")

# --------------------------------------------------------------------------
# SÉLECTION DES COMBATTANTS
# --------------------------------------------------------------------------
fighters = list_fighters()

col_a, col_vs, col_b = st.columns([5, 1, 5])
with col_a:
    fighter_a = st.selectbox("🔵 Coin bleu", fighters, index=0, key="fighter_a")
with col_vs:
    st.markdown('<div class="vs-badge">VS</div>', unsafe_allow_html=True)
with col_b:
    fighter_b = st.selectbox("🔴 Coin rouge", fighters, index=1, key="fighter_b")

if fighter_a == fighter_b:
    st.warning("Choisis deux combattants différents.")
    st.stop()


def _get_api_key():
    return api_key_input or os.environ.get("ANTHROPIC_API_KEY")


def _implied_prob(name: str):
    odds = get_betting_odds(name)
    return odds.get("implied_probability_pct") if odds and "error" not in odds else None


# --------------------------------------------------------------------------
# ONGLETS
# --------------------------------------------------------------------------
tab_tape, tab_agent, tab_3d, tab_elo, tab_live = st.tabs(
    ["📋 Tale of the Tape", "🤖 Analyse Agent", "⚔️ Fight Simulator 3D", "🏆 Classement ELO", "🔴 Live Updates"])

# ============================ ONGLET 1 : TALE OF THE TAPE =================
with tab_tape:
    a, b = get_fighter_stats(fighter_a), get_fighter_stats(fighter_b)

    p1, pvs, p2 = st.columns([5, 1, 5])
    with p1:
        st.markdown(render_fighter_portrait(a, ACCENT_BLUE), unsafe_allow_html=True)
    with pvs:
        st.markdown('<div class="vs-badge">VS</div>', unsafe_allow_html=True)
    with p2:
        st.markdown(render_fighter_portrait(b, ACCENT_RED), unsafe_allow_html=True)

    st.markdown("")

    def radar_values(f: dict) -> list[float]:
        return [
            round(f["striking_accuracy_pct"] / 10, 1),
            round(min(10, f["takedown_avg_per_15min"] * 1.4 + f["submission_rate_pct"] / 20), 1),
            f["cardio_rating"],
            f["power_rating"],
            f["chin_durability"],
            round(f["takedown_defense_pct"] / 10, 1),
        ]

    axes = ["Striking", "Grappling", "Cardio", "Puissance", "Menton", "Défense TD"]
    fig = go.Figure()
    for f, color, fill in [(a, ACCENT_BLUE, "rgba(0, 217, 255, 0.25)"), (b, ACCENT_RED, "rgba(255, 23, 68, 0.25)")]:
        vals = radar_values(f)
        fig.add_trace(go.Scatterpolar(
            r=vals + vals[:1], theta=axes + axes[:1], name=f["name"],
            line=dict(color=color, width=2), fill="toself", fillcolor=fill,
        ))
    fig.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(range=[0, 10], gridcolor="#333", tickfont=dict(color="#888", size=9)),
            angularaxis=dict(gridcolor="#333", tickfont=dict(color="#ddd", size=12)),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(font=dict(color="#eee"), orientation="h", y=-0.1, x=0.5, xanchor="center"),
        margin=dict(l=60, r=60, t=30, b=30), height=420,
    )
    st.plotly_chart(fig, use_container_width=True)

    metrics = [
        ("Taille", "height_cm", "cm"), ("Allonge", "reach_cm", "cm"), ("Stance", "stance", ""),
        ("Précision de frappe", "striking_accuracy_pct", "%"),
        ("Frappes / min", "strikes_landed_per_min", ""),
        ("Takedowns / 15min", "takedown_avg_per_15min", ""),
        ("Défense takedown", "takedown_defense_pct", "%"),
        ("Taux de KO", "ko_rate_pct", "%"), ("Taux de soumission", "submission_rate_pct", "%"),
    ]
    for label, key, unit in metrics:
        m1, m2, m3 = st.columns([2, 5, 2])
        m1.markdown(f"<div style='font-size:1.05rem;font-weight:700'>{a.get(key, '—')}{unit}</div>",
                    unsafe_allow_html=True)
        m2.markdown(f"<div style='text-align:center;color:#9a9a9a'>{label}</div>", unsafe_allow_html=True)
        m3.markdown(f"<div style='text-align:right;font-size:1.05rem;font-weight:700'>{b.get(key, '—')}{unit}</div>",
                    unsafe_allow_html=True)
    st.caption(f"🔵 {a.get('style_tags', '')}  ·  🔴 {b.get('style_tags', '')}")

# ============================ ONGLET 2 : ANALYSE AGENT ====================
ICONS = {"thought": "🧠", "action": "⚙️", "observation": "👁️"}
LABELS = {"thought": "Pensée", "action": "Appel de l'outil", "observation": "Données récoltées"}
CSS_CLASS = {"thought": "trace-thought", "action": "trace-action", "observation": "trace-observation"}


def render_step(container, step: dict) -> None:
    kind = step["type"]
    if kind == "thought":
        body = step["text"]
    elif kind == "action":
        body = f"<code>{step['tool']}({step['input']})</code>"
    elif kind == "observation":
        body = f"<code>{str(step['output'])[:450]}</code>"
    else:
        return
    label = LABELS[kind] + (f" [{step['tool']}]" if kind == "action" else "")
    container.markdown(
        f'<div class="trace-box {CSS_CLASS[kind]}"><b>{ICONS[kind]} {label}</b> — {body}</div>',
        unsafe_allow_html=True,
    )


def render_final_report(report: dict, name_a: str, name_b: str) -> None:
    st.subheader("🏆 Rapport Stratégique — FightStrategist AI")

    prob_a = float(report.get("victory_probability_a", 50))
    prob_b = float(report.get("victory_probability_b", 50))
    total = prob_a + prob_b if (prob_a + prob_b) > 0 else 1
    prob_a, prob_b = 100 * prob_a / total, 100 * prob_b / total
    favorite, fav_prob, fav_color = (name_a, prob_a, ACCENT_BLUE) if prob_a >= prob_b else (name_b, prob_b, ACCENT_RED)

    # Convertir couleur hex en RGB pour la barre de probabilité
    def hex_to_rgba(hex_color, alpha=1):
        h = hex_color.lstrip('#')
        return f"rgba({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)}, {alpha})"

    color_a_rgb = hex_to_rgba(ACCENT_BLUE)
    color_b_rgb = hex_to_rgba(ACCENT_RED)

    st.markdown(f'<div class="gold-box">🥇 Prédiction : {favorite} · '
                f'{report.get("predicted_method", "N/A")}</div>', unsafe_allow_html=True)
    st.markdown("")

    # portraits photo autour de la barre de probabilité
    pc1, pc2, pc3 = st.columns([2, 6, 2])
    with pc1:
        st.markdown(render_fighter_portrait(get_fighter_stats(name_a), ACCENT_BLUE), unsafe_allow_html=True)
    with pc3:
        st.markdown(render_fighter_portrait(get_fighter_stats(name_b), ACCENT_RED), unsafe_allow_html=True)
    with pc2:
        bar_a = int(prob_a)
        st.markdown(
            f"""
            <div style="margin-top:55px;display:flex;height:44px;border-radius:8px;overflow:hidden;
                        font-weight:800;font-family:'Poppins', sans-serif;">
                <div style="width:{bar_a}%;background:{ACCENT_BLUE};display:flex;align-items:center;
                            justify-content:center; transition: all 0.5s ease;">{name_a} {prob_a:.0f}%</div>
                <div style="width:{100 - bar_a}%;background:{ACCENT_RED};display:flex;align-items:center;
                            justify-content:center; transition: all 0.5s ease;">{name_b} {prob_b:.0f}%</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        rows = []
        for name, ai_p in ((name_a, prob_a), (name_b, prob_b)):
            mkt = _implied_prob(name)
            if mkt is not None:
                edge = ai_p - mkt
                tag = "💰 VALUE" if edge >= 5 else ("⚠️ surcoté" if edge <= -5 else "≈ aligné")
                rows.append(f"<tr><td>{name}</td><td>{ai_p:.0f}%</td><td>{mkt:.0f}%</td>"
                            f"<td class='value-tag'>{edge:+.0f} pts · {tag}</td></tr>")
        if rows:
            st.markdown(
                "<table style='width:100%;margin-top:14px;font-size:0.95rem;'>"
                "<tr style='color:#9a9a9a'><th align=left>Combattant</th><th align=left>IA</th>"
                "<th align=left>Vegas (implicite)</th><th align=left>Edge</th></tr>"
                + "".join(rows) + "</table>",
                unsafe_allow_html=True,
            )

    g1, _ = st.columns([2, 3])
    with g1:
        gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=fav_prob,
            number={"suffix": "%", "font": {"color": fav_color, "size": 44}},
            title={"text": f"Confiance IA — {favorite}", "font": {"color": "#ddd", "size": 14}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": "#555", "tickfont": {"color": "#888"}},
                "bar": {"color": fav_color},
                "bgcolor": "#1a1a1d",
                "borderwidth": 1, "bordercolor": "#333",
                "threshold": {"line": {"color": ACCENT_GOLD, "width": 3}, "value": fav_prob},
            },
        ))
        gauge.update_layout(paper_bgcolor="rgba(0,0,0,0)", height=240,
                            margin=dict(l=30, r=30, t=50, b=10))
        st.plotly_chart(gauge, use_container_width=True)

    if report.get("vegas_analysis"):
        st.info("🎰 " + report["vegas_analysis"])
    st.info(report.get("summary", ""))

    c1, c2 = st.columns(2)
    for col, name, keys_field, plan_field, css in [
        (c1, name_a, "keys_to_victory_a", "game_plan_a", "blue"),
        (c2, name_b, "keys_to_victory_b", "game_plan_b", ""),
    ]:
        with col:
            keys = report.get(keys_field, []) or []
            keys_html = "".join(f"<li>🎯 {k}</li>" for k in keys)
            st.markdown(
                f"""<div class="gameplan-card {css}">
                    <h4>Game Plan — {name}</h4>
                    <p>{report.get(plan_field, '')}</p>
                    <ul style="list-style:none;padding-left:0;">{keys_html}</ul>
                </div>""",
                unsafe_allow_html=True,
            )


with tab_agent:
    col_agent, col_base = st.columns([3, 2])
    with col_agent:
        launch = st.button("🚀 Analyse Elite (agent + Monte-Carlo)", use_container_width=True, type="primary")
    with col_base:
        baseline = st.button("⚡ Baseline : LLM seul, sans tools", use_container_width=True,
                             help="Un unique appel LLM sans accès aux données — le contre-exemple pédagogique.")

    if baseline:
        if not _get_api_key():
            st.error("Aucune clé API Anthropic disponible (sidebar ou .env).")
        else:
            st.subheader("⚡ Baseline — un seul appel LLM, zéro tool")
            st.markdown(
                '<div class="baseline-box">⚠️ <b>Mode Hallucination :</b> les chiffres ci-dessous sont '
                "inventés par la mémoire du modèle. Il n'a accès ni à la base SQLite, ni aux notes de "
                "scouting, ni au simulateur Monte-Carlo — à comparer avec l'Analyse Elite où chaque "
                "affirmation est ancrée dans un tool call visible.</div>",
                unsafe_allow_html=True,
            )
            with st.spinner("Appel LLM unique en cours..."):
                try:
                    st.markdown(run_baseline(fighter_a, fighter_b, api_key=_get_api_key()))
                except Exception as exc:
                    st.error(f"Erreur pendant l'appel baseline : {exc}")

    if launch:
        if not _get_api_key():
            st.error("Aucune clé API Anthropic disponible (sidebar ou .env).")
        else:
            st.subheader("🔎 Live Trace de l'Agent — enquête en direct")
            trace_container = st.container()
            report = None
            with st.spinner("L'agent mène son enquête (5 phases)..."):
                try:
                    for step in run_agent_stream(fighter_a, fighter_b, api_key=_get_api_key()):
                        if step["type"] == "final":
                            report = step["report"]
                        else:
                            render_step(trace_container, step)
                except Exception as exc:
                    st.error(f"Erreur pendant l'exécution de l'agent : {exc}")

            if report:
                st.markdown("---")
                render_final_report(report, fighter_a, fighter_b)

# ============================ ONGLET 3 : FIGHT SIMULATOR 3D ===============
with tab_3d:
    cbtn, cseed = st.columns([3, 2])
    with cseed:
        random_seed = st.checkbox("🎲 Seed aléatoire (nouveau scénario à chaque simulation)", value=True)
        fixed_seed = None if random_seed else st.number_input("Seed", 0, 9999, 42)
    with cbtn:
        simulate = st.button("🎬 Simuler le combat", use_container_width=True, type="primary")

    if simulate:
        seed = random.randint(0, 99999) if random_seed else int(fixed_seed)
        st.session_state["fight3d"] = {
            "timeline": simulate_fight_playbyplay(fighter_a, fighter_b, seed=seed),
            "a": get_fighter_stats(fighter_a), "b": get_fighter_stats(fighter_b),
            "seed": seed,
        }

    sim = st.session_state.get("fight3d")
    if sim and sim["timeline"].get("events") and sim["a"].get("name") == get_fighter_stats(fighter_a).get("name") \
            and sim["b"].get("name") == get_fighter_stats(fighter_b).get("name"):
        components.html(load_fight3d_html(sim["timeline"], sim["a"], sim["b"]), height=780)

        res = sim["timeline"]["result"]
        st.markdown(f'<div class="gold-box">🏆 Résultat officiel : {res["winner_name"]} par '
                    f'{res["method"]} — Round {res["round"]} · {res["time"]} (seed {sim["seed"]})</div>',
                    unsafe_allow_html=True)

        sc1, sc2 = st.columns(2)
        with sc1:
            st.markdown("**🧑‍⚖️ Scorecards des juges**")
            if res["scorecards"]:
                header = f"| Round | {sim['timeline']['fighter_a']} | {sim['timeline']['fighter_b']} |\n|---|---|---|\n"
                st.markdown(header + "\n".join(
                    f"| R{c['round']} | {c['a']} | {c['b']} |" for c in res["scorecards"]))
            else:
                st.caption("Combat terminé avant la fin du premier round — pas de scorecard.")
        with sc2:
            st.markdown("**📈 Stats du combat**")
            sa, sb = res["stats_summary"]["a"], res["stats_summary"]["b"]
            st.markdown(
                f"| | {sim['timeline']['fighter_a']} | {sim['timeline']['fighter_b']} |\n|---|---|---|\n"
                f"| Frappes touchées | {sa['strikes_landed']} | {sb['strikes_landed']} |\n"
                f"| Takedowns | {sa['takedowns']} | {sb['takedowns']} |\n"
                f"| Contrôle au sol (s) | {sa['control_time_s']} | {sb['control_time_s']} |")

        st.caption("📊 Cette simulation est UN tirage parmi la distribution Monte-Carlo — la probabilité "
                   "affichée dans le rapport agent reste la référence statistique.")
    elif not sim:
        st.info("Sélectionnez vos combattants puis cliquez **🎬 Simuler le combat** — le moteur 3D rejoue "
                "la timeline générée par `simulate_fight_playbyplay` (lutteurs qui luttent, strikers qui frappent).")

# ============================ ONGLET 4 : CLASSEMENT ELO ===================
with tab_elo:
    elo = get_elo_ratings(fighter_a, fighter_b)
    m = elo.get("matchup", {})
    if m:
        e1, e2, e3 = st.columns(3)
        e1.metric(f"ELO — {fighter_a}", m["elo_a"])
        e2.metric("Delta du matchup", f"{m['delta']:+d}",
                  f"{m['elo_win_probability_a_pct']}% pour A (modèle ELO)")
        e3.metric(f"ELO — {fighter_b}", m["elo_b"])
        st.caption("Rappel : les combattants custom n'ont pas d'historique → ELO 1500 de base.")

    st.markdown("**Classement du roster** (K=32 · base 1500 · bonus finish ×1.25 · qualité d'opposition prise en compte)")
    rows_html = ""
    for r in elo["ranking"]:
        photo = get_fighter_photo(r["fighter"])
        img = (f'<img src="{photo}" style="width:36px;height:36px;border-radius:50%;object-fit:cover;'
               f'vertical-align:middle;margin-right:10px;">') if photo else "🥊 "
        hl = ' style="background:rgba(212,175,55,.12);"' if r["fighter"] in (fighter_a, fighter_b) else ""
        rows_html += (f"<tr{hl}><td style='padding:6px 10px;'>#{r['rank']}</td>"
                      f"<td style='padding:6px 10px;'>{img}{r['fighter']}</td>"
                      f"<td style='padding:6px 10px;font-weight:800;color:{ACCENT_GOLD};'>{r['elo']}</td></tr>")
    st.markdown(f"<table style='width:100%;border-collapse:collapse;'>{rows_html}</table>",
                unsafe_allow_html=True)

# ============================ ONGLET 5 : LIVE UPDATES ========================
with tab_live:
    st.markdown(
        f"""
        <div style="text-align: center; margin-bottom: 2rem;">
            <h1 style="font-family: 'Poppins', sans-serif; font-size: 2.5rem;
                       background: linear-gradient(120deg, {ACCENT_RED}, {ACCENT_BLUE});
                       -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                       margin-bottom: 0.5rem;">🔴 Live Updates</h1>
            <p style="color: {TEXT_SECONDARY}; font-size: 1rem;">Dernières infos en temps réel du monde MMA</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="baseline-box" style="margin-bottom: 1.5rem;">
            <strong style="color: {ACCENT_BLUE};">📡 Real-time Insights</strong><br>
            Blessures rapportées • Nouvelles d'entraînement • Mouvements d'odds • Analyse de forme
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Filtrer par combattant
    col_filter, col_refresh = st.columns([3, 1])
    with col_filter:
        live_filter = st.selectbox("🔍 Filtrer", ["Tous les combattants"] + fighters, key="live_filter")
    with col_refresh:
        if st.button("🔄", use_container_width=True, help="Rafraîchir"):
            st.rerun()

    filter_name = None if live_filter == "Tous les combattants" else live_filter
    updates_result = get_live_updates(filter_name)
    updates = updates_result.get("recent_updates", [])

    if not updates:
        st.markdown(
            f"""
            <div style="text-align: center; padding: 3rem 1rem;">
                <p style="font-size: 2rem;">📡</p>
                <p style="color: {TEXT_SECONDARY};">Aucune mise à jour pour le moment</p>
                <p style="font-size: 0.9rem; color: {TEXT_SECONDARY};">Revenez dans quelques instants</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        # Type et couleurs modernes
        update_types = {
            "injury": ("🚑", "BLESSURE", ACCENT_RED),
            "news": ("📰", "NEWS", ACCENT_BLUE),
            "odds": ("💰", "ODDS", ACCENT_GOLD),
            "form": ("📈", "FORME", SUCCESS_GREEN),
            "training": ("💪", "ENTRAÎNEMENT", ACCENT_PURPLE),
        }

        for idx, update in enumerate(updates):
            upd_type = update.get("update_type", "news")
            icon, label, color = update_types.get(upd_type, ("📌", upd_type.upper(), TEXT_SECONDARY))
            severity = update.get("severity", "info")

            severity_styling = {
                "critical": (ACCENT_RED, "⚠️ CRITIQUE"),
                "warning": (WARNING_ORANGE, "⚡ ATTENTION"),
                "info": (ACCENT_BLUE, "ℹ️ INFO"),
            }
            sev_color, sev_label = severity_styling.get(severity, (TEXT_SECONDARY, ""))

            st.markdown(
                f"""
                <div style="
                    background: linear-gradient(135deg, rgba({int(color.lstrip('#')[:2], 16)},
                                                             {int(color.lstrip('#')[2:4], 16)},
                                                             {int(color.lstrip('#')[4:], 16)}, 0.08) 0%,
                                                rgba(255, 255, 255, 0.02) 100%);
                    backdrop-filter: blur(10px);
                    border: 1px solid rgba({int(color.lstrip('#')[:2], 16)},
                                          {int(color.lstrip('#')[2:4], 16)},
                                          {int(color.lstrip('#')[4:], 16)}, 0.3);
                    border-left: 4px solid {color};
                    border-radius: 14px;
                    padding: 1.25rem;
                    margin-bottom: 1rem;
                    transition: all 0.3s ease;
                " class="update-card">
                    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 0.75rem;">
                        <span style="font-size: 1.4rem;">{icon}</span>
                        <span style="color: {color}; font-weight: 700; text-transform: uppercase;
                                     letter-spacing: 1px; font-size: 0.85rem;">{label}</span>
                        <span style="color: {sev_color}; font-size: 0.75rem; font-weight: 700;
                                     margin-left: auto;">{sev_label}</span>
                    </div>
                    <div style="font-weight: 700; color: {TEXT_PRIMARY}; margin-bottom: 0.5rem;
                                font-size: 1.05rem; line-height: 1.4;">
                        {update.get('title', 'Sans titre')}
                    </div>
                    <div style="color: {TEXT_SECONDARY}; font-size: 0.95rem; margin-bottom: 0.75rem;
                                line-height: 1.5;">
                        {update.get('description', '')}
                    </div>
                    <div style="color: {TEXT_SECONDARY}; font-size: 0.8rem;
                                border-top: 1px solid rgba(255, 255, 255, 0.1);
                                padding-top: 0.75rem;">
                        🥊 <strong>{update.get('fighter_name', 'N/A')}</strong> •
                        📅 {update.get('timestamp', 'N/A')[:10]}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("---")
        st.markdown(
            f"""
            <div style="text-align: center; padding: 1rem; color: {TEXT_SECONDARY}; font-size: 0.85rem;">
                ✓ {updates_result['updates_count']} mise(s) à jour •
                Dernière: {updates_result.get('last_update', 'N/A')[:10]}
            </div>
            """,
            unsafe_allow_html=True,
        )
