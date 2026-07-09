# Mini-project — Fnac-style catalog chatbot

A tiny Flask web app: type a question about the catalog, get a grounded answer.
This is the TD3 `retrieve -> answer_question` loop (§2 and §7 of `TD3_rag.ipynb`),
behind a one-page web UI, backed by a **persistent** ChromaDB index instead of
the notebook's in-memory one.

## Files

- `build_index.py` — one-off script: loads `../../data/products.csv`, embeds
  every product with `all-MiniLM-L6-v2`, and writes a persistent Chroma
  collection to `./chroma_db/`.
- `app.py` — Flask app. Loads the persistent index at startup, exposes `/`
  (the chat page) and `POST /ask` (JSON: `{"question": "..."}` ->
  `{"answer": "...", "sources": [...]}`), and runs the same `retrieve` +
  `answer_question` logic as TD3 §2/§7.
- `templates/index.html` — the single-page chat UI.
- `requirements.txt` — dependencies.
- `.env.example` — copy to `.env` and fill in your key.

## Setup

1. From this folder, create a virtualenv (optional but recommended) and
   install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and set your key:

   ```bash
   cp .env.example .env
   # then edit .env: ANTHROPIC_API_KEY=sk-ant-...
   ```

   The app never hard-codes the API key — it's loaded from `.env` via
   `python-dotenv`, exactly like the notebook.

3. Build the index **once** (re-run any time `products.csv` changes):

   ```bash
   python build_index.py
   ```

   This writes a persistent Chroma index to `./chroma_db/`. It's built once
   and reloaded instantly on every app start — no re-embedding the catalog
   on every request or every restart.

4. Run the app:

   ```bash
   python app.py
   ```

   Then open <http://localhost:5000> and ask something like:
   *"do you have noise-cancelling headphones under €200?"*

## Notes

- Uses `claude-haiku-4-5` only, matching the notebook.
- `retrieve` embeds the query with the same MiniLM model used to build the
  index, so query and corpus share one vector space.
- `answer_question` grounds the answer strictly in the top-k retrieved
  products and is told to say so if nothing fits — no hallucinated catalog
  items.
- This is a minimal POC, not a production app: no auth, no rate limiting,
  no error pages beyond basic JSON errors.
