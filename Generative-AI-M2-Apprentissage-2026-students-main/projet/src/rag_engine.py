"""
src/rag_engine.py
-----------------
Moteur RAG vectoriel : remplace l'ancien TF-IDF par une vraie base vectorielle
persistante (ChromaDB) avec des embeddings locaux `all-MiniLM-L6-v2`
(sentence-transformers) — le même modèle que les labs du cours, déjà en cache.

Pipeline :
1. charge les rapports de scouting markdown de `data/fight_reports/*.md` ;
2. découpe chaque fichier en chunks (un paragraphe = un chunk, avec le nom du
   combattant en métadonnée) ;
3. embedde EXPLICITEMENT avec MiniLM (pas l'embedder par défaut de Chroma) et
   indexe dans une collection persistante sous `chroma_db/` ;
4. expose `search(query, k, fighter_name=None)` : similarité cosinus + filtre
   métadonnée optionnel.

L'index n'est (re)construit que si la collection est vide ou si le corpus a
changé de taille — sinon on réutilise l'index persistant (démarrage rapide).
"""
from __future__ import annotations

from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

REPORTS_DIR = Path(__file__).parent.parent / "data" / "fight_reports"
CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"
COLLECTION = "fight_reports"
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"


def _load_chunks() -> list[dict]:
    """Un chunk par paragraphe de chaque rapport, avec le combattant en métadonnée."""
    chunks = []
    for md_file in sorted(REPORTS_DIR.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        lines = text.splitlines()
        # Le titre H1 du fichier donne le nom du combattant : "# Jon Jones — Notes de scouting"
        title = next((l for l in lines if l.startswith("# ")), "# Inconnu")
        fighter = title.lstrip("# ").split("—")[0].strip()
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip() and not p.strip().startswith("#")]
        for i, para in enumerate(paragraphs):
            chunks.append({
                "id": f"{md_file.stem}-{i}",
                "text": para,
                "fighter": fighter,
                "source": md_file.name,
            })
    return chunks


class FightReportRAG:
    def __init__(self):
        self.embedder = SentenceTransformer(EMBED_MODEL_NAME)
        self.client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        self.collection = self.client.get_or_create_collection(COLLECTION)
        self._sync_index()

    def _sync_index(self) -> None:
        chunks = _load_chunks()
        if self.collection.count() == len(chunks) and chunks:
            return  # index à jour, on réutilise le persistant
        if self.collection.count():
            self.client.delete_collection(COLLECTION)
            self.collection = self.client.get_or_create_collection(COLLECTION)
        if not chunks:
            return
        embeddings = self.embedder.encode([c["text"] for c in chunks], show_progress_bar=False)
        self.collection.add(
            ids=[c["id"] for c in chunks],
            embeddings=embeddings.tolist(),
            documents=[c["text"] for c in chunks],
            metadatas=[{"fighter": c["fighter"], "source": c["source"]} for c in chunks],
        )

    def search(self, query: str, k: int = 3, fighter_name: str | None = None) -> list[dict]:
        """Recherche vectorielle ; filtre optionnel sur le combattant (match souple)."""
        q_vec = self.embedder.encode(query).tolist()
        where = None
        if fighter_name:
            # match souple : on cherche la valeur exacte de métadonnée la plus proche
            known = {m["fighter"] for m in self.collection.get(include=["metadatas"])["metadatas"]}
            target = next((f for f in known if fighter_name.lower() in f.lower()
                           or f.lower() in fighter_name.lower()), None)
            if target:
                where = {"fighter": target}
        res = self.collection.query(
            query_embeddings=[q_vec],
            n_results=min(k, max(self.collection.count(), 1)),
            where=where,
        )
        hits = []
        for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
            hits.append({
                "score": round(1 - dist / 2, 3),  # distance L2 normalisée -> pseudo-similarité
                "fighter": meta["fighter"],
                "source": meta["source"],
                "excerpt": doc,
            })
        return hits


_rag_singleton: FightReportRAG | None = None


def get_rag() -> FightReportRAG:
    global _rag_singleton
    if _rag_singleton is None:
        _rag_singleton = FightReportRAG()
    return _rag_singleton


if __name__ == "__main__":
    rag = get_rag()
    print(f"Index : {rag.collection.count()} chunks")
    for hit in rag.search("faiblesses face aux lutteurs qui changent de niveau", k=3):
        print(f"  [{hit['score']}] {hit['fighter']}: {hit['excerpt'][:90]}...")
