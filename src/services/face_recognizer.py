"""
Compares a live face embedding against every enrolled student's stored
embeddings and returns ranked candidates. Brute-force cosine similarity is
completely fine for a 10-15 student roster (master plan section 11).
"""

import pickle
from dataclasses import dataclass
from typing import Dict, List

import numpy as np

from src import config


@dataclass
class Candidate:
    student_id: str
    student_name: str
    similarity: float


class FaceRecognizer:
    def __init__(self, embeddings_path=config.EMBEDDINGS_PATH):
        with open(embeddings_path, "rb") as f:
            db = pickle.load(f)
        # db: { student_id: {"name": str, "embeddings": np.ndarray [N, 512]} }
        self._db: Dict[str, dict] = db

    def match(self, embedding: np.ndarray, top_k: int = 2) -> List[Candidate]:
        scores = []
        for student_id, entry in self._db.items():
            enrolled = entry["embeddings"]  # [N, 512], L2-normalized
            sims = enrolled @ embedding  # cosine similarity since both are normalized
            best_sim = float(np.max(sims))
            scores.append(Candidate(student_id=student_id, student_name=entry["name"], similarity=best_sim))

        scores.sort(key=lambda c: c.similarity, reverse=True)
        return scores[:top_k]

    def roster(self) -> List[str]:
        return [entry["name"] for entry in self._db.values()]

    def roster_ids(self) -> List[str]:
        return list(self._db.keys())
