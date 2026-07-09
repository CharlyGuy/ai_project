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
# PALETTE + CSS "BROADCAST"
# --------------------------------------------------------------------------
DARK = "#0D0D0D"
CARD = "#161618"
RED = "#E60000"
GOLD = "#D4AF37"
BLUE = "#4d7cff"

st.markdown(
    f"""
    <style>
    .stApp {{ background-color: {DARK}; }}
    .stMainBlock, .stMainBlock * {{ color: #f5f5f5; letter-spacing: 0.3px; }}

    [data-testid="stSidebar"], [data-testid="stSidebar"] * {{
        background-color: #111113 !important; color: #d8d8d8 !important;
    }}

    .fs-title {{
        text-align: center; font-size: 3rem; font-weight: 900; text-transform: uppercase;
        background: linear-gradient(90deg, {RED}, {GOLD});
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        font-family: 'Arial Black', sans-serif; margin-bottom: 0;
    }}
    .fs-subtitle {{ text-align: center; color: #9a9a9a !important; margin-top: 2px;
                    text-transform: uppercase; font-size: 0.85rem; letter-spacing: 3px; }}

    .vs-badge {{ text-align: center; font-size: 2.4rem; font-weight: 900; color: {RED} !important;
                 padding-top: 2.6rem; font-family: 'Arial Black', sans-serif;
                 text-shadow: 0 0 22px rgba(230,0,0,.6); }}

    .trace-box {{
        background: #121214; border-left: 3px solid {RED}; border-radius: 6px;
        padding: 0.55rem 0.9rem; margin-bottom: 0.45rem; font-size: 0.92rem;
    }}
    .trace-box code {{ color: {GOLD} !important; background: transparent; }}
    .trace-thought {{ border-left-color: {BLUE}; }}
    .trace-action {{ border-left-color: {GOLD}; }}
    .trace-observation {{ border-left-color: #2ecf7a; }}

    .gold-box {{
        background: linear-gradient(135deg, rgba(212,175,55,.12), rgba(212,175,55,.04));
        border: 1px solid {GOLD}; border-radius: 10px; padding: 0.9rem 1.2rem;
        text-align: center; font-size: 1.15rem; font-weight: 800; color: {GOLD} !important;
        text-transform: uppercase; letter-spacing: 1px;
    }}
    .gameplan-card {{
        background: {CARD}; border-radius: 10px; padding: 1.2rem; height: 100%;
        border-top: 3px solid {RED};
    }}
    .gameplan-card.blue {{ border-top-color: {BLUE}; }}
    .gameplan-card h4 {{ text-transform: uppercase; font-family: 'Arial Black', sans-serif; }}
    .gameplan-card li {{ margin-bottom: 0.35rem; }}

    .baseline-box {{
        background: #1c1c1f; border: 1px dashed #555; border-radius: 10px;
        padding: 1.1rem 1.3rem; color: #c9c9c9 !important;
    }}
    .value-tag {{ color: {GOLD} !important; font-weight: 800; }}
    .methodo {{ font-size: 0.8rem; color: #9a9a9a !important; }}
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
        st.markdown(render_fighter_portrait(a, BLUE), unsafe_allow_html=True)
    with pvs:
        st.markdown('<div class="vs-badge">VS</div>', unsafe_allow_html=True)
    with p2:
        st.markdown(render_fighter_portrait(b, RED), unsafe_allow_html=True)

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
    for f, color, fill in [(a, BLUE, "rgba(77,124,255,0.25)"), (b, RED, "rgba(230,0,0,0.25)")]:
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
    favorite, fav_prob, fav_color = (name_a, prob_a, BLUE) if prob_a >= prob_b else (name_b, prob_b, RED)

    st.markdown(f'<div class="gold-box">🥇 Prédiction : {favorite} · '
                f'{report.get("predicted_method", "N/A")}</div>', unsafe_allow_html=True)
    st.markdown("")

    # portraits photo autour de la barre de probabilité
    pc1, pc2, pc3 = st.columns([2, 6, 2])
    with pc1:
        st.markdown(render_fighter_portrait(get_fighter_stats(name_a), BLUE), unsafe_allow_html=True)
    with pc3:
        st.markdown(render_fighter_portrait(get_fighter_stats(name_b), RED), unsafe_allow_html=True)
    with pc2:
        bar_a = int(prob_a)
        st.markdown(
            f"""
            <div style="margin-top:55px;display:flex;height:44px;border-radius:8px;overflow:hidden;
                        font-weight:800;font-family:'Arial Black',sans-serif;">
                <div style="width:{bar_a}%;background:{BLUE};display:flex;align-items:center;
                            justify-content:center;">{name_a} {prob_a:.0f}%</div>
                <div style="width:{100 - bar_a}%;background:{RED};display:flex;align-items:center;
                            justify-content:center;">{name_b} {prob_b:.0f}%</div>
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
                "threshold": {"line": {"color": GOLD, "width": 3}, "value": fav_prob},
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
                      f"<td style='padding:6px 10px;font-weight:800;color:{GOLD};'>{r['elo']}</td></tr>")
    st.markdown(f"<table style='width:100%;border-collapse:collapse;'>{rows_html}</table>",
                unsafe_allow_html=True)

