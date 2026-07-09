"""
agent/tools.py
---------------
Les "tools" de l'agent (Lab 4 / MCP). Chaque fonction Python ci-dessous a un
équivalent JSON-Schema dans TOOL_SCHEMAS afin d'être proposée telle quelle à
l'API Anthropic (tool use / function calling). C'est la même interface qu'un
vrai serveur MCP exposerait : voir agent/mcp_server.py pour une version qui
tourne réellement sur le protocole MCP (bonus).

Tools exposés :
- get_fighter_stats(name)        -> fiche technique d'un combattant
- get_fight_history(name, n)     -> historique de ses derniers combats
- search_fight_reports(query)    -> RAG sur les comptes-rendus texte
- compare_styles(name_a, name_b) -> deltas physiques + alertes de style
- simulate_round(...)            -> simulation mathématique d'un round
"""
import json
import random
from pathlib import Path

from .rag import get_rag

DATA_DIR = Path(__file__).parent.parent / "data"

with open(DATA_DIR / "fighters.json", "r", encoding="utf-8") as f:
    _FIGHTERS = json.load(f)

_FIGHTERS_BY_NAME = {f["name"].lower(): f for f in _FIGHTERS}


def _resolve(name: str):
    """Résolution tolérante (casse, sous-chaîne) du nom de combattant."""
    key = name.lower().strip()
    if key in _FIGHTERS_BY_NAME:
        return _FIGHTERS_BY_NAME[key]
    for fname, fighter in _FIGHTERS_BY_NAME.items():
        if key in fname or fname in key:
            return fighter
    return None


def list_fighters():
    """Utilitaire (pas un tool LLM) pour peupler les menus déroulants Streamlit."""
    return [f["name"] for f in _FIGHTERS]


# ---------------------------------------------------------------------------
# TOOLS
# ---------------------------------------------------------------------------

def get_fighter_stats(name: str) -> dict:
    fighter = _resolve(name)
    if not fighter:
        return {"error": f"Combattant '{name}' introuvable dans la base."}
    return fighter


def get_fight_history(name: str, n: int = 5) -> dict:
    rag = get_rag()
    reports = [r for r in rag.reports if r["fighter"].lower() == name.lower()]
    if not reports:
        # fallback tolérant sur sous-chaîne
        reports = [r for r in rag.reports if name.lower() in r["fighter"].lower()]
    if not reports:
        return {"error": f"Aucun historique trouvé pour '{name}'."}
    return {"fighter": name, "fights": reports[:n]}


def search_fight_reports(query: str, fighter_name: str | None = None, k: int = 3) -> dict:
    rag = get_rag()
    results = rag.search(query, k=k, fighter_name=fighter_name)
    return {"query": query, "results": results}


def compare_styles(name_a: str, name_b: str) -> dict:
    a, b = _resolve(name_a), _resolve(name_b)
    if not a or not b:
        return {"error": "Un des deux combattants est introuvable."}

    alerts = []
    if a["reach_cm"] - b["reach_cm"] >= 8:
        alerts.append(f"{a['name']} a un avantage d'allonge net (+{a['reach_cm'] - b['reach_cm']} cm).")
    elif b["reach_cm"] - a["reach_cm"] >= 8:
        alerts.append(f"{b['name']} a un avantage d'allonge net (+{b['reach_cm'] - a['reach_cm']} cm).")

    if a["takedown_avg_per_15min"] >= 3 and b["takedown_defense_pct"] < 70:
        alerts.append(f"{a['name']} projette beaucoup (>{a['takedown_avg_per_15min']}/15min) "
                       f"et la défense de takedown de {b['name']} est faible ({b['takedown_defense_pct']}%): risque au sol pour {b['name']}.")
    if b["takedown_avg_per_15min"] >= 3 and a["takedown_defense_pct"] < 70:
        alerts.append(f"{b['name']} projette beaucoup (>{b['takedown_avg_per_15min']}/15min) "
                       f"et la défense de takedown de {a['name']} est faible ({a['takedown_defense_pct']}%): risque au sol pour {a['name']}.")

    if a["cardio_rating"] - b["cardio_rating"] >= 3:
        alerts.append(f"{a['name']} a un net avantage de cardio, un combat qui va tard peut favoriser {a['name']}.")
    elif b["cardio_rating"] - a["cardio_rating"] >= 3:
        alerts.append(f"{b['name']} a un net avantage de cardio, un combat qui va tard peut favoriser {b['name']}.")

    return {
        "fighter_a": a["name"],
        "fighter_b": b["name"],
        "reach_diff_cm": a["reach_cm"] - b["reach_cm"],
        "height_diff_cm": a["height_cm"] - b["height_cm"],
        "alerts": alerts or ["Pas de mismatch physique flagrant, l'issue dépendra surtout du gameplan et du rythme."],
    }


