"""
src/tools.py
------------
Les outils "UFC Performance Institute" exposés à l'agent (API Anthropic tool use,
et re-publiés tels quels via MCP dans src/mcp_server.py).

- get_fighter_stats(fighter_name)      : fiche technique complète (SQLite)
- get_fight_history(fighter_name, n)   : derniers combats (SQLite)
- get_betting_odds(fighter_name)       : cotes de Vegas + probabilité implicite (SQLite)
- search_fight_reports(query, ...)     : recherche vectorielle RAG (ChromaDB + MiniLM)
- compare_styles(fighter_a, fighter_b) : deltas physiques + alertes de mismatch
- simulate_fight(fighter_a, fighter_b) : Monte-Carlo 500 combats complets (cardio
  décroissant, précision vs défense, KO basé sur puissance vs menton)
- submit_final_report(...)             : tool "puits", signal de fin de boucle

La probabilité de victoire du rapport final vient de simulate_fight : CALCULÉE,
pas estimée par le LLM.
"""
from __future__ import annotations

import random

from . import database as db
from .rag_engine import get_rag

# La base est créée/seedée au premier import (idempotent).
db.init_db()

# ---------------------------------------------------------------------------
# Combattants custom (mode "Create-a-Fighter") : registre en mémoire, consulté
# AVANT SQLite par tous les tools. L'UI (re)registre depuis st.session_state.
# ---------------------------------------------------------------------------
CUSTOM_FIGHTERS: dict[str, dict] = {}

_DEFAULT_CUSTOM = {
    "nickname": "", "weight_class": "Lightweight", "stance": "Orthodox",
    "wins": 0, "losses": 0, "draws": 0, "height_cm": 180, "reach_cm": 183,
    "striking_accuracy_pct": 50.0, "strikes_landed_per_min": 4.0,
    "takedown_avg_per_15min": 1.5, "takedown_defense_pct": 70.0,
    "ko_rate_pct": 40.0, "submission_rate_pct": 20.0,
    "chin_durability": 7.0, "cardio_rating": 7.0, "power_rating": 7.0,
    "style_tags": "Custom",
}


def register_custom_fighter(fighter: dict) -> dict:
    """Enregistre (ou met à jour) un combattant custom ; complète les champs manquants."""
    full = {**_DEFAULT_CUSTOM, **fighter, "id": -1, "custom": True}
    CUSTOM_FIGHTERS[full["name"].lower()] = full
    return full


def _get_fighter(name: str) -> dict | None:
    """Résolution : combattants custom d'abord, puis SQLite (match souple)."""
    key = name.strip().lower()
    if key in CUSTOM_FIGHTERS:
        return CUSTOM_FIGHTERS[key]
    for cname, f in CUSTOM_FIGHTERS.items():
        if key in cname or cname in key:
            return f
    return db.get_fighter(name)


def list_fighters() -> list[str]:
    """Utilitaire UI (pas un tool LLM) : les noms pour les menus déroulants."""
    return db.list_fighter_names() + [f["name"] for f in CUSTOM_FIGHTERS.values()]


# ---------------------------------------------------------------------------
# TOOLS
# ---------------------------------------------------------------------------

def get_fighter_stats(fighter_name: str) -> dict:
    fighter = _get_fighter(fighter_name)
    if not fighter:
        return {"error": f"Combattant '{fighter_name}' introuvable dans la base."}
    return fighter


def get_fight_history(fighter_name: str, n: int = 5) -> dict:
    history = db.get_history(fighter_name, n)
    if not history:
        return {"error": f"Aucun historique trouvé pour '{fighter_name}'."}
    return {"fighter": fighter_name, "fights": history}


def get_betting_odds(fighter_name: str) -> dict:
    fighter = _get_fighter(fighter_name)
    if not fighter:
        return {"error": f"Combattant '{fighter_name}' introuvable."}
    odds = db.get_odds(fighter_name)
    if not odds:
        return {"error": f"Pas de cotes disponibles pour '{fighter_name}'."}
    cur, op = odds["current_odds"], odds["opening_odds"]
    fmt = lambda o: f"+{o}" if o > 0 else str(o)
    return {
        "fighter": fighter["name"],
        "current_odds": fmt(cur),
        "opening_odds": fmt(op),
        "implied_probability_pct": db.american_odds_to_prob(cur),
        "line_movement": "le marché a renforcé ce combattant" if abs(cur) > abs(op) and cur < 0
                          else "le marché s'est refroidi sur ce combattant" if cur > op > 0 or (cur > 0 > op)
                          else "ligne stable",
    }


def search_fight_reports(query: str, fighter_name: str | None = None, k: int = 3) -> dict:
    results = get_rag().search(query, k=k, fighter_name=fighter_name)
    return {"query": query, "results": results}


