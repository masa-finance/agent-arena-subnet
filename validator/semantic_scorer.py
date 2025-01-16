from typing import List, Tuple
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from fiber.logging_utils import get_logger
from interfaces.types import Tweet
from .posts_getter import PostsGetter

# Constants
DEFAULT_MODEL = 'all-MiniLM-L6-v2'
SIMILARITY_THRESHOLD = 0.8
WEIGHTS = {
    'originality': 0.6,
    'uniqueness': 0.4
}

logger = get_logger(__name__)

class SemanticScorer:
    """
    Analyzes semantic similarity between texts and calculates originality scores.
    """
    def __init__(self, model_name: str = DEFAULT_MODEL, netuid: int = None, max_posts: int = 100):
        """Initialize the scorer with model and configuration."""
        self.model = SentenceTransformer(model_name)
        self.similarity_threshold = SIMILARITY_THRESHOLD
        self.weights = WEIGHTS
        self.max_posts = max_posts
        self.posts_getter = PostsGetter(netuid) if netuid is not None else None

    # Core scoring methods
    def _get_similarity_matrix(self, embeddings: np.ndarray) -> np.ndarray:
        """Calculate pairwise similarity matrix for given embeddings."""
        similarity_matrix = cosine_similarity(embeddings)
        np.fill_diagonal(similarity_matrix, 0)
        return similarity_matrix

    def _calculate_component_scores(self, embeddings: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Calculate both originality and uniqueness scores from embeddings."""
        similarity_matrix = self._get_similarity_matrix(embeddings)
        
        # Calculate originality scores
        originality_scores = 1 - similarity_matrix.mean(axis=1)
        
        # Calculate uniqueness scores
        similar_posts = (similarity_matrix > self.similarity_threshold).sum(axis=1) - 1
        uniqueness_scores = 1 / (1 + similar_posts)
        
        return originality_scores, uniqueness_scores

    # Public interface methods
    def calculate_scores(self, texts: List[str]) -> List[float]:
        """Calculate combined similarity scores for a list of texts."""
        if not texts:
            logger.debugf("No texts provided for scoring")
            return []

        logger.debugf("Encoding %d texts for semantic analysis", len(texts))
        embeddings = self.model.encode(texts)
        
        originality_scores, uniqueness_scores = self._calculate_component_scores(embeddings)
        
        logger.debugf("Originality scores range: min=%.3f, max=%.3f", 
                     np.min(originality_scores), np.max(originality_scores))
        logger.debugf("Uniqueness scores range: min=%.3f, max=%.3f", 
                     np.min(uniqueness_scores), np.max(uniqueness_scores))

        final_scores = (
            self.weights['originality'] * originality_scores +
            self.weights['uniqueness'] * uniqueness_scores
        )

        logger.debugf("Final semantic scores range: min=%.3f, max=%.3f", 
                     np.min(final_scores), np.max(final_scores))
        return [float(score) for score in final_scores]

    async def get_posts_with_scores(self, posts: List[Tweet]) -> List[float]:
        """
        Analyze posts for semantic similarity.
        Returns: List of similarity scores where higher scores indicate more original content.
        """
        try:
            post_texts = [post.get('Text', '') for post in posts]
            scores = self.calculate_scores(post_texts)
            
            logger.infof("Analyzed %d posts for semantic similarity", len(scores))
            return scores

        except Exception as e:
            logger.errorf("Error analyzing posts for similarity: %s", str(e))
            return [0.0] * len(posts)  # Return neutral scores on error