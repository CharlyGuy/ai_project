# 🥊 FightStrategist AI v2 — UFC Insights Edition

**Projet de synthèse M2 IASD (Labs 3-4-5 : RAG, MCP, boucle agentique).** Agent autonome de
scouting & gameplan MMA : on choisit deux combattants, l'agent enquête seul (SQLite, RAG,
cotes de Vegas, ELO), lance une simulation Monte-Carlo, et livre un rapport stratégique —
puis le **Fight Simulator 3D** rejoue un scénario du combat en mode jeu vidéo, avec les
vraies photos des combattants.

## 1. Architecture

```
projet/
├── app.py                       # UI Streamlit "broadcast" en 4 onglets
├── src/
│   ├── database.py              # SQLite : 17 combattants réels, historiques, cotes de Vegas
│   ├── rag_engine.py            # RAG vectoriel : ChromaDB persistant + MiniLM (embeddings locaux)
│   ├── tools.py                 # 9 tools (stats, historique, cotes, RAG, styles, Monte-Carlo,
│   │                            #   ELO, timeline play-by-play, rapport final) + custom fighters
│   ├── agent_loop.py            # Boucle Reason→Act→Observe (générateur) · claude-haiku-4-5
│   ├── mcp_server.py            # Les mêmes tools sur le protocole MCP (stdio)
│   ├── assets.py                # Photos locales -> data-URI base64 (zéro CORS)
│   └── fight3d_loader.py        # Assemble le HTML autonome du simulateur 3D
├── static/
│   ├── photos/                  # 17 photos officielles téléchargées une fois (usage local)
│   └── fight3d/                 # Moteur Three.js r128 vendoré (démo 100% offline)
│       ├── engine.js            # Scène octogone, humanoïdes articulés, animations, effets, HUD
│       ├── index.html           # Testable SEUL dans un navigateur (charge sample_fight.js)
│       ├── sample_fight.json/js # Timeline d'exemple (Khabib vs Gaethje)
│       └── three.min.js         # Three.js r128 vendoré
├── scripts/download_photos.py   # Téléchargement one-shot des photos (UFC + Wikipedia, fallback avatar)
├── data/
│   ├── ufc_database.db          # Base SQLite (auto-seedée)
│   └── fight_reports/*.md       # 17 notes de scouting (corpus RAG)
└── chroma_db/                   # Index vectoriel persistant
```

### Flux de bout en bout

```
Sélection A vs B
   ├─> 📋 Tale of the Tape : SQLite -> portraits photo + radar Plotly (sans LLM)
   ├─> 🤖 Analyse Agent    : boucle agentique -> tools (SQLite/RAG/cotes/ELO)
   │        -> simulate_fight (Monte-Carlo 500 combats) -> rapport (probabilité CALCULÉE)
   ├─> ⚔️ Fight Simulator  : simulate_fight_playbyplay -> timeline JSON (+ photos data-URI)
   │        -> fight3d_loader -> moteur Three.js (iframe autonome) -> replay 3D animé
   └─> 🏆 Classement ELO   : fight_history rejouée chronologiquement (K=32, base 1500)
```

## 2. Installation & lancement

```bash
cd projet
pip install -r requirements.txt
python scripts/download_photos.py     # une seule fois (photos locales)
# .env à la racine du repo avec ANTHROPIC_API_KEY=sk-ant-...
streamlit run app.py
```

Le moteur 3D est aussi testable **sans Streamlit** : ouvrir `static/fight3d/index.html`
dans un navigateur (il charge la timeline d'exemple `sample_fight.js`).

Serveur MCP (bonus, connectable à Claude Desktop) : `python -m src.mcp_server`.

**Modèle : `claude-haiku-4-5`** (contrainte hackathon — budget API limité).

## 3. Comment est calculée la probabilité de victoire ?

En deux étages, et le chiffre final vient des maths, pas du LLM :

1. **Modèle de round** (`_round_model`) : scores striking (précision × volume × fatigue) et
   grappling (takedowns × fatigue − défense adverse) ; chances de KO (puissance de l'attaquant
   × taux de KO × fragilité du **menton** adverse) et de soumission (grappling vs défense de
   takedown). La fatigue par round est amortie par le cardio.
2. **Monte-Carlo** (`simulate_fight`) : le combat complet est rejoué **500 fois** ; la
   probabilité affichée est la fréquence empirique de victoire, avec la répartition des
   méthodes (KO/soumission/décision) et la durée moyenne.

Le system prompt impose à l'agent de partir de ce chiffre (ajustement qualitatif borné
**±10 points**, justifié dans la synthèse).

## 4. Arguments de soutenance

**(a) Probabilités calculées, pas hallucinées.** Le bouton *Baseline : LLM seul* montre le
même modèle sans tools : chiffres inventés de mémoire, invérifiables. L'Analyse Elite ancre
chaque affirmation dans un tool call visible (live trace) et la probabilité vient du
Monte-Carlo. Démo : lancer les deux côte à côte.

**(b) Cohérence données → visuel.** Dans le Fight Simulator 3D, **Khabib lutte réellement à
l'écran parce que ses stats le dictent** (5,3 TD/15min → la distribution d'actions de la
timeline est pilotée par le profil : ~17 tentatives de takedown par combat simulé, 0 pour
Gaethje). À l'inverse, Pereira vs Adesanya reste debout. Le visuel n'est pas un habillage :
il rejoue la sortie du même modèle mathématique que le rapport.

**(c) Honnêteté méthodologique.** Anti-leakage (l'agent ne voit que des données antérieures
au combat, jamais l'issue) ; ajustement LLM borné ±10 pts ; la simulation 3D est explicitement
présentée comme *UN tirage de la distribution* (la référence statistique reste le rapport) ;
ELO calculé chronologiquement avec qualité d'opposition ; disclaimer données.

## 5. Innovations data science

- **ELO dynamique** (`get_elo_ratings`) : la table `fight_history` est rejouée en ordre
  chronologique (K=32, base 1500, bonus finish ×1.25, adversaires du roster à leur rating
  courant). L'agent peut citer le delta ELO du matchup dans son rapport.
- **Radar chart** 6 axes (Plotly) superposant les deux profils normalisés.
- **Create-a-Fighter** : combattant custom créé aux sliders (sidebar), injecté dans les menus,
  utilisable dans l'analyse agent ET le simulateur 3D (ELO 1500, avatar initiales).
- **IA vs Vegas** : conversion des cotes américaines en probabilité implicite et détection de
  la « value » algorithmique (edge ≥ 5 pts).

## 6. Disclaimer

Données réalistes mais **figées à but pédagogique** (stats approximées type UFCStats,
cotes mockées) — pas une source officielle. **Photos © UFC / Wikimedia Commons, utilisées à
titre strictement académique**, téléchargées une fois et servies localement.