def compare_styles(fighter_a: str, fighter_b: str) -> dict:
    a, b = _get_fighter(fighter_a), _get_fighter(fighter_b)
    if not a or not b:
        return {"error": "Un des deux combattants est introuvable."}

    def archetype(f):
        if f["takedown_avg_per_15min"] >= 3:
            return "Grappler"
        if f["takedown_avg_per_15min"] >= 1.5:
            return "Mixte"
        return "Striker"

    alerts = []
    reach_delta = a["reach_cm"] - b["reach_cm"]
    if abs(reach_delta) >= 8:
        longer = a if reach_delta > 0 else b
        alerts.append(f"{longer['name']} a un avantage d'allonge net (+{abs(reach_delta)} cm) : "
                      f"il peut scorer en distance longue sans engagement.")
    for atk, dfn in ((a, b), (b, a)):
        if atk["takedown_avg_per_15min"] >= 3 and dfn["takedown_defense_pct"] < 70:
            alerts.append(f"MISMATCH SOL : {atk['name']} tire beaucoup "
                          f"({atk['takedown_avg_per_15min']}/15min) et la défense de takedown de "
                          f"{dfn['name']} est faible ({dfn['takedown_defense_pct']}%).")
        if atk["power_rating"] >= 9 and dfn["chin_durability"] <= 6:
            alerts.append(f"ALERTE KO : la puissance de {atk['name']} ({atk['power_rating']}/10) "
                          f"face au menton fragile de {dfn['name']} ({dfn['chin_durability']}/10).")
    cardio_delta = a["cardio_rating"] - b["cardio_rating"]
    if abs(cardio_delta) >= 2:
        fitter = a if cardio_delta > 0 else b
        alerts.append(f"{fitter['name']} a un net avantage de cardio : les rounds tardifs penchent vers lui.")
    if not alerts:
        alerts.append("Pas de mismatch flagrant : l'issue dépendra du gameplan et du rythme.")

    return {
        "fighter_a": {"name": a["name"], "archetype": archetype(a), "stance": a["stance"]},
        "fighter_b": {"name": b["name"], "archetype": archetype(b), "stance": b["stance"]},
        "reach_diff_cm": reach_delta,
        "height_diff_cm": a["height_cm"] - b["height_cm"],
        "cardio_diff": cardio_delta,
        "power_vs_chin": {
            f"{a['name']} power vs {b['name']} chin": f"{a['power_rating']}/10 vs {b['chin_durability']}/10",
            f"{b['name']} power vs {a['name']} chin": f"{b['power_rating']}/10 vs {a['chin_durability']}/10",
        },
        "alerts": alerts,
    }


# ---------------------------------------------------------------------------
# Simulation Monte-Carlo
# ---------------------------------------------------------------------------

def _fatigue(f: dict, rnd: int) -> float:
    """Facteur d'efficacité du round `rnd` : le cardio (1-10) amortit la décroissance."""
    decay = (10 - f["cardio_rating"]) * 0.035
    return max(0.45, 1 - decay * (rnd - 1))


def _round_model(a: dict, b: dict, rnd: int):
    """Scores offensifs du round + chances de finish, pour un round donné.

    - striking : précision × volume × fatigue, pénalisé rien (la défense joue via le chin/KO)
    - grappling : takedowns × fatigue, pénalisé par la défense de takedown adverse
    - KO : puissance de l'attaquant × son taux de KO × fragilité du menton adverse × fatigue
    - Soumission : taux de soumission × capacité à amener au sol × faille de TDD adverse
    """
    fa, fb = _fatigue(a, rnd), _fatigue(b, rnd)

    def striking(f, fat):
        return f["striking_accuracy_pct"] * 0.6 + f["strikes_landed_per_min"] * 6 * fat

    def grappling(atk, dfn, fat):
        base = atk["takedown_avg_per_15min"] * 11 * fat + atk["submission_rate_pct"] * 0.25
        return max(0.0, base - dfn["takedown_defense_pct"] * 0.18)

    score_a = max(0.0, striking(a, fa) + grappling(a, b, fa))
    score_b = max(0.0, striking(b, fb) + grappling(b, a, fb))

    def ko_chance(atk, dfn, fat):
        return (atk["power_rating"] / 10) * (atk["ko_rate_pct"] / 100) \
            * ((10 - dfn["chin_durability"]) / 10 * 0.6 + 0.15) * fat * 0.45

    def sub_chance(atk, dfn, fat):
        ground_access = min(1.0, atk["takedown_avg_per_15min"] / 4)
        opening = (100 - dfn["takedown_defense_pct"]) / 100 * 0.7 + 0.08
        return (atk["submission_rate_pct"] / 100) * ground_access * opening * fat * 0.5

    return score_a, score_b, ko_chance(a, b, fa), sub_chance(a, b, fa), ko_chance(b, a, fb), sub_chance(b, a, fb)


