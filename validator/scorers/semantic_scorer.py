from typing import List, Optional
import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
from fiber.logging_utils import get_logger
from .base_scorer import BaseScorer
from ..config.hardware_config import HardwareConfig, PerformanceConfig
from ..config.progress_config import ProgressStages

logger = get_logger(__name__)

class SemanticConfig:
    """Configuration for semantic scoring parameters"""
    DEFAULT_MODEL = 'all-MiniLM-L6-v2'
    SIMILARITY_THRESHOLD = 0.8
    WEIGHTS = {
        'originality': 0.6,
        'uniqueness': 0.4
    }

class SemanticScorer(BaseScorer):
    """Analyzes semantic similarity between texts and calculates originality scores."""
    
    def __init__(self, 
                 hardware_config: Optional[HardwareConfig] = None,
                 model_name: str = SemanticConfig.DEFAULT_MODEL):
        """Initialize the scorer with hardware-accelerated model."""
        self.config = hardware_config or PerformanceConfig.get_config()
        self.device = torch.device(self.config.device_type)
        self._init_model(model_name)
        self._log_initialization()
        
        # Scoring parameters
        self.similarity_threshold = SemanticConfig.SIMILARITY_THRESHOLD
        self.weights = SemanticConfig.WEIGHTS

    def _init_model(self, model_name: str) -> None:
        """Initialize the transformer model on the appropriate device"""
        self.model = SentenceTransformer(model_name)
        self.model.to(self.device)

    def _log_initialization(self) -> None:
        """Log initialization details"""
        logger.info(f"Initialized SemanticScorer with device: {self.config.device_type}")
        if self.config.device_type == "cuda":
            logger.info(f"Using CUDA GPU: {torch.cuda.get_device_name(0)}")
        elif self.config.device_type == "mps":
            logger.info("Using Apple Silicon MPS acceleration")
        else:
            logger.info("Using CPU - no hardware acceleration available")

    def _get_similarity_matrix(self, embeddings: torch.Tensor) -> torch.Tensor:
        """Calculate pairwise similarity matrix using hardware acceleration."""
        embeddings = embeddings.to(self.device, dtype=torch.float32)
        norm = torch.nn.functional.normalize(embeddings, p=2, dim=1)
        similarity_matrix = torch.mm(norm, norm.t())
        similarity_matrix.fill_diagonal_(0)
        return similarity_matrix

    def _calculate_component_scores(self, embeddings: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Calculate originality and uniqueness scores."""
        similarity_matrix = self._get_similarity_matrix(embeddings)
        
        # Calculate originality scores (inverse of average similarity)
        originality_scores = 1 - similarity_matrix.mean(dim=1)
        
        # Calculate uniqueness scores (inverse of similar post count)
        similar_posts = (similarity_matrix > self.similarity_threshold).sum(dim=1).float()
        uniqueness_scores = 1.0 / (1.0 + similar_posts)
        
        return (
            torch.clamp(originality_scores, 0, 1),
            torch.clamp(uniqueness_scores, 0, 1)
        )

    def _process_batch(self, batch: List[str]) -> np.ndarray:
        """Process a single batch of texts"""
        try:
            with torch.no_grad():
                embeddings = self.model.encode(
                    batch,
                    show_progress_bar=False,
                    batch_size=min(self.config.batch_size, 128),
                    convert_to_tensor=True,
                    device=self.device,
                    normalize_embeddings=True
                )
                
                orig_scores, uniq_scores = self._calculate_component_scores(embeddings)
                batch_scores = (
                    self.weights['originality'] * orig_scores +
                    self.weights['uniqueness'] * uniq_scores
                ).cpu().numpy()
                
                # Clean up GPU memory
                del embeddings, orig_scores, uniq_scores
                if self.config.device_type == "cuda":
                    torch.cuda.empty_cache()
                
                return np.clip(batch_scores, 0, 1)
                
        except RuntimeError as e:
            if "out of memory" in str(e) or "buffer size" in str(e):
                return self._handle_oom_error(batch, e)
            raise e

    def _handle_oom_error(self, batch: List[str], error: RuntimeError) -> np.ndarray:
        """Handle out-of-memory errors by splitting the batch"""
        half_batch = len(batch) // 2
        if half_batch < 1:
            raise error
        
        scores1 = self.calculate_scores(batch[:half_batch])
        scores2 = self.calculate_scores(batch[half_batch:])
        return np.concatenate([scores1, scores2])

    def calculate_score(self, text: str) -> float:
        """Calculate score for a single text"""
        if not text or not text.strip():
            return 0.0
        return self.calculate_scores([text])[0]

    def calculate_scores(self, 
                        texts: List[str], 
                        progress_bar: Optional[tqdm] = None) -> List[float]:
        """Calculate semantic scores for a list of texts"""
        if not texts:
            return []

        valid_texts = [text for text in texts if text and text.strip()]
        if not valid_texts:
            return [0.0] * len(texts)

        if progress_bar:
            progress_bar.set_postfix(
                ProgressStages.get_scoring_status(
                    ProgressStages.SEMANTIC,
                    texts=len(valid_texts)
                )
            )

        final_scores = np.zeros(len(texts), dtype=np.float32)
        
        # Process in batches
        for i in range(0, len(valid_texts), self.config.batch_size):
            batch = valid_texts[i:i + self.config.batch_size]
            batch_scores = self._process_batch(batch)
            final_scores[i:i + len(batch)] = batch_scores
            
            if progress_bar:
                progress_bar.set_postfix(
                    ProgressStages.get_semantic_status(
                        min(i + self.config.batch_size, len(valid_texts)),
                        len(valid_texts)
                    )
                )

        # Handle invalid texts by mapping scores back to original indices
        if len(valid_texts) != len(texts):
            result = np.zeros(len(texts), dtype=np.float32)
            valid_idx = 0
            for i, text in enumerate(texts):
                if text and text.strip():
                    result[i] = final_scores[valid_idx]
                    valid_idx += 1
            return result.tolist()
            
        return final_scores.tolist() 