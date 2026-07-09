# Mini-projet TD5 — PIM Copilot

Un **agent LLM** en boucle `reason → act → observe` qui enrichit le catalogue Fnac en lisant les specs brutes d'un fournisseur.

**Le workflow :**
1. Copiez les infos d'un produit fournisseur (nom, brand, specs brutes)
2. Collez-les dans le chatbot
3. L'agent :
   - **Raisonne** (comprend le produit)
   - **Agit** (appelle les outils MCP : cherche la catégorie, récupère le schéma, cherche des exemples, crée le produit)
   - **Observe** (lit les résultats des outils, continue ou arrête)
4. Le produit enrichi apparaît dans le catalogue (votre ChromaDB TD4)

## Fichiers

- `agent.py` — la boucle `run_agent` qui connecte au serveur TD4 via **stdio**
- `app.py` — FastAPI backend avec endpoint `POST /chat`
- `index.html` — UI chat simple
- `requirements.txt` — dépendances

## Prérequis

**✅ Vous devez d'abord avoir complété le mini-projet TD4** — le serveur MCP persistant doit exister.

Vérifiez :
```bash
ls ../TD4_mcp/mini_project/
# Vous devez voir : pim_server.py, chroma_db/, requirements.txt, README.md
```

Si TD4 manque : allez faire le [mini-projet TD4](../TD4_mcp/mini_project/README.md) d'abord.

## Installation

### 1. Placez ce dossier

```
notebooks/
├── data/products.csv
├── data/taxonomy.json
├── TD4_mcp/mini_project/pim_server.py  ← doit exister
└── TD5_agent/mini_project/             ← ce dossier
    ├── agent.py
    ├── app.py
    ├── index.html
    └── requirements.txt
```

### 2. Installez les dépendances

```bash
cd notebooks/TD5_agent/mini_project

# Activez votre venv
source ../../genai_env/bin/activate

# Installez
pip install -r requirements.txt
```

## Lancement

### Étape 1 : Assurez-vous que le serveur TD4 est construit

```bash
cd ../TD4_mcp/mini_project

# Si vous ne l'avez pas encore fait, construisez l'index une fois
python pim_server.py
# Attendez quelques secondes, puis Ctrl+C pour arrêter

# L'index persistant chroma_db/ est créé (les lancements suivants sont rapides)
```

### Étape 2 : Lancez le copilot

```bash
cd ../../TD5_agent/mini_project

# Assurez-vous que votre venv est activé
python app.py
```

Vous devez voir :
```
INFO:     Uvicorn running on http://127.0.0.1:8000
Press CTRL+C to quit
```

### Étape 3 : Ouvrez le chatbot

Allez à **`http://localhost:8000`** dans votre navigateur.

## Utilisation

### Exemple 1 : Produit simple

```
Apple AirPods Pro 2, brand Apple, category Headphones, price €280,
30-hour battery, active noise cancelling, transparency mode, spatial audio,
MagSafe charging case, lightning connector
```

L'agent va :
1. Reconnaître "Headphones" comme catégorie
2. Chercher des casques similaires comme référence de style
3. Remplir les attributs : connectivity, noise_cancellation, etc.
4. Créer le produit enrichi

### Exemple 2 : Produit avec infos supplémentaires

```
Beats Studio Pro headphones, Beats brand, premium audio, €400,
ANC enabled, 40-hour battery, Spatial Audio with dynamic head tracking,
lossless audio with USB-C, multipoint Bluetooth connection.
Wholesale price: €250, MOQ: 10 units, Lead time: 2 weeks
```

Les infos qu'aucun attribut de catégorie ne couvre (prix de gros, MOQ, délai)
iront dans `extra` — le catch-all du fournisseur.

## Comprendre le flux agent

L'agent tourne en boucle :

```
1. REASON : "Quel est ce produit? Quelle catégorie?"
   → appelle search_products() pour des exemples
   → appelle get_category_attributes() pour le schéma

2. ACT : "Voici les infos. Je vais créer le produit."
   → appelle create_product(...)

3. OBSERVE : "Le produit a été créé avec SKU NEW-1234."
   → boucle termine (pas plus de tools à appeler)

4. FINAL ANSWER : "Produit créé : Apple AirPods Pro 2, SKU NEW-1234, ..."
```

Chaque cycle est **une vraie MCP call** au serveur TD4. L'agent **voit le résultat réel** et décide de continuer ou s'arrêter.

## Architecture

```
┌─ Browser (http://localhost:8000)
│
└─ FastAPI app.py
    │
    └─ agent.py (run_agent loop)
        │
        └─ MCP stdio client
            │
            └─ TD4 pim_server.py (subprocess)
                │
                └─ Persistent ChromaDB index
```

- **Browser ↔ FastAPI** : HTTP JSON
- **FastAPI ↔ agent** : Python asyncio
- **agent ↔ TD4 server** : **stdio MCP** (subprocess + stdout/stdin)
- **TD4 server ↔ ChromaDB** : in-process

## Dépannage

### ❌ "TD4 server not found"
Vérifiez que vous avez bien complété le TD4 mini-projet. Le chemin doit être :
```
notebooks/TD4_mcp/mini_project/pim_server.py
```

### ❌ "Agent error: ... No such file or directory"
Le serveur TD4 n'a pas pu démarrer. Vérifiez que votre venv TD4 a les dépendances :
```bash
cd ../TD4_mcp/mini_project
pip install -r requirements.txt
```

### ❌ "Port 8000 already in use"
Le port est occupé. Changez le port dans `app.py` (dernière ligne) :
```python
uvicorn.run(app, host="127.0.0.1", port=8001, reload=True)
```

### ❌ Le produit créé n'apparaît pas dans la recherche
Vérifiez que le serveur TD4 utilise bien l'index **persistant** (c'est le cas par défaut).
L'embedding doit être le **même MiniLM** partout.

## Architecture avancée

Si vous voulez étendre :

1. **Multi-turn conversation** : remplacez le POST simple par une vraie session WebSocket
   qui garde l'historique des messages et reuse la même session MCP.

2. **Human-in-the-loop** : pausez avant `create_product()` et attendez l'approbation
   (un "Confirm?" classique).

3. **Batch enrichment** : lancez l'agent sur une liste de produits, pas un seul.

4. **Streaming** : affichez la trace des tool-calls en direct (avec `response.streaming`
   sur une WebSocket).

## Notes

- L'agent utilise **Haiku uniquement** (coût bas, pas d'API key côté client).
- L'index ChromaDB est **persistant et partagé** avec TD3/TD4 → les produits
  restent d'un lancement à l'autre.
- Le serveur TD4 est relancé **à chaque requête** (simple, pas optimisé).
  Pour production, garder une session MCP permanente serait mieux.

## Fichiers TD5 du notebook

Pour une référence complète, voir `TD5_agent.ipynb` :
- §2–§4 : une seule boucle `reason → act → observe` step-by-step
- §5 : la boucle généralisée `run_agent`
- §6 : ce mini-projet
