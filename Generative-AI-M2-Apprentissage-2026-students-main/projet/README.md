# 🥊 FightStrategist AI

**Track 1 — Innovation libre.** Agent autonome de scouting & de gameplan pour un combat de MMA / boxe /
kickboxing. On choisit deux combattants, l'agent enquête seul (stats, historique, comptes-rendus texte),
simule le combat, et livre un rapport stratégique avec probabilité de victoire et gameplan pour chacun.

## 1. Pourquoi c'est un agent (et pas juste un prompt)

D'après le litmus test du README du hackathon : *"Puis-je répondre correctement en un coup, sans rien
chercher ni rien changer ?"* — Non, ici :

- Le modèle **ne connaît pas par cœur** les stats de chaque combattant mockées dans `data/` → il doit
  appeler des **tools** (`get_fighter_stats`, `get_fight_history`).
- Le **nombre d'étapes n'est pas connu à l'avance** : selon les combattants, l'agent creuse plus ou moins
  d'hypothèses avant de conclure.
- Il **réagit à ses propres observations** : ex. il regarde `compare_styles`, voit que la défense de
  takedown de B est faible, puis va chercher spécifiquement dans `search_fight_reports` si B a déjà été
  soumis par le passé — une boucle Reason → Act → Observe classique.
- La prédiction finale est **construite par itération** (plusieurs `simulate_round` sur différents rounds)
  et non générée en un seul jet.

## 2. Architecture & mapping avec les 5 labs

| Brique | Fichier | Lab correspondant |
|---|---|---|
| Vectorisation + recherche sémantique sur les comptes-rendus de combats | `agent/rag.py` | Lab 3 — Embeddings & RAG |
| Outils typés (schémas JSON) exposés au modèle, + version protocole MCP réel en bonus | `agent/tools.py`, `agent/mcp_server.py` | Lab 4 — MCP |
| Boucle Reason → Act → Observe pilotée par `claude-haiku-4-5` (tool use) | `agent/agent_loop.py` | Lab 5 — Agent loop |
| Interface web + "Tale of the Tape" + live trace | `app.py` (Streamlit) | Wrapping produit |

```
projet/
├── app.py                 # Interface Streamlit (UI + orchestration)
├── agent/
│   ├── agent_loop.py       # Boucle agentique Reason→Act→Observe (Anthropic tool use)
│   ├── tools.py            # 6 tools + schémas JSON pour l'API Anthropic
│   ├── rag.py               # Index TF-IDF sur les comptes-rendus de combats
│   └── mcp_server.py         # (bonus) mêmes tools exposés via un vrai serveur MCP
├── data/
│   ├── fighters.json         # Fiches techniques (mock)
│   └── fight_reports.json     # Corpus texte pour le RAG (mock)
├── requirements.txt
├── .env.example
└── README.md
```

### Les 6 tools de l'agent

| Tool | Rôle |
|---|---|
| `get_fighter_stats(name)` | Taille, allonge, record, style, % de frappe, cardio... |
| `get_fight_history(name, n)` | Derniers combats (adversaire, méthode, round) |
| `search_fight_reports(query, fighter_name?)` | RAG texte libre ("faiblesses au sol de X") |
| `compare_styles(name_a, name_b)` | Deltas physiques + alertes de mismatch automatiques |
| `simulate_round(fighter_a, fighter_b, round_num)` | Simulation mathématique d'un round (striking + grappling + fatigue) |
| `submit_final_report(...)` | Tool "puits" : signal de fin de boucle + rapport structuré |

> **Note MCP :** pour ce POC, l'agent appelle les tools directement en process via l'API *tool use*
> d'Anthropic — c'est le pattern enseigné au TD4, seulement sans lancer un process serveur séparé (plus
> simple à déployer pour un hackathon). `agent/mcp_server.py` expose exactement les mêmes fonctions via un
> vrai serveur MCP (`pip install mcp`, puis `mcp dev agent/mcp_server.py`) pour montrer que la même couche
> d'outils est 100% compatible MCP et branchable sur Claude Desktop / Claude Code.

### RAG (Lab 3)

`agent/rag.py` vectorise `data/fight_reports.json` avec un TF-IDF (scikit-learn) et fait de la recherche
par similarité cosinus. C'est volontairement léger (pas de téléchargement de modèle, fonctionne offline) —
l'interface `search(query, k)` est celle d'un vrai store vectoriel : on peut brancher un vrai modèle
d'embeddings à la place de `TfidfVectorizer` sans toucher au reste de l'agent.

## 3. Installation & lancement

```bash
cd projet
python -m venv .venv && source .venv/bin/activate   # optionnel mais recommandé
pip install -r requirements.txt

cp .env.example .env
# puis édite .env et colle ta clé ANTHROPIC_API_KEY

streamlit run app.py
```

L'app s'ouvre sur `http://localhost:8501`. Si tu ne veux pas utiliser de `.env`, tu peux coller ta clé
directement dans la sidebar de l'app (elle n'est jamais écrite sur disque).

**Modèle utilisé : `claude-haiku-4-5`** (contrainte du hackathon — budget API limité).

## 4. Utilisation

1. Choisis un **Combattant A** et un **Combattant B** dans les menus déroulants (10 combattants mockés,
   MMA/boxe/kickboxing).
2. La **Tale of the Tape** s'affiche immédiatement (comparaison stats, sans appel LLM).
3. Clique sur **🚀 Lancer l'Analyse Stratégique**.
4. Le **Live Trace** affiche en direct les pensées de l'agent (🧠), ses appels d'outils (⚙️) et les
   résultats obtenus (👁️).
5. Le **Rapport Stratégique** final s'affiche : probabilité de victoire, méthode prédite, clés de victoire
   et gameplan détaillé pour chaque combattant.

## 5. Données

Les fiches (`data/fighters.json`) et les comptes-rendus (`data/fight_reports.json`) sont des **données
mockées à but pédagogique** : les records/statistiques sont approximatifs et ne doivent pas être considérés
comme une source officielle. C'est volontaire — le sujet autorise explicitement les données mockées pour se
concentrer sur la boucle agentique plutôt que sur l'intégration d'une vraie API sportive.

Pour aller plus loin : remplacer `data/*.json` par un vrai scraping (Sherdog, Tapology...) ou une vraie API
sportive ne demande aucun changement dans `agent/agent_loop.py` — seuls `agent/tools.py` (source des
données) serait à adapter.

## 6. Pistes d'extension (non implémentées, pour la pitch)

- Vrai store vectoriel (Chroma / pgvector) à la place du TF-IDF.
- Génération d'image "affiche de combat" pour le rapport final.
- Historique des analyses passées (mémoire long-terme de l'agent).
- Mode "conseil coin" : l'agent ajuste le gameplan round par round en direct pendant un combat simulé.
