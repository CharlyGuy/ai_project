"""
src/agent_loop.py
-----------------
La boucle agentique Reason → Act → Observe, pilotée par Claude Haiku via l'API
Messages d'Anthropic (tool use natif).

`run_agent_stream` est un GÉNÉRATEUR : il yield chaque étape en temps réel
(pensée / action / observation / rapport final) pour alimenter le live trace
Streamlit au fur et à mesure — pas de callback, on consomme le flux avec un
simple `for step in run_agent_stream(...)`.

La boucle s'arrête dès que le modèle appelle `submit_final_report`, ou après
MAX_TURNS itérations (garde-fou anti-runaway).

Note modèle : on utilise `claude-haiku-4-5` (génération actuelle de Haiku,
successeur de claude-3-5-haiku — même tier de prix, meilleur tool use).
"""
from __future__ import annotations

import json
import os
from typing import Generator, Optional

import anthropic

from .tools import TOOL_SCHEMAS, TOOL_DISPATCH

MODEL = "claude-haiku-4-5"
MAX_TURNS = 8

SYSTEM_PROMPT = """Tu es "FightStrategist AI", l'analyste en chef du UFC Performance Institute.
On te donne deux combattants (A et B). Mène une enquête AUTONOME et STRICTE en 5 phases, dans cet ordre :

PHASE 1 — COLLECTE : récupère la fiche technique des deux combattants (get_fighter_stats) et leur
historique récent (get_fight_history). Repère comment ils gagnent et comment ils ont perdu.
PHASE 2 — MARCHÉ & STYLE : consulte les cotes de Vegas des deux hommes (get_betting_odds) et lance
compare_styles pour détecter les mismatchs physiques et stylistiques (allonge, puissance vs menton, sol).
PHASE 3 — FAILLES CACHÉES : formule 1 ou 2 hypothèses à partir des phases 1-2 (ex: "B recule sous la
pression linéaire") et VÉRIFIE-les dans les notes de scouting via search_fight_reports au lieu de deviner.
PHASE 4 — SIMULATION : lance simulate_fight (Monte-Carlo de 500 combats complets). C'est CE tool qui
fournit la probabilité de victoire chiffrée — pas ton intuition.
PHASE 5 — SYNTHÈSE : termine par UN SEUL appel à submit_final_report. Les victory_probability_a/b
DOIVENT partir des probabilités de simulate_fight ; tu peux les ajuster d'au plus ±10 points si tes
découvertes qualitatives (RAG, historique) le justifient, en expliquant l'ajustement dans summary.
Dans vegas_analysis, compare ta prédiction aux probabilités implicites du marché : signale la "value".
N'appelle AUCUN autre tool après submit_final_report.

Avant chaque appel de tool, écris UNE phrase courte disant ce que tu cherches et pourquoi (ton
raisonnement doit être visible). Reste efficace : 6 à 9 appels de tools suffisent, ne redemande pas
deux fois la même chose. Réponds en français."""


def _client(api_key: Optional[str] = None) -> anthropic.Anthropic:
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "Aucune clé API trouvée. Renseigne ANTHROPIC_API_KEY dans ton .env ou dans la sidebar."
        )
    return anthropic.Anthropic(api_key=key)


def run_agent_stream(
    fighter_a: str,
    fighter_b: str,
    api_key: Optional[str] = None,
    max_turns: int = MAX_TURNS,
) -> Generator[dict, None, None]:
    """Boucle agentique complète pour le matchup A vs B, en flux.

    Yield des dicts :
      {"type": "thought", "text": str}
      {"type": "action", "tool": str, "input": dict}
      {"type": "observation", "tool": str, "output": dict}
      {"type": "final", "report": dict}
    """
    client = _client(api_key)
    messages: list[dict] = [
        {
            "role": "user",
            "content": (
                f"Analyse le matchup : {fighter_a} (combattant A, coin bleu) vs {fighter_b} "
                f"(combattant B, coin rouge). Suis tes 5 phases puis livre le rapport via submit_final_report."
            ),
        }
    ]
    final_report: dict | None = None

    for _turn in range(max_turns):
        response = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )

        assistant_content: list[dict] = []
        tool_results: list[dict] = []
        stop = False

        for block in response.content:
            if block.type == "text" and block.text.strip():
                yield {"type": "thought", "text": block.text.strip()}
                assistant_content.append({"type": "text", "text": block.text})

            elif block.type == "tool_use":
                yield {"type": "action", "tool": block.name, "input": dict(block.input)}
                assistant_content.append(
                    {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
                )

                if block.name == "submit_final_report":
                    final_report = dict(block.input)
                    stop = True
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "Rapport reçu, fin de l'analyse.",
                    })
                    continue

                fn = TOOL_DISPATCH.get(block.name)
                if fn is None:
                    output = {"error": f"Tool inconnu : {block.name}"}
                else:
                    try:
                        output = fn(block.input)
                    except Exception as exc:  # un tool qui plante ne casse pas la boucle
                        output = {"error": str(exc)}

                yield {"type": "observation", "tool": block.name, "output": output}
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(output, ensure_ascii=False),
                })

        messages.append({"role": "assistant", "content": assistant_content})
        if stop:
            break
        if tool_results:
            messages.append({"role": "user", "content": tool_results})
        elif response.stop_reason != "tool_use":
            # Le modèle a conclu en texte libre sans passer par submit_final_report : on insiste.
            messages.append({
                "role": "user",
                "content": "Conclus maintenant ton analyse en appelant submit_final_report.",
            })

    if final_report is None:
        final_report = {
            "victory_probability_a": 50, "victory_probability_b": 50,
            "predicted_method": "Indéterminé",
            "keys_to_victory_a": [], "keys_to_victory_b": [],
            "game_plan_a": "", "game_plan_b": "", "vegas_analysis": "",
            "summary": "L'agent n'a pas produit de rapport final dans le nombre de tours imparti.",
        }
    yield {"type": "final", "report": final_report}


def run_baseline(fighter_a: str, fighter_b: str, api_key: Optional[str] = None) -> str:
    """Contre-exemple pédagogique : UN SEUL appel LLM, sans aucun tool.

    Le modèle n'a accès ni à la base SQLite, ni aux notes de scouting, ni au
    simulateur Monte-Carlo : il puise dans sa mémoire d'entraînement (générique,
    figée) et INVENTE les chiffres qu'il avance. À comparer avec l'agent.
    """
    client = _client(api_key)
    resp = client.messages.create(
        model=MODEL,
        max_tokens=1200,
        system=("Tu es un analyste expert en MMA. Réponds en français, de façon structurée et concise."),
        messages=[{
            "role": "user",
            "content": (
                f"Analyse le matchup {fighter_a} vs {fighter_b}. Donne : la probabilité de victoire de "
                f"chacun (en %), la méthode de victoire la plus probable, 3 clés de victoire et un gameplan "
                f"court pour chaque combattant, puis une synthèse de 2-3 phrases."
            ),
        }],
    )
    return "".join(block.text for block in resp.content if block.type == "text")