def simulate_round(fighter_a: str, fighter_b: str, round_num: int = 1, seed: int | None = None) -> dict:
    """Simulation mathématique simplifiée d'un round à partir des stats.
    Combine striking, wrestling et cardio (dégradé au fil des rounds) pour
    produire une probabilité de round gagné par chaque combattant + un
    évènement notable (KO/soumission) tiré aléatoirement mais pondéré.
    """
    a, b = _resolve(fighter_a), _resolve(fighter_b)
    if not a or not b:
        return {"error": "Un des deux combattants est introuvable."}

    rng = random.Random(seed)

    def fatigue_factor(fighter, rnd):
        # Le cardio_rating (1-10) amortit la perte d'efficacité au fil des rounds
        decay_per_round = (10 - fighter["cardio_rating"]) * 0.03
        return max(0.5, 1 - decay_per_round * (rnd - 1))

    fa, fb = fatigue_factor(a, round_num), fatigue_factor(b, round_num)

    striking_score_a = a["striking_accuracy_pct"] * fa + a["ko_rate_pct"] * 0.2
    striking_score_b = b["striking_accuracy_pct"] * fb + b["ko_rate_pct"] * 0.2

    grappling_score_a = a["takedown_avg_per_15min"] * 10 * fa + a["submission_rate_pct"] * 0.3 \
        - b["takedown_defense_pct"] * 0.15
    grappling_score_b = b["takedown_avg_per_15min"] * 10 * fb + b["submission_rate_pct"] * 0.3 \
        - a["takedown_defense_pct"] * 0.15

    score_a = max(0.0, striking_score_a + max(0, grappling_score_a))
    score_b = max(0.0, striking_score_b + max(0, grappling_score_b))
    total = score_a + score_b if (score_a + score_b) > 0 else 1
    prob_a = round(score_a / total, 3)
    prob_b = round(1 - prob_a, 3)

    # évènement notable (KO/soumission), pondéré par les taux de finish et un peu d'aléatoire
    finish_chance_a = (a["ko_rate_pct"] + a["submission_rate_pct"]) / 2 / 100 * fa * 0.35
    finish_chance_b = (b["ko_rate_pct"] + b["submission_rate_pct"]) / 2 / 100 * fb * 0.35
    roll = rng.random()
    event = None
    if roll < finish_chance_a:
        method = "KO/TKO" if a["ko_rate_pct"] >= a["submission_rate_pct"] else "Soumission"
        event = f"{a['name']} termine le combat par {method} au round {round_num}."
    elif roll < finish_chance_a + finish_chance_b:
        method = "KO/TKO" if b["ko_rate_pct"] >= b["submission_rate_pct"] else "Soumission"
        event = f"{b['name']} termine le combat par {method} au round {round_num}."

    return {
        "round": round_num,
        "prob_round_winner_a": prob_a,
        "prob_round_winner_b": prob_b,
        "round_winner": a["name"] if prob_a >= prob_b else b["name"],
        "finish_event": event,
    }


