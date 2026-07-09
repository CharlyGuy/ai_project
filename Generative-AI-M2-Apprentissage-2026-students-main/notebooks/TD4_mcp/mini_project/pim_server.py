#!/usr/bin/env python3
"""
pim_server.py — Standalone PIM MCP server over stdio transport.

Exposes 5 tools for catalog operations:
  - search_products(query, k=3)      : semantic search (your TD3 RAG)
  - get_product(sku)                 : fetch one product from ChromaDB
  - get_category_tree()              : return catalog category hierarchy
  - get_category_attributes(category): return attribute schema for a leaf category
  - create_product(...)              : add a new product to the persistent index

The chromaDB index is persistent (built once from products.csv), so products
added via create_product are immediately discoverable by search_products.

Usage:
    python pim_server.py

This server is spawned by Claude Desktop via the MCP config and communicates
over stdio. See README.md for registration instructions.
"""

import json
import os
import sys
import logging
from typing import Optional

import pandas as pd
from sentence_transformers import SentenceTransformer
import chromadb
from mcp.server.fastmcp import FastMCP

# Suppress verbose MCP logs
logging.getLogger("mcp").setLevel(logging.WARNING)

# --- setup ---------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_ROOT = os.path.join(HERE, "..", "..", "data")
CSV_PATH = os.path.join(DATA_ROOT, "products.csv")
TAXONOMY_PATH = os.path.join(DATA_ROOT, "taxonomy.json")
INDEX_PATH = os.path.join(HERE, "chroma_db")

# Load the shared catalog and taxonomy
if not os.path.exists(CSV_PATH):
    print(f"ERROR: products.csv not found at {CSV_PATH}", file=sys.stderr)
    print(f"Make sure you run this from notebooks/TD4_mcp/mini_project/", file=sys.stderr)
    sys.exit(1)

df = pd.read_csv(CSV_PATH)
df["doc"] = df["name"] + " — " + df["long_description"]

with open(TAXONOMY_PATH) as f:
    taxonomy = json.load(f)

# Initialize the embedding model and persistent ChromaDB index
embed_model = SentenceTransformer("all-MiniLM-L6-v2")
chroma_client = chromadb.PersistentClient(path=INDEX_PATH)

# If the index doesn't exist yet, build it from the catalog
try:
    collection = chroma_client.get_collection("catalog")
except Exception:
    # First run: build the index
    collection = chroma_client.create_collection("catalog")
    embeddings = embed_model.encode(df["doc"].tolist(), show_progress_bar=False)
    collection.add(
        ids=df["sku"].tolist(),
        embeddings=embeddings.tolist(),
        documents=df["doc"].tolist(),
        metadatas=[
            {
                "name": r["name"],
                "brand": r["brand"],
                "category": r["category"],
                "price": float(r["price"]),
                "short_description": r["short_description"],
                "long_description": r["long_description"],
                "attributes": r["attributes"],
            }
            for _, r in df.iterrows()
        ],
    )

# Create the MCP server
mcp_server = FastMCP("pim")


# --- helper: retrieve function (your TD3 RAG) ---
def retrieve(query_text: str, k: int = 3) -> list:
    """Semantic search over the catalog; return k most similar products."""
    q_vec = embed_model.encode(query_text).tolist()
    res = collection.query(query_embeddings=[q_vec], n_results=k)
    hits = []
    for sku, meta in zip(res["ids"][0], res["metadatas"][0]):
        hit = {"sku": sku, **meta}
        if isinstance(hit.get("attributes"), str):
            hit["attributes"] = json.loads(hit["attributes"])
        hits.append(hit)
    return hits


# --- tools ---
@mcp_server.tool()
def search_products(query: str, k: int = 3) -> list:
    """Semantic search over the product catalog; returns up to k products most similar to the query."""
    return retrieve(query, k=k)


@mcp_server.tool()
def get_product(sku: str) -> dict:
    """Fetch a single product by its SKU."""
    result = collection.get(ids=[sku], include=["metadatas", "documents"])
    if result["ids"]:
        meta = result["metadatas"][0]
        if isinstance(meta.get("attributes"), str):
            meta["attributes"] = json.loads(meta["attributes"])
        return {"sku": sku, **meta}
    return {"error": f"Product {sku} not found"}


@mcp_server.tool()
def get_category_tree() -> dict:
    """Return the catalog category tree as {top_category: [leaf_category, ...]}."""
    return {
        cat["name"]: [sub["name"] for sub in cat["subcategories"]]
        for cat in taxonomy["categories"]
    }


@mcp_server.tool()
def get_category_attributes(category: str) -> dict:
    """Return the applicable attribute schema for a leaf category."""
    for cat in taxonomy["categories"]:
        for sub in cat["subcategories"]:
            if sub["name"] == category:
                return {
                    attr["name"]: (
                        ", ".join(attr["values"])
                        if "values" in attr
                        else attr["type"]
                    )
                    for attr in sub.get("category_attributes", [])
                }
    return {}


@mcp_server.tool()
def create_product(
    name: str,
    brand: str,
    category: str,
    price: float,
    short_description: str,
    long_description: str,
    attributes: Optional[dict] = None,
) -> dict:
    """Create a new product and add it to the catalog. Returns the new SKU and is immediately searchable."""
    if attributes is None:
        attributes = {}

    # Generate a new SKU (simple scheme: brand-initials + count)
    new_sku = f"NEW-{len(list(collection.get(ids=[])))}"

    # Embed and add to ChromaDB
    doc = name + " — " + long_description
    embedding = embed_model.encode(doc).tolist()

    metadata = {
        "name": name,
        "brand": brand,
        "category": category,
        "price": float(price),
        "short_description": short_description,
        "long_description": long_description,
        "attributes": json.dumps(attributes),  # store as JSON string like the rest
    }

    collection.add(
        ids=[new_sku],
        embeddings=[embedding],
        documents=[doc],
        metadatas=[metadata],
    )

    return {
        "sku": new_sku,
        "name": name,
        "brand": brand,
        "category": category,
        "price": price,
        "short_description": short_description,
        "long_description": long_description,
        "attributes": attributes,
        "message": f"Product created and indexed. Try searching for it immediately.",
    }


# --- main ---
if __name__ == "__main__":
    mcp_server.run()
