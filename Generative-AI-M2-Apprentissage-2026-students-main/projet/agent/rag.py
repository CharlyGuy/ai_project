"""
agent/rag.py
------------
Couche RAG (Lab 3) : on vectorise le corpus texte des comptes-rendus de combats
(`data/fight_reports.json`) et on retrouve les passages les plus pertinents
pour une requête donnée (ex: "faiblesses au sol de Justin Gaethje").

Choix technique : on utilise un TF-IDF (scikit-learn) plutôt qu'un modèle
d'embeddings lourd à télécharger, pour que le POC tourne offline / sans clé
API supplémentaire. L'interface `search(query, k)` est volontairement la même
que celle d'un vrai store vectoriel : il suffit de remplacer `vectorize()` par
un vrai modèle d'embeddings (OpenAI, Voyage, sentence-transformers...) pour
passer en prod sans toucher au reste de l'agent.
"""
import json
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DATA_PATH = Path(__file__).parent.parent / "data" / "fight_reports.json"


class FightReportRAG:
    def __init__(self, data_path: Path = DATA_PATH):
        with open(data_path, "r", encoding="utf-8") as f:
            self.reports = json.load(f)

        # Un "document" = résumé + métadonnées textuelles utiles à la recherche
        self.corpus = [
            f"{r['fighter']} vs {r['opponent']}: {r['result']} par {r['method']} "
            f"(round {r['round']}). {r['summary']}"
            for r in self.reports
        ]

        self.vectorizer = TfidfVectorizer(stop_words=None, ngram_range=(1, 2))
        self.matrix = self.vectorizer.fit_transform(self.corpus)

    def search(self, query: str, k: int = 3, fighter_name: str | None = None):
        """Retourne les k passages les plus proches de `query`.
        Si `fighter_name` est fourni, on ne cherche que dans ses combats.
        """
        query_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self.matrix)[0]

        indices = np.argsort(scores)[::-1]

        results = []
        for idx in indices:
            report = self.reports[idx]
            if fighter_name and fighter_name.lower() not in report["fighter"].lower():
                continue
            if scores[idx] <= 0:
                continue
            results.append(
                {
                    "score": round(float(scores[idx]), 3),
                    "fighter": report["fighter"],
                    "opponent": report["opponent"],
                    "result": report["result"],
                    "method": report["method"],
                    "round": report["round"],
                    "summary": report["summary"],
                }
            )
            if len(results) >= k:
                break
        return results


# Instance unique réutilisée par les tools (évite de refaire le TF-IDF à chaque appel)
_rag_singleton: FightReportRAG | None = None


def get_rag() -> FightReportRAG:
    global _rag_singleton
    if _rag_singleton is None:
        _rag_singleton = FightReportRAG()
    return _rag_singleton
