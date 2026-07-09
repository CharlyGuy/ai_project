"""
src/mcp_server.py
-----------------
Les mêmes outils que src/tools.py, exposés via le protocole officiel MCP
(Model Context Protocol) en transport stdio — connectables tels quels à
Claude Desktop, Claude Code, ou n'importe quel client MCP.

Lancement direct :
    python -m src.mcp_server        # depuis projet/
ou inspection interactive :
    mcp dev src/mcp_server.py

Enregistrement Claude Desktop (claude_desktop_config.json) :
    {
      "mcpServers": {
        "ufc-insights": {
          "command": "/chemin/absolu/vers/genai_env/bin/python3",
          "args": ["-m", "src.mcp_server"],
          "cwd": "/chemin/absolu/vers/projet"
        }
      }
    }
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import tools

mcp = FastMCP("ufc-insights")


@mcp.tool()
def get_fighter_stats(fighter_name: str) -> dict:
    """Fiche technique complète d'un combattant UFC : mensurations, record, striking, lutte, menton, cardio, puissance."""
    return tools.get_fighter_stats(fighter_name)


@mcp.tool()
def get_fight_history(fighter_name: str, n: int = 5) -> dict:
    """Les n derniers combats d'un combattant (adversaire, résultat, méthode, round, event, date)."""
    return tools.get_fight_history(fighter_name, n)


@mcp.tool()
def get_betting_odds(fighter_name: str) -> dict:
    """Cotes de Vegas actuelles et d'ouverture (format américain) + probabilité implicite du marché."""
    return tools.get_betting_odds(fighter_name)


@mcp.tool()
def search_fight_reports(query: str, fighter_name: str | None = None, k: int = 3) -> dict:
    """Recherche vectorielle dans les notes de scouting : failles stylistiques et tendances tactiques."""
    return tools.search_fight_reports(query, fighter_name, k)


@mcp.tool()
def compare_styles(fighter_a: str, fighter_b: str) -> dict:
    """Compare deux combattants : archétypes, deltas physiques, matrice puissance-vs-menton, alertes de mismatch."""
    return tools.compare_styles(fighter_a, fighter_b)


@mcp.tool()
def simulate_fight(fighter_a: str, fighter_b: str, n_simulations: int = 500, rounds: int = 3) -> dict:
    """Simulation Monte-Carlo de N combats complets ; renvoie les probabilités de victoire calculées et la répartition des méthodes."""
    return tools.simulate_fight(fighter_a, fighter_b, n_simulations, rounds)


if __name__ == "__main__":
    mcp.run()