def simulate_fight(fighter_a: str, fighter_b: str, n_simulations: int = 500,
                   rounds: int = 3, seed: int | None = None) -> dict:
    """Monte-Carlo : rejoue le combat complet N fois et compte les victoires.

    Chaque round simulé : tirage KO (puissance vs menton) puis soumission
    (grappling vs défense de takedown) ; sinon le round est attribué par tirage
    pondéré par les scores striking+grappling, dégradés par la fatigue (cardio).
    Sans finish : décision des juges au nombre de rounds gagnés.
    """
    a, b = _get_fighter(fighter_a), _get_fighter(fighter_b)
    if not a or not b:
        return {"error": "Un des deux combattants est introuvable."}
    n_simulations = max(100, min(int(n_simulations), 5000))

    rng = random.Random(seed)
    wins_a = wins_b = 0
    methods: dict[str, int] = {}
    finish_rounds: dict[int, int] = {}
    total_rounds = 0

    for _ in range(n_simulations):
        ra = rb = 0
        winner = method = None
        end_round = rounds
        for rnd in range(1, rounds + 1):
            s_a, s_b, ko_a, sub_a, ko_b, sub_b = _round_model(a, b, rnd)
            roll = rng.random()
            if roll < ko_a:
                winner, method, end_round = "a", "KO/TKO", rnd
                break
            if roll < ko_a + ko_b:
                winner, method, end_round = "b", "KO/TKO", rnd
                break
            if roll < ko_a + ko_b + sub_a:
                winner, method, end_round = "a", "Soumission", rnd
                break
            if roll < ko_a + ko_b + sub_a + sub_b:
                winner, method, end_round = "b", "Soumission", rnd
                break
            total = s_a + s_b if (s_a + s_b) > 0 else 1
            if rng.random() < s_a / total:
                ra += 1
            else:
                rb += 1
        total_rounds += end_round
        if winner is None:
            method = "Décision"
            if ra == rb:
                winner = "a" if rng.random() < 0.5 else "b"
            else:
                winner = "a" if ra > rb else "b"
        else:
            finish_rounds[end_round] = finish_rounds.get(end_round, 0) + 1

        name = a["name"] if winner == "a" else b["name"]
        if winner == "a":
            wins_a += 1
        else:
            wins_b += 1
        key = f"{name} par {method}"
        methods[key] = methods.get(key, 0) + 1

    breakdown = {k: round(100 * v / n_simulations, 1)
                 for k, v in sorted(methods.items(), key=lambda kv: -kv[1])}
    most_likely = next(iter(breakdown))
    likely_finish_round = max(finish_rounds, key=finish_rounds.get) if finish_rounds else None
    return {
        "n_simulations": n_simulations,
        "rounds_per_fight": rounds,
        "win_probability_a_pct": round(100 * wins_a / n_simulations, 1),
        "win_probability_b_pct": round(100 * wins_b / n_simulations, 1),
        "method_breakdown_pct": breakdown,
        "most_likely_outcome": most_likely + (f" (round {likely_finish_round})"
                                              if likely_finish_round and "Décision" not in most_likely else ""),
        "finish_rate_pct": round(100 * sum(finish_rounds.values()) / n_simulations, 1),
        "avg_fight_length_rounds": round(total_rounds / n_simulations, 2),
    }


# ---------------------------------------------------------------------------
# Timeline play-by-play (alimente le Fight Simulator 3D)
# ---------------------------------------------------------------------------

# Liste FERMÉE des actions — le moteur 3D (static/fight3d/engine.js) connaît exactement celles-ci.
ACTIONS = ["idle", "jab", "cross", "hook", "uppercut", "leg_kick", "body_kick", "head_kick",
           "takedown_attempt", "ground_control", "ground_strikes", "submission_attempt",
           "block", "dodge", "clinch", "knockdown", "ko", "submission_win", "decision"]

_STRIKES = ["jab", "cross", "hook", "uppercut", "leg_kick", "body_kick", "head_kick"]
_STRIKE_DMG = {"jab": 1.5, "cross": 3.0, "hook": 3.6, "uppercut": 3.8,
               "leg_kick": 2.4, "body_kick": 3.2, "head_kick": 5.5}
_STRIKE_TARGET = {"jab": "head", "cross": "head", "hook": "head", "uppercut": "head",
                  "leg_kick": "leg", "body_kick": "body", "head_kick": "head"}

_COMMENT = {
    "jab": ["{a} avance derrière son jab", "Le jab de {a} claque", "{a} mesure la distance au jab"],
    "cross": ["Grosse droite de {a} !", "{a} traverse avec le cross", "Le cross de {a} passe la garde"],
    "hook": ["CROCHET de {a} !", "{a} balance le hook dans l'échange", "Le crochet court de {a} touche"],
    "uppercut": ["Uppercut vicieux de {a} !", "{a} glisse l'uppercut dans la garde"],
    "leg_kick": ["Low kick sec de {a}", "{a} attaque la jambe d'appui", "Encore un low kick de {a}"],
    "body_kick": ["Kick au corps de {a}", "{a} claque le body kick"],
    "head_kick": ["HEAD KICK de {a} !!", "{a} tente la high kick !"],
    "takedown_attempt": ["ÉNORME takedown de {a} !", "{a} change de niveau et attrape les jambes !",
                          "{a} presse contre la cage et tire"],
    "takedown_fail": ["{b} défend le takedown de {a} !", "{a} tire mais {b} garde ses appuis"],
    "ground_control": ["{a} contrôle au sol, {b} est coincé", "{a} passe en position dominante",
                        "Contrôle écrasant de {a}"],
    "ground_strikes": ["Ground and pound de {a} !", "{a} pleut des coups depuis le dessus"],
    "submission_attempt": ["{a} cherche la soumission !", "{a} enroule le cou de {b} !",
                            "Tentative d'étranglement de {a} !"],
    "block": ["{b} bloque proprement", "La garde de {b} absorbe"],
    "dodge": ["{b} esquive du buste !", "{b} slip le coup de justesse"],
    "clinch": ["Les deux hommes s'accrochent dans le clinch", "{a} enferme {b} contre la cage"],
    "knockdown": ["{b} EST AU SOL !! {a} l'a touché !", "KNOCKDOWN !! {b} s'écroule !"],
    "ko": ["C'EST FINI !! {a} par KO !!", "IL L'A ÉTEINT !! Victoire de {a} !"],
    "submission_win": ["{b} TAPE !! Soumission de {a} !!", "C'est terminé, {a} par soumission !"],
}