# ============================ ONGLET 5 : LIVE UPDATES ========================
with tab_live:
    st.header("🔴 Mises à jour en temps réel")
    st.markdown(
        '<div class="baseline-box">📡 Dernières news, blessures rapportées, changements odds et développements '
        'd\'entraînement — mises à jour publiées en direct de la communauté MMA.</div>',
        unsafe_allow_html=True,
    )

    # Filtrer par combattant ou voir toutes les updates
    col_filter, col_auto = st.columns([3, 2])
    with col_filter:
        live_filter = st.selectbox("Filtrer par combattant", ["Tous les combattants"] + fighters, key="live_filter")
    with col_auto:
        if st.button("🔄 Rafraîchir", use_container_width=True):
            st.rerun()

    filter_name = None if live_filter == "Tous les combattants" else live_filter

    # Récupérer les updates temps réel
    updates_result = get_live_updates(filter_name)
    updates = updates_result.get("recent_updates", [])

    if not updates:
        st.info("Aucune mise à jour en direct pour le moment. Vérifiez à nouveau plus tard! 📡")
    else:
        # Afficher les updates groupées par type
        update_types = {
            "injury": ("🚑", "Blessure", "#ff6b6b"),
            "news": ("📰", "News", "#4ecdc4"),
            "odds": ("💰", "Odds", "#ffe66d"),
            "form": ("📈", "Forme", "#95e1d3"),
            "training": ("💪", "Entraînement", "#a8dadc"),
        }

        for update in updates:
            upd_type = update.get("update_type", "news")
            icon, label, color = update_types.get(upd_type, ("📌", upd_type.title(), "#cccccc"))
            severity = update.get("severity", "info")
            severity_color = "#ff6b6b" if severity == "critical" else "#ffa600" if severity == "warning" else "#4ecdc4"

            # Card style pour chaque update
            st.markdown(
                f"""
                <div style="background: {color}11; border-left: 4px solid {color};
                            border-radius: 8px; padding: 12px 16px; margin-bottom: 12px;">
                    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 6px;">
                        <span style="font-size: 1.3rem;">{icon}</span>
                        <span style="color: {color}; font-weight: 800; text-transform: uppercase;
                                     letter-spacing: 1px;">{label}</span>
                        <span style="color: {severity_color}; font-size: 0.75rem;
                                     font-weight: 700;">● {severity.upper()}</span>
                    </div>
                    <div style="font-weight: 700; color: #eee; margin-bottom: 4px;">
                        {update.get('title', 'Sans titre')}
                    </div>
                    <div style="color: #bbb; font-size: 0.95rem; margin-bottom: 8px;">
                        {update.get('description', '')}
                    </div>
                    <div style="color: #999; font-size: 0.8rem;">
                        🕐 {update.get('fighter_name', '')} — {update.get('timestamp', '')[:10]}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("---")
        st.caption(f"✓ {updates_result['updates_count']} mise(s) à jour affichée(s). "
                   f"Dernière update : {updates_result.get('last_update', 'N/A')[:10]}")
