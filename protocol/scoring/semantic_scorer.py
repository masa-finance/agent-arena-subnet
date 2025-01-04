from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

class SemanticScorer:
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        self.model = SentenceTransformer(model_name)
        self.similarity_threshold = 0.8
        self.weights = {
            'originality': 0.6,
            'uniqueness': 0.4
        }

    def _calculate_originality_scores(self, embeddings: np.ndarray) -> np.ndarray:
        similarity_matrix = cosine_similarity(embeddings)
        np.fill_diagonal(similarity_matrix, 0)
        originality_scores = 1 - similarity_matrix.mean(axis=1)
        return originality_scores

    def _calculate_uniqueness_scores(self, embeddings: np.ndarray) -> np.ndarray:
        similarity_matrix = cosine_similarity(embeddings)
        similar_posts = (similarity_matrix > self.similarity_threshold).sum(axis=1) - 1
        uniqueness_scores = 1 / (1 + similar_posts)
        return uniqueness_scores

    def calculate_scores(self, texts: List[str]) -> List[float]:
        if not texts:
            return []

        embeddings = self.model.encode(texts)
        originality_scores = self._calculate_originality_scores(embeddings)
        uniqueness_scores = self._calculate_uniqueness_scores(embeddings)

        final_scores = (
            self.weights['originality'] * originality_scores +
            self.weights['uniqueness'] * uniqueness_scores
        )

        return [float(score) for score in final_scores] 