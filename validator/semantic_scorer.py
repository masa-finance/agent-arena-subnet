from typing import List, Tuple
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from fiber.logging_utils import get_logger
from interfaces.types import Tweet
from validator.get_agent_posts import GetAgentPosts

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
        self.posts_getter = GetAgentPosts(netuid) if netuid is not None else None

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
        
        # Calculate uniqueness scores (avoiding division by zero)
        similar_posts = (similarity_matrix > self.similarity_threshold).sum(axis=1)
        # Ensure we don't divide by zero by adding 1 to denominator
        uniqueness_scores = np.where(
            similar_posts == 0,
            1.0,  # If no similar posts, maximum uniqueness
            1 / (1 + similar_posts)  # Otherwise, calculate as before
        )
        
        # Ensure all scores are finite
        originality_scores = np.clip(originality_scores, 0, 1)
        uniqueness_scores = np.clip(uniqueness_scores, 0, 1)
        
        return originality_scores, uniqueness_scores

    # Public interface methods
    def calculate_scores(self, texts: List[str]) -> List[float]:
        """Calculate combined similarity scores for a list of texts."""
        if not texts:
            logger.debug("No texts provided for scoring")
            return []

        # Filter out empty texts
        valid_texts = [text for text in texts if text and text.strip()]
        if not valid_texts:
            logger.debug("No valid texts after filtering")
            return [0.0] * len(texts)

        logger.debug("Encoding %d texts for semantic analysis", len(valid_texts))
        embeddings = self.model.encode(valid_texts)
        
        originality_scores, uniqueness_scores = self._calculate_component_scores(embeddings)
        
        logger.debug("Originality scores range: min=%.3f, max=%.3f", 
                     np.min(originality_scores), np.max(originality_scores))
        logger.debug("Uniqueness scores range: min=%.3f, max=%.3f", 
                     np.min(uniqueness_scores), np.max(uniqueness_scores))

        final_scores = (
            self.weights['originality'] * originality_scores +
            self.weights['uniqueness'] * uniqueness_scores
        )

        # Ensure final scores are finite and in [0,1] range
        final_scores = np.clip(final_scores, 0, 1)

        logger.debug("Final semantic scores range: min=%.3f, max=%.3f", 
                     np.min(final_scores), np.max(final_scores))
                     
        # If we filtered out any empty texts, we need to reconstruct the full scores list
        if len(valid_texts) != len(texts):
            full_scores = []
            valid_idx = 0
            for text in texts:
                if text and text.strip():
                    full_scores.append(float(final_scores[valid_idx]))
                    valid_idx += 1
                else:
                    full_scores.append(0.0)
            return full_scores
            
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