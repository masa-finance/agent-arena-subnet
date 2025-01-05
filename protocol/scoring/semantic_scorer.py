from typing import List, Tuple
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

DEFAULT_MODEL = 'all-MiniLM-L6-v2'
SIMILARITY_THRESHOLD = 0.8
WEIGHTS = {
    'originality': 0.6,
    'uniqueness': 0.4
}

class SemanticScorer:
    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.model = SentenceTransformer(model_name)
        self.similarity_threshold = SIMILARITY_THRESHOLD
        self.weights = WEIGHTS

    def _get_similarity_matrix(self, embeddings: np.ndarray) -> np.ndarray:
        similarity_matrix = cosine_similarity(embeddings)
        np.fill_diagonal(similarity_matrix, 0)
        return similarity_matrix

    def get_originality_scores(self, embeddings: np.ndarray) -> np.ndarray:
        similarity_matrix = self._get_similarity_matrix(embeddings)
        return 1 - similarity_matrix.mean(axis=1)

    def get_uniqueness_scores(self, embeddings: np.ndarray) -> np.ndarray:
        similarity_matrix = self._get_similarity_matrix(embeddings)
        similar_posts = (similarity_matrix > self.similarity_threshold).sum(axis=1) - 1
        return 1 / (1 + similar_posts)

    def calculate_scores(self, texts: List[str]) -> List[float]:
        if not texts:
            return []

        embeddings = self.model.encode(texts)
        originality_scores = self.get_originality_scores(embeddings)
        uniqueness_scores = self.get_uniqueness_scores(embeddings)

        final_scores = (
            self.weights['originality'] * originality_scores +
            self.weights['uniqueness'] * uniqueness_scores
        )

        return [float(score) for score in final_scores]