def _pick_comment(rng: random.Random, key: str, a_name: str, b_name: str) -> str:
    return rng.choice(_COMMENT[key]).format(a=a_name, b=b_name)


def _action_weights(f: dict) -> dict:
    """Distribution des actions offensives pilotée par le PROFIL du combattant.

    Un Khabib (5.3 TD/15min, tags lutteur) doit visiblement lutter ; un Pereira
    (81% KO, 0.3 TD) doit visiblement frapper. C'est la cohérence données →
    comportement à l'écran.
    """
    tags = f.get("style_tags", "").lower()
    grappler_bias = 1.6 if any(t in tags for t in ("lutteur", "grappler", "sambo", "jiu-jitsu", "wrestling")) else 1.0
    td_drive = f["takedown_avg_per_15min"] * grappler_bias
    w = {
        "jab": 10 + f["strikes_landed_per_min"] * 1.5,
        "cross": 6 + f["power_rating"] + f["ko_rate_pct"] * 0.08,
        "hook": 4 + f["power_rating"] + f["ko_rate_pct"] * 0.08,
        "uppercut": 2 + f["power_rating"] * 0.6,
        "leg_kick": 3 + (4 if "kick" in tags or "low kick" in tags else 0),
        "body_kick": 2 + (2 if "kick" in tags else 0),
        "head_kick": 1 + (2.5 if "kick" in tags else 0) + f["ko_rate_pct"] * 0.02,
        "takedown_attempt": td_drive * 4.5,
        "clinch": 1.5 + td_drive * 0.6,
    }
    return w


def _weighted_choice(rng: random.Random, weights: dict) -> str:
    total = sum(weights.values())
    roll = rng.random() * total
    acc = 0.0
    for action, w in weights.items():
        acc += w
        if roll <= acc:
            return action
    return "jab"


