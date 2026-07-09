"""
app.py
------
FightStrategist AI — interface Streamlit.

- Sélection de deux combattants (menus déroulants) -> "Tale of the Tape".
- Bouton "Lancer l'Analyse Stratégique" -> exécute la boucle agentique
  (agent/agent_loop.py) et affiche en direct le raisonnement (Live Trace).
- Rapport final : probabilité de victoire, clés de victoire, gameplans.
"""
import os

import streamlit as st
from dotenv import load_dotenv

from agent.agent_loop import run_agent
from agent.tools import list_fighters, get_fighter_stats

load_dotenv()

st.set_page_config(
    page_title="FightStrategist AI",
    page_icon="🥊",
    layout="wide",
)

# --------------------------------------------------------------------------
# STYLE — esthétique "carte de combat" (dark, rouge, condensé)
# --------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* Fond noir global de l'application */
    .stApp { 
        background-color: #0e0e10; 
    }
    
    /* Force le blanc sur TOUT le bloc principal, y compris les textes imbriqués */
    .stMainBlock, .stMainBlock * { 
        color: #ffffff !important; 
        font-family: 'Arial Black', sans-serif; 
        letter-spacing: 0.5px; 
    }
    
    /* Style spécifique pour la Sidebar pour qu'elle reste intacte et lisible */
    [data-testid="stSidebar"], [data-testid="stSidebar"] * {
        background-color: #f0f2f6 !important;
        color: #31333f !important; 
        font-family: sans-serif !important;
    }
    
    /* Contourner les badges de succès/code dans la sidebar */
    [data-testid="stSidebar"] .stAlert * {
        color: #155724 !important; /* Garde le texte du bouton succès au vert */
    }

    .fs-title {
        text-align: center; font-size: 2.6rem; font-weight: 900;
        background: linear-gradient(90deg, #ff2d2d, #ff9d2d);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin-bottom: 0;
    }
    
    .fs-subtitle { text-align: center; color: #dcdcdc !important; margin-top: 0; margin-bottom: 1.5rem; }
    
    .fighter-card {
        background: #1a1a1d; border: 1px solid #2c2c30; border-radius: 12px;
        padding: 1.1rem 1.3rem; text-align: center;
    }
    .fighter-name { font-size: 1.4rem; font-weight: 800; color: #ffffff !important; }
    .fighter-record { color: #ff5b5b !important; font-weight: 700; }
    
    .vs-badge {
        text-align: center; font-size: 2rem; font-weight: 900; color: #ff2d2d !important;
        padding-top: 2.2rem;
    }
    
    /* Boîtes de Live Trace */
    .trace-box {
        background: #131315; border-left: 3px solid #ff2d2d; border-radius: 6px;
        padding: 0.55rem 0.9rem; margin-bottom: 0.45rem; font-size: 0.92rem;
        color: #ffffff !important;
    }
    .trace-box code { color: #ffb020 !important; }
    
    .trace-thought { border-left-color: #4d7cff; }
    .trace-action { border-left-color: #ffb020; }
    .trace-observation { border-left-color: #2ecf7a; }
    
    .gameplan-card {
        background: #1a1a1d; border-radius: 12px; padding: 1.2rem;
        border-top: 4px solid #ff2d2d; height: 100%;
        color: #ffffff !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<p class="fs-title">🥊 FightStrategist AI</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="fs-subtitle">Agent autonome de scouting &amp; gameplan — MMA / Boxe / Kickboxing</p>',
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------
# SIDEBAR — config
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Configuration")
    env_key_present = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if env_key_present:
        st.success("Clé API détectée dans l'environnement (.env)")
        api_key_input = None
    else:
        api_key_input = st.text_input("Clé API Anthropic", type="password", help="sk-ant-...")
        st.caption("Ou définis ANTHROPIC_API_KEY dans un fichier .env (voir .env.example).")

    st.markdown("---")
    st.caption("**Modèle utilisé :** `claude-haiku-4-5`")
    st.caption("**Stack :** RAG (TF-IDF) · Tools (MCP-style) · Boucle agentique Reason→Act→Observe")
    st.markdown("---")
    st.caption("⚠️ Données de combattants **mockées** à but pédagogique — stats approximatives, pas une source officielle.")

# --------------------------------------------------------------------------
# SÉLECTION DES COMBATTANTS
# --------------------------------------------------------------------------
fighters = list_fighters()

col_a, col_vs, col_b = st.columns([5, 1, 5])
with col_a:
    fighter_a = st.selectbox("🔵 Combattant A", fighters, index=0, key="fighter_a")
with col_vs:
    st.markdown('<div class="vs-badge">VS</div>', unsafe_allow_html=True)
with col_b:
    fighter_b = st.selectbox("🔴 Combattant B", fighters, index=1, key="fighter_b")

launch = st.button("🚀 Lancer l'Analyse Stratégique", use_container_width=True, type="primary")

# --------------------------------------------------------------------------
# TALE OF THE TAPE
# --------------------------------------------------------------------------


def _record_str(f):
    r = f["record"]
    return f"{r['wins']}-{r['losses']}-{r['draws']}"


def render_tale_of_the_tape(name_a, name_b):
    a, b = get_fighter_stats(name_a), get_fighter_stats(name_b)

    st.subheader("📋 Tale of the Tape")
    c1, c2 = st.columns(2)
    for col, f, color in [(c1, a, "🔵"), (c2, b, "🔴")]:
        with col:
            st.markdown(
                f"""<div class="fighter-card">
                    <div class="fighter-name">{color} {f['name']} {f.get('nickname','')}</div>
                    <div class="fighter-record">{_record_str(f)} · {f['weight_class']}</div>
                </div>""",
                unsafe_allow_html=True,
            )

    metrics = [
        ("Taille", "height_cm", "cm"),
        ("Allonge", "reach_cm", "cm"),
        ("Précision de frappe", "striking_accuracy_pct", "%"),
        ("Défense takedown", "takedown_defense_pct", "%"),
        ("Taux de KO", "ko_rate_pct", "%"),
        ("Taux de soumission", "submission_rate_pct", "%"),
        ("Cardio (1-10)", "cardio_rating", ""),
        ("Menton (1-10)", "chin_rating", ""),
    ]
    for label, key, unit in metrics:
        m1, m2, m3 = st.columns([2, 5, 2])
        m1.markdown(f"<div style=\"color:white;font-size:1.1rem;font-weight:700\">{a[key]}{unit}</div>", unsafe_allow_html=True)
        m2.markdown(f"<div style='text-align:center;color:#bdbdbd'>{label}</div>", unsafe_allow_html=True)
        m3.markdown(f"<div style='text-align:right;color:white;font-size:1.1rem;font-weight:700'>{b[key]}{unit}</div>", unsafe_allow_html=True)

    st.caption(
        f"🔵 Style : {', '.join(a['style_tags'])}  ·  🔴 Style : {', '.join(b['style_tags'])}"
    )


if fighter_a and fighter_b:
    if fighter_a == fighter_b:
        st.warning("Choisis deux combattants différents pour lancer l'analyse.")
    else:
        render_tale_of_the_tape(fighter_a, fighter_b)

st.markdown("---")

# --------------------------------------------------------------------------
# LIVE TRACE + RAPPORT FINAL
# --------------------------------------------------------------------------

ICONS = {"thought": "🧠", "action": "⚙️", "observation": "👁️", "final": "🏆"}
LABELS = {"thought": "Pensée", "action": "Action", "observation": "Observation", "final": "Résultat"}
CSS_CLASS = {"thought": "trace-thought", "action": "trace-action", "observation": "trace-observation"}


def render_step(container, step):
    kind = step["type"]
    if kind == "thought":
        body = step["text"]
    elif kind == "action":
        body = f"<code>{step['tool']}({step['input']})</code>"
    elif kind == "observation":
        out = step["output"]
        body = f"<code>{str(out)[:400]}</code>"
    else:
        return
    container.markdown(
        f'<div class="trace-box {CSS_CLASS.get(kind,"")}">'
        f'<b>{ICONS[kind]} {LABELS[kind]}</b> — {body}</div>',
        unsafe_allow_html=True,
    )


def render_final_report(report, name_a, name_b):
    st.subheader("🏆 Rapport Stratégique")

    prob_a = float(report.get("victory_probability_a", 50))
    prob_b = float(report.get("victory_probability_b", 50))
    total = prob_a + prob_b if (prob_a + prob_b) > 0 else 1
    prob_a, prob_b = 100 * prob_a / total, 100 * prob_b / total

    st.markdown(f"**Méthode de victoire prédite :** {report.get('predicted_method', 'N/A')}")

    bar_a = int(prob_a)
    st.markdown(
        f"""
        <div style="display:flex;height:34px;border-radius:8px;overflow:hidden;font-weight:700;">
            <div style="width:{bar_a}%;background:#4d7cff;display:flex;align-items:center;justify-content:center;color:white;">
                {name_a} {prob_a:.0f}%
            </div>
            <div style="width:{100-bar_a}%;background:#ff2d2d;display:flex;align-items:center;justify-content:center;color:white;">
                {name_b} {prob_b:.0f}%
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("")
    st.info(report.get("summary", ""))

    c1, c2 = st.columns(2)
    for col, name, keys_field, plan_field in [
        (c1, name_a, "keys_to_victory_a", "game_plan_a"),
        (c2, name_b, "keys_to_victory_b", "game_plan_b"),
    ]:
        with col:
            keys = report.get(keys_field, []) or []
            keys_html = "".join(f"<li>{k}</li>" for k in keys)
            st.markdown(
                f"""<div class="gameplan-card">
                    <h4>🎯 Game Plan — {name}</h4>
                    <p>{report.get(plan_field, '')}</p>
                    <ul>{keys_html}</ul>
                </div>""",
                unsafe_allow_html=True,
            )


if launch:
    if fighter_a == fighter_b:
        st.error("Choisis deux combattants différents.")
    else:
        api_key = api_key_input or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            st.error("Aucune clé API Anthropic disponible. Renseigne-la dans la sidebar ou via .env.")
        else:
            st.subheader("🔎 Live Trace — l'agent enquête en direct")
            trace_container = st.container()
            steps_holder = []

            def callback(step):
                steps_holder.append(step)
                render_step(trace_container, step)

            with st.spinner("L'agent mène son enquête..."):
                try:
                    report = run_agent(fighter_a, fighter_b, callback, api_key=api_key)
                except Exception as exc:
                    st.error(f"Erreur pendant l'exécution de l'agent : {exc}")
                    report = None

            if report:
                st.markdown("---")
                render_final_report(report, fighter_a, fighter_b)
