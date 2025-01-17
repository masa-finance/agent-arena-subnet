from typing import List, Tuple
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import torch
import logging
from typing import Optional
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_MODEL = 'all-MiniLM-L6-v2'
SIMILARITY_THRESHOLD = 0.8
WEIGHTS = {
    'originality': 0.6,
    'uniqueness': 0.4
}

class SemanticScorer:
    """
    Analyzes semantic similarity between texts and calculates originality scores.
    """
    def __init__(self, model_name: str = DEFAULT_MODEL, device_type: Optional[str] = None):
        """Initialize the scorer with hardware-accelerated model."""
        # Use provided device type or auto-detect
        if device_type:
            self.device = torch.device(device_type)
        else:
            if torch.backends.mps.is_available():
                self.device = torch.device("mps")
                logger.info("Using Apple Silicon MPS acceleration")
            elif torch.cuda.is_available():
                self.device = torch.device("cuda")
                logger.info(f"Using CUDA GPU: {torch.cuda.get_device_name(0)}")
            else:
                self.device = torch.device("cpu")
                logger.info("Using CPU - no hardware acceleration available")

        # Initialize model on appropriate device
        self.model = SentenceTransformer(model_name)
        self.model.to(self.device)
        
        self.similarity_threshold = SIMILARITY_THRESHOLD
        self.weights = WEIGHTS

    def _get_similarity_matrix(self, embeddings: torch.Tensor) -> torch.Tensor:
        """Calculate pairwise similarity matrix using hardware acceleration."""
        # Ensure embeddings are on the correct device and using float32
        embeddings = embeddings.to(self.device, dtype=torch.float32)
        
        # Compute similarity matrix using torch operations
        norm = torch.nn.functional.normalize(embeddings, p=2, dim=1)
        similarity_matrix = torch.mm(norm, norm.t())
        
        # Zero out diagonal
        similarity_matrix.fill_diagonal_(0)
        
        return similarity_matrix

    def _calculate_component_scores(self, embeddings: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Calculate scores using hardware-accelerated operations."""
        similarity_matrix = self._get_similarity_matrix(embeddings)
        
        # Calculate originality scores
        originality_scores = 1 - similarity_matrix.mean(dim=1)
        
        # Calculate uniqueness scores
        similar_posts = (similarity_matrix > self.similarity_threshold).sum(dim=1).float()
        uniqueness_scores = 1.0 / (1.0 + similar_posts)
        
        # Ensure all scores are finite and clipped
        originality_scores = torch.clamp(originality_scores, 0, 1)
        uniqueness_scores = torch.clamp(uniqueness_scores, 0, 1)
        
        return originality_scores, uniqueness_scores

    def calculate_scores(self, texts: List[str], batch_size: int = 32) -> List[float]:
        if not texts:
            return []

        valid_texts = [text for text in texts if text and text.strip()]
        if not valid_texts:
            return [0.0] * len(texts)

        # Pre-allocate arrays for better memory efficiency
        final_scores = np.zeros(len(texts), dtype=np.float32)
        
        # Process in smaller batches with memory cleanup
        for i in range(0, len(valid_texts), batch_size):
            batch = valid_texts[i:i + batch_size]
            
            try:
                # Encode with hardware acceleration and memory optimization
                with torch.no_grad():
                    embeddings = self.model.encode(
                        batch,
                        show_progress_bar=False,
                        batch_size=min(batch_size, 128),  # Limit sub-batch size
                        convert_to_tensor=True,
                        device=self.device,
                        normalize_embeddings=True
                    )
                    
                    # Move to CPU immediately after computation to free GPU memory
                    orig_scores, uniq_scores = self._calculate_component_scores(embeddings)
                    batch_scores = (
                        self.weights['originality'] * orig_scores +
                        self.weights['uniqueness'] * uniq_scores
                    ).cpu().numpy()
                    
                    final_scores[i:i + len(batch)] = np.clip(batch_scores, 0, 1)
                    
                    # Explicit cleanup
                    del embeddings, orig_scores, uniq_scores, batch_scores
                    torch.cuda.empty_cache() if torch.cuda.is_available() else None
                    
            except RuntimeError as e:
                if "out of memory" in str(e) or "buffer size" in str(e):
                    # If we hit memory issues, try with an even smaller batch
                    logger.warning(f"Memory error with batch size {batch_size}, reducing batch size")
                    half_batch = len(batch) // 2
                    if half_batch < 1:
                        raise e
                    
                    # Process the smaller batches
                    scores1 = self.calculate_scores(batch[:half_batch], batch_size=half_batch)
                    scores2 = self.calculate_scores(batch[half_batch:], batch_size=half_batch)
                    final_scores[i:i + len(batch)] = scores1 + scores2
                else:
                    raise e

        # Handle filtered texts efficiently
        if len(valid_texts) != len(texts):
            result = np.zeros(len(texts), dtype=np.float32)
            valid_idx = 0
            for i, text in enumerate(texts):
                if text and text.strip():
                    result[i] = final_scores[valid_idx]
                    valid_idx += 1
            return result.tolist()
            
        return final_scores.tolist()