def simulate_fight_playbyplay(fighter_a: str, fighter_b: str, rounds: int = 3,
                              seed: int | None = None) -> dict:
    """Génère une timeline événement-par-événement d'UN combat simulé (un tirage
    de la distribution Monte-Carlo), destinée au Fight Simulator 3D.

    - 15-30 événements par round, sur 60 s de temps simulé (t en secondes cumulées) ;
    - actions tirées du profil (lutteur → takedowns/contrôle, striker → coups) ;
    - `landed` dépend de la précision attaquant vs défense adverse ;
    - KO amortis par le chin du défenseur, fatigue via _fatigue ;
    - l'issue est tirée avec le MÊME modèle de round que simulate_fight.
    """
    a, b = _get_fighter(fighter_a), _get_fighter(fighter_b)
    if not a or not b:
        return {"error": "Un des deux combattants est introuvable."}

    rng = random.Random(seed)
    ROUND_SIM_S = 60.0      # 60 s simulées = 5:00 affichées (facteur 5)
    events: list[dict] = []
    health = {"a": 100.0, "b": 100.0}
    scorecards: list[dict] = []
    stats = {k: {"strikes_landed": 0, "takedowns": 0, "control_time_s": 0} for k in ("a", "b")}
    fighters = {"a": a, "b": b}
    names = {"a": a["name"], "b": b["name"]}

    winner = method = None
    end_round, end_t = rounds, ROUND_SIM_S

    for rnd in range(1, rounds + 1):
        s_a, s_b, ko_a, sub_a, ko_b, sub_b = _round_model(a, b, rnd)
        dmg_round = {"a": 0.0, "b": 0.0}

        # L'issue du round est tirée AVANT (même modèle que simulate_fight) ;
        # la timeline est ensuite générée pour raconter ce scénario.
        roll = rng.random()
        finish = None  # (actor, method)
        if roll < ko_a:
            finish = ("a", "KO/TKO")
        elif roll < ko_a + ko_b:
            finish = ("b", "KO/TKO")
        elif roll < ko_a + ko_b + sub_a:
            finish = ("a", "Soumission")
        elif roll < ko_a + ko_b + sub_a + sub_b:
            finish = ("b", "Soumission")
        finish_t = rng.uniform(0.35, 0.95) * ROUND_SIM_S if finish else None

        # Volume d'événements : activité combinée, dégradée par la fatigue.
        fat_pair = (_fatigue(a, rnd) + _fatigue(b, rnd)) / 2
        n_target = max(15, min(30, int((15 + (a["strikes_landed_per_min"] + b["strikes_landed_per_min"])
                                        + (a["takedown_avg_per_15min"] + b["takedown_avg_per_15min"]) * 1.2)
                                       * fat_pair)))
        t = 0.0
        ground_state: str | None = None   # 'a' ou 'b' = qui domine au sol
        ground_left = 0

        w_a, w_b = _action_weights(a), _action_weights(b)
        total_score = (s_a + s_b) or 1.0

        while True:
            t += rng.uniform(ROUND_SIM_S / (n_target * 1.4), ROUND_SIM_S / (n_target * 0.75))
            if finish_t is not None and t >= finish_t:
                break
            if t >= ROUND_SIM_S:
                break

            if ground_state and ground_left > 0:
                # Séquence au sol : le dominant contrôle / frappe / tente la soumission.
                actor = ground_state
                dfn = "b" if actor == "a" else "a"
                act = rng.choices(["ground_control", "ground_strikes", "submission_attempt"],
                                  weights=[4, 3, 1 + fighters[actor]["submission_rate_pct"] * 0.05])[0]
                ground_left -= 1
                if ground_left == 0 or rng.random() < 0.15:
                    ground_state = None  # stand-up
                dmg = 0.0
                if act == "ground_strikes":
                    dmg = round(rng.uniform(1.5, 4.0) * fighters[actor]["power_rating"] / 8, 1)
                    stats[actor]["strikes_landed"] += 1
                stats[actor]["control_time_s"] += 4
                health[dfn] = max(1.0, health[dfn] - dmg)
                dmg_round[dfn] += dmg
                events.append({"t": round(t, 1), "round": rnd, "actor": actor, "action": act,
                               "landed": True, "damage": dmg, "target": "body",
                               "commentary": _pick_comment(rng, act, names[actor], names[dfn])})
                continue

            # Debout : l'acteur est tiré au prorata des scores du round (le dominant agit plus).
            actor = "a" if rng.random() < s_a / total_score else "b"
            dfn = "b" if actor == "a" else "a"
            atk, d = fighters[actor], fighters[dfn]
            act = _weighted_choice(rng, w_a if actor == "a" else w_b)
            fat = _fatigue(atk, rnd)

            if act == "takedown_attempt":
                p_land = min(0.75, (100 - d["takedown_defense_pct"]) / 100
                             + atk["takedown_avg_per_15min"] * 0.04)
                landed = rng.random() < p_land
                dmg = round(rng.uniform(3.0, 6.0) * fat, 1) if landed else 0.0
                key = "takedown_attempt" if landed else "takedown_fail"
                if landed:
                    stats[actor]["takedowns"] += 1
                    ground_state, ground_left = actor, rng.randint(2, 5)
                health[dfn] = max(1.0, health[dfn] - dmg)
                dmg_round[dfn] += dmg
                events.append({"t": round(t, 1), "round": rnd, "actor": actor,
                               "action": "takedown_attempt", "landed": landed, "damage": dmg,
                               "target": "body",
                               "commentary": _pick_comment(rng, key, names[actor], names[dfn])})
                continue

            if act == "clinch":
                events.append({"t": round(t, 1), "round": rnd, "actor": actor, "action": "clinch",
                               "landed": True, "damage": 0.0, "target": "body",
                               "commentary": _pick_comment(rng, "clinch", names[actor], names[dfn])})
                continue

            # Frappe : landed selon précision vs défense (esquive ≈ inverse d'être touché).
            p_land = max(0.2, min(0.85, atk["striking_accuracy_pct"] / 100 * fat
                                  - (d["takedown_defense_pct"] - 60) * 0.001))
            landed = rng.random() < p_land
            if landed:
                base = _STRIKE_DMG[act] * (0.7 + atk["power_rating"] / 10 * 0.8) * fat
                dmg = round(base * rng.uniform(0.7, 1.3), 1)
                stats[actor]["strikes_landed"] += 1
                health[dfn] = max(1.0, health[dfn] - dmg)
                dmg_round[dfn] += dmg
                events.append({"t": round(t, 1), "round": rnd, "actor": actor, "action": act,
                               "landed": True, "damage": dmg, "target": _STRIKE_TARGET[act],
                               "commentary": _pick_comment(rng, act, names[actor], names[dfn])})
                # Knockdown possible sur grosse frappe (amorti par le chin, sans finir le round).
                if finish is None and dmg > 6 and rng.random() < (10 - d["chin_durability"]) / 30:
                    t += 1.5
                    events.append({"t": round(t, 1), "round": rnd, "actor": actor,
                                   "action": "knockdown", "landed": True, "damage": 2.0,
                                   "target": "head",
                                   "commentary": _pick_comment(rng, "knockdown", names[actor], names[dfn])})
                    health[dfn] = max(1.0, health[dfn] - 2.0)
                    dmg_round[dfn] += 2.0
            else:
                react = rng.choice(["block", "dodge"])
                events.append({"t": round(t, 1), "round": rnd, "actor": dfn, "action": react,
                               "landed": True, "damage": 0.0, "target": "none",
                               "commentary": _pick_comment(rng, react, names[actor], names[dfn])})

        # --- fin du round : finish scénarisé ou scorecard ---
        if finish is not None:
            f_actor, f_method = finish
            f_dfn = "b" if f_actor == "a" else "a"
            t_fin = finish_t
            if f_method == "KO/TKO":
                big = rng.choice(["cross", "hook", "uppercut", "head_kick"])
                events.append({"t": round(t_fin - 2.0, 1), "round": rnd, "actor": f_actor,
                               "action": big, "landed": True, "damage": 9.5, "target": "head",
                               "commentary": _pick_comment(rng, big, names[f_actor], names[f_dfn])})
                events.append({"t": round(t_fin - 1.0, 1), "round": rnd, "actor": f_actor,
                               "action": "knockdown", "landed": True, "damage": 5.0, "target": "head",
                               "commentary": _pick_comment(rng, "knockdown", names[f_actor], names[f_dfn])})
                events.append({"t": round(t_fin, 1), "round": rnd, "actor": f_actor, "action": "ko",
                               "landed": True, "damage": 10.0, "target": "head",
                               "commentary": _pick_comment(rng, "ko", names[f_actor], names[f_dfn])})
            else:
                events.append({"t": round(t_fin - 3.0, 1), "round": rnd, "actor": f_actor,
                               "action": "takedown_attempt", "landed": True, "damage": 4.0,
                               "target": "body",
                               "commentary": _pick_comment(rng, "takedown_attempt", names[f_actor], names[f_dfn])})
                stats[f_actor]["takedowns"] += 1
                events.append({"t": round(t_fin - 1.5, 1), "round": rnd, "actor": f_actor,
                               "action": "submission_attempt", "landed": True, "damage": 3.0,
                               "target": "body",
                               "commentary": _pick_comment(rng, "submission_attempt", names[f_actor], names[f_dfn])})
                events.append({"t": round(t_fin, 1), "round": rnd, "actor": f_actor,
                               "action": "submission_win", "landed": True, "damage": 5.0,
                               "target": "body",
                               "commentary": _pick_comment(rng, "submission_win", names[f_actor], names[f_dfn])})
            health[f_dfn] = 0.0
            winner, method, end_round, end_t = f_actor, f_method, rnd, t_fin
            break

        # Round complet : 10-9 à celui qui a infligé le plus de dégâts.
        round_winner = "a" if dmg_round["b"] >= dmg_round["a"] else "b"
        scorecards.append({"round": rnd,
                           "a": 10 if round_winner == "a" else 9,
                           "b": 10 if round_winner == "b" else 9})

    if winner is None:
        method = "Décision"
        pts_a = sum(c["a"] for c in scorecards)
        pts_b = sum(c["b"] for c in scorecards)
        winner = "a" if pts_a > pts_b else ("b" if pts_b > pts_a else rng.choice(["a", "b"]))
        events.append({"t": round(rounds * ROUND_SIM_S, 1), "round": rounds, "actor": winner,
                       "action": "decision", "landed": True, "damage": 0.0, "target": "none",
                       "commentary": f"Décision des juges : victoire de {names[winner]} !"})

    # t simulé (0-60 s) -> temps affiché du round (5:00), facteur 5.
    real_s = int((end_t if method != "Décision" else ROUND_SIM_S) * 5)
    time_str = f"{real_s // 60}:{real_s % 60:02d}"

    return {
        "fighter_a": a["name"], "fighter_b": b["name"],
        "events": events,
        "result": {
            "winner": winner, "winner_name": names[winner], "method": method,
            "round": end_round, "time": time_str,
            "final_health": {k: round(v, 1) for k, v in health.items()},
            "scorecards": scorecards,
            "stats_summary": stats,
        },
    }


