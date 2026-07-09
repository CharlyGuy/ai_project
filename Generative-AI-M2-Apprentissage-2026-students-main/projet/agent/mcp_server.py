"""
agent/mcp_server.py
--------------------
BONUS (optionnel, pas nécessaire pour faire tourner l'app Streamlit) :
expose les mêmes tools via un vrai serveur MCP (protocole officiel), en
utilisant le SDK `mcp` (FastMCP). Cela permet de brancher exactement les
mêmes outils sur Claude Desktop, Claude Code ou n'importe quel client MCP,
en plus de l'usage "tool use" direct utilisé par app.py.

Installation :
    pip install mcp

Lancement en mode dev (inspecteur MCP) :
    mcp dev agent/mcp_server.py

Le coeur de l'app (Streamlit) N'A PAS besoin de ce fichier : il appelle les
fonctions de agent/tools.py directement via l'API tool-use d'Anthropic, ce
qui évite de gérer un process serveur MCP séparé pour un simple POC. Ce
fichier montre juste que la même logique de tools est 100% compatible MCP.
"""
from mcp.server.fastmcp import FastMCP

from . import tools as t

mcp = FastMCP("fight-strategist")


@mcp.tool()
def get_fighter_stats(name: str) -> dict:
    """Renvoie la fiche technique complète d'un combattant."""
    return t.get_fighter_stats(name)


@mcp.tool()
def get_fight_history(name: str, n: int = 5) -> dict:
    """Renvoie les derniers combats d'un combattant."""
    return t.get_fight_history(name, n)


@mcp.tool()
def search_fight_reports(query: str, fighter_name: str | None = None, k: int = 3) -> dict:
    """Recherche RAG dans les comptes-rendus de combats passés."""
    return t.search_fight_reports(query, fighter_name, k)


@mcp.tool()
def compare_styles(name_a: str, name_b: str) -> dict:
    """Compare deux combattants et remonte des alertes de style."""
    return t.compare_styles(name_a, name_b)


@mcp.tool()
def simulate_round(fighter_a: str, fighter_b: str, round_num: int = 1) -> dict:
    """Simule mathématiquement un round entre deux combattants."""
    return t.simulate_round(fighter_a, fighter_b, round_num)


if __name__ == "__main__":
    mcp.run()
