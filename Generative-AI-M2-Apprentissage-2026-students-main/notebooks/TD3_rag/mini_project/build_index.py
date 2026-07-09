"""
build_index.py — run ONCE to build the persistent ChromaDB index for the mini-project.

Loads the shared catalog (../../data/products.csv), embeds every product with the
same MiniLM model used throughout TD1/TD3, and writes the vectors to a PERSISTENT
Chroma collection on disk (./chroma_db). The Flask app (app.py) then just opens
that index at startup — no re-embedding on every request or every restart.

Usage:
    python build_index.py
"""

import json
import os

import pandas as pd
import chromadb
from sentence_transformers import SentenceTransformer

# --- paths -------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(HERE, "..", "..", "data", "products.csv")
INDEX_PATH = os.path.join(HERE, "chroma_db")
COLLECTION_NAME = "catalog"


def build():
    print(f"Loading catalog from {CSV_PATH} ...")
    df = pd.read_csv(CSV_PATH)

    # Same indexed text as TD3 §1/§2: name + long_description, so the corpus lives
    # in the exact same vector space the notebook built.
    df["doc"] = df["name"] + " — " + df["long_description"]

    print(f"Loaded {len(df)} products across {df['category'].nunique()} categories.")

    # Persistent client -- this is the only real change vs. the notebook's
    # in-memory chromadb.Client(): the index now survives app restarts.
    client = chromadb.PersistentClient(path=INDEX_PATH)

    # Drop any stale collection so re-running this script is clean/idempotent.
    if COLLECTION_NAME in [c.name for c in client.list_collections()]:
        client.delete_collection(COLLECTION_NAME)
    collection = client.create_collection(COLLECTION_NAME)

    # Same metadata schema as TD3 §2 -- the whole product, so retrieve() can hand
    # back everything a caller needs (sku is the Chroma id).
    metadatas = [
        {
            "name": r["name"],
            "brand": r["brand"],
            "category": r["category"],
            "price": float(r["price"]),
            "short_description": r["short_description"],
            "long_description": r["long_description"],
            "attributes": r["attributes"],  # JSON string -> Chroma metadata must be scalar
        }
        for _, r in df.iterrows()
    ]

    print("Embedding corpus with all-MiniLM-L6-v2 (this can take a minute)...")
    embed_model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = embed_model.encode(df["doc"].tolist(), show_progress_bar=True).tolist()

    collection.add(
        ids=df["sku"].tolist(),
        embeddings=embeddings,
        documents=df["doc"].tolist(),
        metadatas=metadatas,
    )

    assert collection.count() == len(df), "every product should be indexed"
    print(f"Indexed {collection.count()} products into a persistent Chroma "
          f"collection at {INDEX_PATH}.")


if __name__ == "__main__":
    build()
