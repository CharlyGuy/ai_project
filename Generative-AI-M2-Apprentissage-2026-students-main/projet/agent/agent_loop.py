"""
agent/agent_loop.py
--------------------
La boucle agentique (Lab 5) : Reason -> Act -> Observe, pilotée par
claude-haiku-4-5 via l'API Messages (tool use).

- Reason  : le modèle écrit un court raisonnement (texte) avant/entre les appels d'outils.
- Act     : le modèle émet un `tool_use` (get_fighter_stats, simulate_round, ...).
- Observe : on exécute réellement le tool en Python et on renvoie le résultat
            comme `tool_result` dans le message suivant.

La boucle s'arrête quand le modèle appelle le tool `submit_final_report`
(ou après MAX_TURNS tours, par sécurité).

Chaque étape est poussée dans `trace_callback(step: dict)` pour alimenter le
"live trace" de l'interface Streamlit en temps réel.
"""
import json
import os
from typing import Callable, Optional

import anthropic

from .tools import TOOL_SCHEMAS, TOOL_DISPATCH

MODEL = "claude-haiku-4-5"
MAX_TURNS = 8

SYSTEM_PROMPT = """Tu es "FightStrategist AI", un matchmaker et entraîneur expert en MMA/boxe/kickboxing.
On te donne deux combattants (A et B). Ta mission : mener une enquête autonome sur les deux, en utilisant
les tools disponibles, pour produire un rapport stratégique de matchup.

Méthode attendue (Reason -> Act -> Observe) :
1. Récupère d'abord les stats de base des deux combattants (get_fighter_stats).
2. Regarde leur historique récent (get_fight_history) pour repérer des patterns (comment ils gagnent, comment
   ils ont perdu).
3. Utilise compare_styles pour détecter les mismatchs physiques/stylistiques évidents.
4. Dès qu'une hypothèse te vient (ex: "B a une mauvaise défense de takedown, A doit l'emmener au sol"),
   creuse-la avec search_fight_reports au lieu de deviner.
5. Simule 2 ou 3 rounds clés avec simulate_round pour étayer ta prédiction avec des chiffres.
6. Termine TOUJOURS par un unique appel à submit_final_report avec ton verdict complet. N'appelle aucun
   autre tool après submit_final_report.

Avant chaque appel de tool, explique en une phrase courte ce que tu cherches à savoir et pourquoi (ton
raisonnement doit être visible dans le texte, pas seulement dans l'appel d'outil). Reste concis : 5 à 8
appels de tools au total suffisent, inutile de tout re-demander plusieurs fois.
Réponds en français.
"""


def _client(api_key: Optional[str] = None) -> anthropic.Anthropic:
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "Aucune clé API trouvée. Renseigne ANTHROPIC_API_KEY dans ton .env ou dans la sidebar Streamlit."
        )
    return anthropic.Anthropic(api_key=key)


def run_agent(
    fighter_a: str,
    fighter_b: str,
    trace_callback: Callable[[dict], None],
    api_key: Optional[str] = None,
) -> dict:
    """Lance la boucle agentique complète pour un matchup A vs B.

    trace_callback reçoit des dicts de la forme:
      {"type": "thought", "text": "..."}
      {"type": "action", "tool": "...", "input": {...}}
      {"type": "observation", "tool": "...", "output": {...}}
      {"type": "final", "report": {...}}
    et est appelé en direct pendant l'exécution (pour l'UI Streamlit live trace).
    """
    client = _client(api_key)

    messages = [
        {
            "role": "user",
            "content": (
                f"Analyse le matchup suivant : {fighter_a} (combattant A) vs {fighter_b} (combattant B). "
                f"Mène ton enquête puis livre le rapport stratégique complet via submit_final_report."
            ),
        }
    ]

    final_report = None

    for turn in range(MAX_TURNS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )

        assistant_content = []
        tool_results = []
        stop = False

        for block in response.content:
            if block.type == "text" and block.text.strip():
                trace_callback({"type": "thought", "text": block.text.strip()})
                assistant_content.append({"type": "text", "text": block.text})

            elif block.type == "tool_use":
                trace_callback({"type": "action", "tool": block.name, "input": block.input})
                assistant_content.append(
                    {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
                )

                if block.name == "submit_final_report":
                    final_report = block.input
                    trace_callback({"type": "final", "report": final_report})
                    stop = True
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": "Rapport reçu, fin de l'analyse.",
                        }
                    )
                    continue

                fn = TOOL_DISPATCH.get(block.name)
                if fn is None:
                    output = {"error": f"Tool inconnu: {block.name}"}
                else:
                    try:
                        output = fn(block.input)
                    except Exception as exc:  # sécurité: un tool qui plante ne casse pas la boucle
                        output = {"error": str(exc)}

                trace_callback({"type": "observation", "tool": block.name, "output": output})
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(output, ensure_ascii=False),
                    }
                )

        messages.append({"role": "assistant", "content": assistant_content})

        if stop:
            break

        if tool_results:
            messages.append({"role": "user", "content": tool_results})
        elif response.stop_reason != "tool_use":
            # Le modèle a fini sans appeler submit_final_report : on le relance en insistant.
            messages.append(
                {
                    "role": "user",
                    "content": "Merci de conclure ton analyse en appelant maintenant submit_final_report.",
                }
            )

    if final_report is None:
        final_report = {
            "victory_probability_a": 50,
            "victory_probability_b": 50,
            "predicted_method": "Indéterminé",
            "keys_to_victory_a": [],
            "keys_to_victory_b": [],
            "game_plan_a": "",
            "game_plan_b": "",
            "summary": "L'agent n'a pas produit de rapport final dans le nombre de tours imparti.",
        }
        trace_callback({"type": "final", "report": final_report})

    return final_report