def submit_final_report(**kwargs) -> dict:
    """Tool 'puits' : l'agent l'appelle pour livrer son rapport final structuré.
    On ne fait ici que valider/retourner le payload — c'est la boucle agent
    (agent_loop.py) qui interprète l'appel à ce tool comme le signal d'arrêt.
    """
    return {"status": "received", **kwargs}


# ---------------------------------------------------------------------------
# Schemas Anthropic (tool use) + table de dispatch
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "name": "get_fighter_stats",
        "description": "Renvoie la fiche technique complète d'un combattant : taille, allonge, record, "
                        "style principal, précision de frappe, défense de takedown, taux de finish, cardio...",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Nom du combattant"}},
            "required": ["name"],
        },
    },
    {
        "name": "get_fight_history",
        "description": "Renvoie les derniers combats d'un combattant (adversaire, résultat, méthode, round).",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nom du combattant"},
                "n": {"type": "integer", "description": "Nombre de combats à renvoyer (défaut 5)"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "search_fight_reports",
        "description": "Recherche RAG dans les comptes-rendus texte des combats passés (ex: 'faiblesses au sol', "
                        "'défense de takedown', 'chin fragile'). Utile pour creuser une hypothèse qualitative.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Requête en langage naturel"},
                "fighter_name": {"type": "string", "description": "Filtrer sur un combattant précis (optionnel)"},
                "k": {"type": "integer", "description": "Nombre de résultats (défaut 3)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "compare_styles",
        "description": "Compare deux combattants (allonge, taille, cardio, tendance au takedown) et "
                        "remonte des alertes de style automatiques (ex: mismatch d'allonge, risque au sol).",
        "input_schema": {
            "type": "object",
            "properties": {
                "name_a": {"type": "string"},
                "name_b": {"type": "string"},
            },
            "required": ["name_a", "name_b"],
        },
    },
    {
        "name": "simulate_round",
        "description": "Simule mathématiquement l'issue probable d'un round donné entre deux combattants à "
                        "partir de leurs stats (striking, grappling, fatigue). Renvoie des probabilités et un "
                        "éventuel évènement de fin de combat.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fighter_a": {"type": "string"},
                "fighter_b": {"type": "string"},
                "round_num": {"type": "integer", "description": "Numéro du round simulé (1 à 5)"},
            },
            "required": ["fighter_a", "fighter_b"],
        },
    },
    {
        "name": "submit_final_report",
        "description": "À appeler UNE SEULE FOIS, en tout dernier, quand l'enquête est terminée, pour livrer le "
                        "rapport stratégique final structuré. Ne pas appeler d'autre tool après celui-ci.",
        "input_schema": {
            "type": "object",
            "properties": {
                "victory_probability_a": {"type": "number", "description": "Probabilité de victoire du combattant A, entre 0 et 100"},
                "victory_probability_b": {"type": "number", "description": "Probabilité de victoire du combattant B, entre 0 et 100"},
                "predicted_method": {"type": "string", "description": "Méthode de victoire la plus probable (ex: 'Soumission round 2')"},
                "keys_to_victory_a": {
                    "type": "array", "items": {"type": "string"},
                    "description": "3 à 4 clés de victoire concrètes pour le combattant A",
                },
                "keys_to_victory_b": {
                    "type": "array", "items": {"type": "string"},
                    "description": "3 à 4 clés de victoire concrètes pour le combattant B",
                },
                "game_plan_a": {"type": "string", "description": "Gameplan détaillé recommandé pour A (2-4 phrases)"},
                "game_plan_b": {"type": "string", "description": "Gameplan détaillé recommandé pour B (2-4 phrases)"},
                "summary": {"type": "string", "description": "Synthèse courte (2-3 phrases) de l'analyse globale du matchup"},
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
    "search_fight_reports": lambda args: search_fight_reports(**args),
    "compare_styles": lambda args: compare_styles(**args),
    "simulate_round": lambda args: simulate_round(**args),
    "submit_final_report": lambda args: submit_final_report(**args),
}
