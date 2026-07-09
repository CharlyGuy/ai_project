"""
app.py — Fnac-style catalog chatbot.

Loads the PERSISTENT Chroma index built by build_index.py, then exposes:
  - GET  /            a single page with a text box
  - POST /ask         JSON endpoint: {"question": "..."} -> {"answer": "..."}

This is the §7 `retrieve -> answer_question` loop from TD3_rag.ipynb, lifted
almost unchanged -- the only real difference is that `collection` here comes
from a PersistentClient instead of an in-memory one.
"""

import os

from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
import chromadb
from sentence_transformers import SentenceTransformer
import anthropic

# --- setup ---------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(HERE, "chroma_db")
COLLECTION_NAME = "catalog"
MODEL = "claude-haiku-4-5"

load_dotenv()  # reads ANTHROPIC_API_KEY from a .env file (never hard-code the key)
if not os.getenv("ANTHROPIC_API_KEY"):
    raise RuntimeError(
        "ANTHROPIC_API_KEY not found. Create a .env file in mini_project/ with\n"
        "ANTHROPIC_API_KEY=sk-ant-..."
    )

client = anthropic.Anthropic()
embed_model = SentenceTransformer("all-MiniLM-L6-v2")

chroma_client = chromadb.PersistentClient(path=INDEX_PATH)
try:
    collection = chroma_client.get_collection(COLLECTION_NAME)
except Exception as exc:
    raise RuntimeError(
        f"Could not open the '{COLLECTION_NAME}' collection at {INDEX_PATH}. "
        "Did you run `python build_index.py` first?"
    ) from exc

print(f"Loaded persistent index with {collection.count()} products.")

app = Flask(__name__)


# --- the RAG kernel, straight from TD3 §2 / §7 ----------------------------
def retrieve(query_text, k=4):
    """Return the k catalog products most similar to `query_text`, as a list of dicts."""
    query_embedding = embed_model.encode(query_text).tolist()
    results = collection.query(query_embeddings=[query_embedding], n_results=k)
    hits = [
        {"sku": sku, **meta}
        for sku, meta in zip(results["ids"][0], results["metadatas"][0])
    ]
    return hits


def answer_question(question, k=4):
    """Answer a question about the catalog, grounded in the k most relevant products."""
    hits = retrieve(question, k=k)
    context = "\n".join(
        f"- {h['name']} ({h['category']}, EUR {h['price']:.0f}): {h['short_description']}"
        for h in hits
    )
    prompt = (
        "Answer the question using ONLY the catalog products listed below. "
        "If nothing fits, say so.\n\n"
        f"Catalog products:\n{context}\n\nQuestion: {question}"
    )
    resp = client.messages.create(
        model=MODEL,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text, hits


# --- routes ----------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "Please type a question."}), 400

    answer, hits = answer_question(question)
    return jsonify({
        "answer": answer,
        "sources": [{"name": h["name"], "category": h["category"], "price": h["price"]}
                    for h in hits],
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