# ---------------------------------------------------------------------------
# ELO rating dynamique (inspiré du dataset Kaggle "MMA Differentials and ELO")
# ---------------------------------------------------------------------------

def get_elo_ratings(fighter_a: str | None = None, fighter_b: str | None = None) -> dict:
    """Classement ELO du roster (K=32, base 1500), calculé en rejouant la table
    `fight_history` en ordre CHRONOLOGIQUE. Les adversaires membres du roster
    utilisent leur rating courant (la qualité d'opposition compte) ; les
    adversaires externes comptent pour 1500 fixe. Bonus finish : K x1.25 sur
    KO/soumission. Si fighter_a/fighter_b sont fournis, renvoie aussi le delta
    ELO du matchup courant.
    """
    K, BASE = 32, 1500
    roster = db.list_fighter_names()
    ratings = {name: float(BASE) for name in roster}

    # Toutes les lignes d'historique, triées chronologiquement.
    conn = db._connect()
    try:
        rows = conn.execute(
            "SELECT f.name AS fighter, h.opponent_name, h.result, h.method, h.date"
            " FROM fight_history h JOIN fighters f ON f.id = h.fighter_id"
            " ORDER BY h.date ASC"
        ).fetchall()
    finally:
        conn.close()

    seen = set()  # un combat roster-vs-roster apparaît 2x (une ligne par camp) -> dédupliquer
    for r in rows:
        fighter, opp, res, method, date = r["fighter"], r["opponent_name"], r["result"], r["method"], r["date"]
        key = (date, frozenset((fighter, opp)))
        if key in seen:
            continue
        seen.add(key)
        if res == "D":
            continue
        opp_in_roster = opp in ratings
        ra = ratings[fighter]
        rb = ratings[opp] if opp_in_roster else float(BASE)
        expected_a = 1 / (1 + 10 ** ((rb - ra) / 400))
        score_a = 1.0 if res == "W" else 0.0
        k = K * (1.25 if method in ("KO/TKO", "Soumission") else 1.0)
        delta = k * (score_a - expected_a)
        ratings[fighter] = ra + delta
        if opp_in_roster:
            ratings[opp] = rb - delta

    ranking = [{"rank": i + 1, "fighter": name, "elo": round(elo)}
               for i, (name, elo) in enumerate(sorted(ratings.items(), key=lambda kv: -kv[1]))]
    out: dict = {"k_factor": K, "base": BASE, "ranking": ranking}

    if fighter_a and fighter_b:
        fa, fb = _get_fighter(fighter_a), _get_fighter(fighter_b)
        ea = ratings.get(fa["name"], BASE) if fa else BASE   # custom -> 1500
        eb = ratings.get(fb["name"], BASE) if fb else BASE
        out["matchup"] = {
            "fighter_a": fighter_a, "elo_a": round(ea),
            "fighter_b": fighter_b, "elo_b": round(eb),
            "delta": round(ea - eb),
            "elo_win_probability_a_pct": round(100 / (1 + 10 ** ((eb - ea) / 400)), 1),
        }
    return out


