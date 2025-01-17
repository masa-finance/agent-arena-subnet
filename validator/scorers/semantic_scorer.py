from typing import List, Optional
import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
from fiber.logging_utils import get_logger
from interfaces.types import Tweet
from .base_scorer import BaseScorer
from ..config.hardware_config import HardwareConfig, PerformanceConfig
from ..config.progress_config import ProgressStages

logger = get_logger(__name__)

class SemanticConfig:
    """Configuration for semantic scoring parameters"""
    DEFAULT_MODEL = 'all-MiniLM-L6-v2'
    SIMILARITY_THRESHOLD = 0.85
    WEIGHTS = {
        'originality': 0.7,
        'uniqueness': 0.3
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
        """Calculate originality and uniqueness scores with increased sensitivity"""
        similarity_matrix = self._get_similarity_matrix(embeddings)
        
        # Calculate originality scores with exponential penalty for similarity
        originality_scores = torch.exp(-similarity_matrix.mean(dim=1) * 2)
        
        # Calculate uniqueness scores with stronger penalties for similar content
        similar_posts = (similarity_matrix > self.similarity_threshold).sum(dim=1).float()
        uniqueness_scores = torch.exp(-similar_posts * 0.5)
        
        # Apply non-linear scaling to amplify differences
        originality_scores = torch.pow(originality_scores, 1.5)
        uniqueness_scores = torch.pow(uniqueness_scores, 1.5)
        
        return (
            torch.clamp(originality_scores, 0, 1),
            torch.clamp(uniqueness_scores, 0, 1)
        )

    def calculate_score(self, text: str) -> float:
        """Calculate score for a single text"""
        if not text or not text.strip():
            return 0.0
        return self.calculate_scores([text])[0]

    def calculate_scores(self, 
                        texts: List[str], 
                        progress_bar: Optional[tqdm] = None) -> List[float]:
        """Calculate semantic scores with increased weight for quality content"""
        if not texts:
            return []
            
        try:
            with torch.no_grad():
                embeddings = self.model.encode(
                    texts,
                    show_progress_bar=False,
                    batch_size=min(self.config.batch_size, 128),
                    convert_to_tensor=True,
                    device=self.device,
                    normalize_embeddings=True
                )
                
                orig_scores, uniq_scores = self._calculate_component_scores(embeddings)
                
                # Combine scores with weighted components
                combined_scores = (
                    self.weights['originality'] * orig_scores +
                    self.weights['uniqueness'] * uniq_scores
                ).cpu().numpy()
                
                # Apply non-linear scaling to amplify high-quality content
                scores = [np.power(score, 0.75) for score in combined_scores]
                
                # Clean up GPU memory
                del embeddings, orig_scores, uniq_scores
                if self.config.device_type == "cuda":
                    torch.cuda.empty_cache()
                
                return scores
                
        except RuntimeError as e:
            if "out of memory" in str(e):
                logger.warning("GPU OOM error, falling back to CPU")
                self.device = torch.device("cpu")
                self.model.to(self.device)
                return self.calculate_scores(texts, progress_bar)
            raise e 