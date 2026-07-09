# Mini-projet TD4 — Serveur PIM MCP standalone

Un **serveur MCP** (Model Context Protocol) qui expose les opérations de votre catalogue PIM sous forme d'**outils découvrables**. Enregistrez-le dans **Claude Desktop** et interrogez votre catalogue en langage naturel.

## Fichiers

- `pim_server.py` — le serveur MCP standalone (stdio transport)
- `requirements.txt` — dépendances Python

## 5 outils exposés

1. **`search_products(query, k=3)`** — recherche sémantique (votre RAG de TD3)
2. **`get_product(sku)`** — récupère un produit par SKU
3. **`get_category_tree()`** — retourne l'arborescence des catégories
4. **`get_category_attributes(category)`** — retourne les attributs applicables d'une catégorie
5. **`create_product(...)`** — crée un produit (l'ajoute immédiatement à l'index, avec freshness)

## Installation

### 1. Installer les dépendances

```bash
cd notebooks/TD4_mcp/mini_project
pip install -r requirements.txt
```

### 2. Construire l'index ChromaDB (une seule fois)

```bash
python pim_server.py
```

Puis arrêtez-le (`Ctrl+C`) après le démarrage. Cela crée un répertoire `chroma_db/` avec l'index persistant.

La prochaine fois que vous lancez le serveur, il charge cet index existant au lieu de le reconstruire.

## Enregistrer dans Claude Desktop

### 1. Installer Claude Desktop

Si ce n'est pas déjà fait, téléchargez **Claude Desktop** sur [claude.ai/download](https://claude.ai/download) (c'est une app différente de Claude Code). Installez et ouvrez-la.

### 2. Trouver votre fichier de configuration MCP

Le fichier de config MCP de Claude Desktop se trouve à :

- **macOS :** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows :** `%APPDATA%\Claude\claude_desktop_config.json`

Si le fichier n'existe pas, créez-le. S'il existe, ouvrez-le dans votre éditeur de texte.

### 3. Enregistrer votre serveur

Dans le fichier `claude_desktop_config.json`, ajoutez votre serveur PIM sous `mcpServers` (créez la clé si elle n'existe pas) :

```json
{
  "mcpServers": {
    "pim": {
      "command": "/chemin/absolu/vers/votre/venv/bin/python",
      "args": ["/chemin/absolu/vers/notebooks/TD4_mcp/mini_project/pim_server.py"]
    }
  }
}
```

**⚠️ Les deux chemins DOIVENT être absolus** (pas `~/` ou chemins relatifs). Exemples :

- **macOS :**
  ```json
  {
    "mcpServers": {
      "pim": {
        "command": "/Users/guycharlykamgnesoupgoui/Documents/master IASD 2025-2026/IA Agentique/Generative-AI-M2-Apprentissage-2026-students-main/genai_env/bin/python",
        "args": ["/Users/guycharlykamgnesoupgoui/Documents/master IASD 2025-2026/IA Agentique/Generative-AI-M2-Apprentissage-2026-students-main/notebooks/TD4_mcp/mini_project/pim_server.py"]
      }
    }
  }
  ```

- **Windows :**
  ```json
  {
    "mcpServers": {
      "pim": {
        "command": "C:\\Users\\YourName\\venv\\Scripts\\python.exe",
        "args": ["C:\\path\\to\\notebooks\\TD4_mcp\\mini_project\\pim_server.py"]
      }
    }
  }
  ```

### 4. Redémarrer Claude Desktop complètement

**Important :** quittez Claude Desktop complètement, pas juste la fenêtre.

- **macOS :** ⌘Q (Cmd+Q)
- **Windows :** quittez depuis la barre d'état système

Puis relancez Claude Desktop. Les serveurs MCP ne sont lus qu'au démarrage.

### 5. Vérifier que les outils sont apparus

1. Ouvrez un **nouveau chat** dans Claude Desktop.
2. Cherchez le **menu des outils** — un bouton 🛠️ ou un icône "slider" près de la boîte de message.
3. Vous devriez voir un serveur **`pim`** avec les 5 outils listés :
   - `search_products`
   - `get_product`
   - `get_category_tree`
   - `get_category_attributes`
   - `create_product`

Si les outils n'apparaissent pas :
- Vérifiez que les **deux chemins sont absolus** et corrects.
- Allez dans **Settings → Developer** pour voir si Claude Desktop a signalé une erreur de démarrage du serveur.
- Assurez-vous que **toutes les dépendances** sont installées dans votre venv (`pip install -r requirements.txt`).

## Utiliser votre serveur

Une fois enregistré, vous pouvez poser des questions naturelles et Claude Desktop appellera automatiquement vos outils :

- *"Quels casques anti-bruit avez-vous sous 300€ ?"* → appelle `search_products`
- *"Quels attributs s'appliquent à la catégorie Phones ?"* → appelle `get_category_attributes`
- *"Ajoute ce produit : [specs], puis cherche-le."* → appelle `create_product`, puis `search_products`

**L'aha de freshness :** après un `create_product`, demandez à Claude de chercher votre nouveau produit — il le trouvera **instantanément**, car l'index ChromaDB a été mis à jour. Zéro retraining, zéro attente. C'est le même aha qu'en TD3 §2, maintenant exposé comme un outil.

## Notes

- Le serveur **n'a pas besoin de clé API Anthropic** — Claude Desktop gère le modèle.
- L'index ChromaDB est **persistant** (`chroma_db/`), donc les produits ajoutés survivent aux redémarrages.
- Ce serveur **stdio** est exactement ce que votre agent TD5 appellera, donc celui-ci est un test complet avant la vraie intégration.

## Dépannage

**"Server stderr: ModuleNotFoundError"**
→ `pip install -r requirements.txt` dans votre venv activé.

**"No such file: products.csv"**
→ Le serveur cherche `../../data/products.csv` depuis le dossier `mini_project/`. Vérifiez que votre structure est :
```
notebooks/
├── data/products.csv
├── data/taxonomy.json
└── TD4_mcp/mini_project/pim_server.py
```

**"Server won't start / Tools don't appear"**
→ Accédez à **Settings → Developer** dans Claude Desktop — il affiche l'erreur de démarrage du serveur.

**Les chemins me semblent trop longs**
→ C'est normal 😅 — ils doivent être absolus. La alternative est de refactoriser votre layout de dossiers pour les raccourcir, mais le chemin absolu fonctionne.