def submit_final_report(**kwargs) -> dict:
    """Tool 'puits' : la boucle agent interprète cet appel comme le signal d'arrêt."""
    return {"status": "received", **kwargs}


# ---------------------------------------------------------------------------
# Schemas Anthropic (tool use) + table de dispatch
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "name": "get_fighter_stats",
        "description": "Renvoie la fiche technique complète d'un combattant depuis la base UFC : mensurations, "
                        "record, stance, précision et volume de frappe, lutte, taux de KO/soumission, menton, "
                        "cardio, puissance, tags de style.",
        "input_schema": {
            "type": "object",
            "properties": {"fighter_name": {"type": "string", "description": "Nom du combattant"}},
            "required": ["fighter_name"],
        },
    },
    {
        "name": "get_fight_history",
        "description": "Renvoie les derniers combats d'un combattant (adversaire, résultat W/L, méthode, round, "
                        "event, date) — utile pour repérer comment il gagne et comment il a perdu.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fighter_name": {"type": "string"},
                "n": {"type": "integer", "description": "Nombre de combats (défaut 5)"},
            },
            "required": ["fighter_name"],
        },
    },
    {
        "name": "get_betting_odds",
        "description": "Renvoie les cotes de Vegas actuelles et d'ouverture du combattant (format américain, "
                        "ex: -150 favori / +130 outsider), la probabilité implicite du marché et le mouvement de ligne.",
        "input_schema": {
            "type": "object",
            "properties": {"fighter_name": {"type": "string"}},
            "required": ["fighter_name"],
        },
    },
    {
        "name": "search_fight_reports",
        "description": "Recherche vectorielle (RAG) dans les notes de scouting des analystes : failles stylistiques, "
                        "tendances tactiques, points faibles cachés (ex: 'faiblesse face aux lutteurs', 'menton fragile', "
                        "'cardio en championship rounds'). À utiliser pour VÉRIFIER une hypothèse plutôt que deviner.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Requête en langage naturel"},
                "fighter_name": {"type": "string", "description": "Filtrer sur un combattant précis (optionnel)"},
                "k": {"type": "integer", "description": "Nombre de passages (défaut 3)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "compare_styles",
        "description": "Compare deux combattants : archétypes (Striker/Grappler/Mixte), deltas d'allonge/taille/cardio, "
                        "matrice puissance-vs-menton, et alertes automatiques de mismatch (risque KO, risque sol).",
        "input_schema": {
            "type": "object",
            "properties": {
                "fighter_a": {"type": "string"},
                "fighter_b": {"type": "string"},
            },
            "required": ["fighter_a", "fighter_b"],
        },
    },
    {
        "name": "simulate_fight",
        "description": "Simulation Monte-Carlo de N combats complets (défaut 500) : chaque round est simulé avec le "
                        "cardio décroissant, la précision vs la défense, la probabilité de KO (puissance vs menton) et "
                        "de soumission (grappling vs TDD). Renvoie les probabilités de victoire EXACTES, la répartition "
                        "des méthodes et le scénario le plus probable. OBLIGATOIRE avant submit_final_report : les "
                        "probabilités du rapport final doivent partir de ce résultat.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fighter_a": {"type": "string"},
                "fighter_b": {"type": "string"},
                "n_simulations": {"type": "integer", "description": "Combats simulés (défaut 500)"},
                "rounds": {"type": "integer", "description": "3 (défaut) ou 5 pour un main event"},
            },
            "required": ["fighter_a", "fighter_b"],
        },
    },
    {
        "name": "get_elo_ratings",
        "description": "Classement ELO dynamique du roster (K=32, base 1500), calculé chronologiquement sur les "
                        "historiques réels avec prise en compte de la qualité d'opposition (bonus finish x1.25). "
                        "Si fighter_a et fighter_b sont fournis, renvoie aussi le delta ELO du matchup et la "
                        "probabilité de victoire théorique associée — à citer dans le rapport.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fighter_a": {"type": "string", "description": "Combattant A du matchup courant (optionnel)"},
                "fighter_b": {"type": "string", "description": "Combattant B du matchup courant (optionnel)"},
            },
        },
    },
    {
        "name": "simulate_fight_playbyplay",
        "description": "Génère la timeline détaillée événement-par-événement d'UN combat simulé (un tirage de la "
                        "distribution Monte-Carlo) : chaque coup, takedown, contrôle au sol, avec dégâts, commentaire "
                        "et issue. Sert au Fight Simulator 3D ; utile aussi pour illustrer UN scénario concret du combat.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fighter_a": {"type": "string"},
                "fighter_b": {"type": "string"},
                "rounds": {"type": "integer", "description": "3 (défaut) ou 5"},
                "seed": {"type": "integer", "description": "Graine aléatoire pour rejouer le même scénario (optionnel)"},
            },
            "required": ["fighter_a", "fighter_b"],
        },
    },
    {
        "name": "submit_final_report",
        "description": "À appeler UNE SEULE FOIS, en tout dernier, pour livrer le rapport stratégique final. "
                        "Ne pas appeler d'autre tool après.",
        "input_schema": {
            "type": "object",
            "properties": {
                "victory_probability_a": {"type": "number", "description": "Probabilité de victoire de A (0-100), ancrée sur simulate_fight"},
                "victory_probability_b": {"type": "number", "description": "Probabilité de victoire de B (0-100)"},
                "predicted_method": {"type": "string", "description": "Méthode + round les plus probables (ex: 'KO/TKO round 2')"},
                "keys_to_victory_a": {"type": "array", "items": {"type": "string"},
                                       "description": "3-4 clés de victoire concrètes pour A"},
                "keys_to_victory_b": {"type": "array", "items": {"type": "string"},
                                       "description": "3-4 clés de victoire concrètes pour B"},
                "game_plan_a": {"type": "string", "description": "Gameplan détaillé pour A (2-4 phrases)"},
                "game_plan_b": {"type": "string", "description": "Gameplan détaillé pour B (2-4 phrases)"},
                "vegas_analysis": {"type": "string", "description": "1-2 phrases : ta prédiction vs les cotes du marché — y a-t-il de la value ?"},
                "summary": {"type": "string", "description": "Synthèse de l'analyse (2-3 phrases), mentionnant tout ajustement vs la simulation"},
            },
            "required": [
                "victory_probability_a", "victory_probability_b", "predicted_method",
                "keys_to_victory_a", "keys_to_victory_b", "game_plan_a", "game_plan_b", "summary",
            ],
        },
    },
]

TOOL_DISPATCH = {
    "get_fighter_stats": lambda args: get_fighter_stats(**args),
    "get_fight_history": lambda args: get_fight_history(**args),
    "get_betting_odds": lambda args: get_betting_odds(**args),
    "search_fight_reports": lambda args: search_fight_reports(**args),
    "compare_styles": lambda args: compare_styles(**args),
    "simulate_fight": lambda args: simulate_fight(**args),
    "get_elo_ratings": lambda args: get_elo_ratings(**args),
    "simulate_fight_playbyplay": lambda args: simulate_fight_playbyplay(**args),
    "submit_final_report": lambda args: submit_final_report(**args),
}


# ---------------------------------------------------------------------------
# Mini-test console : python -m src.tools
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    tl = simulate_fight_playbyplay("Khabib Nurmagomedov", "Justin Gaethje", seed=10)
    by_round: dict[int, int] = {}
    td = {"a": 0, "b": 0}
    for e in tl["events"]:
        by_round[e["round"]] = by_round.get(e["round"], 0) + 1
        if e["action"] == "takedown_attempt":
            td[e["actor"]] += 1
    print(f"{tl['fighter_a']} vs {tl['fighter_b']} — {len(tl['events'])} événements")
    for rnd, n in sorted(by_round.items()):
        print(f"  round {rnd}: {n} événements")
        assert 10 <= n <= 36, f"round {rnd}: {n} événements hors fourchette"
    print(f"  tentatives de takedown : Khabib={td['a']}  Gaethje={td['b']}")
    assert td["a"] > td["b"], "Khabib (5.3 TD/15min) doit tirer plus que Gaethje (0.2)"
    r = tl["result"]
    for field in ("winner", "winner_name", "method", "round", "time",
                  "final_health", "scorecards", "stats_summary"):
        assert field in r, f"champ manquant: {field}"
    print(f"  résultat : {r['winner_name']} par {r['method']} R{r['round']} {r['time']}")
    print(f"  stats     : {r['stats_summary']}")
    print("MINI-TEST OK")
