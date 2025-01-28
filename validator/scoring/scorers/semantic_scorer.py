from typing import List, Optional
import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
from fiber.logging_utils import get_logger
from interfaces.types import Tweet
from validator.scoring.scorers.base_scorer import BaseScorer
from validator.config.hardware_config import HardwareConfig, PerformanceConfig
from collections import Counter

logger = get_logger(__name__)

class SemanticConfig:
    """Configuration for semantic scoring parameters"""
    DEFAULT_MODEL = 'all-MiniLM-L6-v2'
    SIMILARITY_THRESHOLD = 0.85
    WEIGHTS = {
        'originality': 0.7,
        'uniqueness': 0.3
    }
    # Add keyword stuffing detection
    KEYWORD_THRESHOLD = 0.3  # Max ratio of repeated key phrases
    MIN_POST_LENGTH = 20     # Minimum meaningful post length
    
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

    def _detect_keyword_stuffing(self, texts: List[str]) -> torch.Tensor:
        """Detect repetitive phrases and keyword stuffing"""
        keyword_penalties = []
        
        for text in texts:
            # Skip empty or very short texts
            if not text or len(text) < SemanticConfig.MIN_POST_LENGTH:
                keyword_penalties.append(0.2)  # Penalize too-short content
                continue
                
            # Extract common phrases (2-3 words)
            words = text.lower().split()
            phrases = []
            for i in range(len(words)-1):
                phrases.append(' '.join(words[i:i+2]))
                if i < len(words)-2:
                    phrases.append(' '.join(words[i:i+3]))
            
            # Count phrase frequencies
            phrase_counts = Counter(phrases)
            total_phrases = len(phrases)
            
            # Calculate repetition ratio
            if total_phrases > 0:
                repeat_ratio = max(phrase_counts.values()) / total_phrases
                if repeat_ratio > SemanticConfig.KEYWORD_THRESHOLD:
                    keyword_penalties.append(0.3)  # Heavy penalty for keyword stuffing
                else:
                    keyword_penalties.append(1.0)
            else:
                keyword_penalties.append(0.5)
        
        return torch.tensor(keyword_penalties, device=self.device)

    def _calculate_component_scores(self, embeddings: torch.Tensor, texts: List[str]) -> tuple[torch.Tensor, torch.Tensor]:
        """Calculate originality and uniqueness scores with content quality checks"""
        similarity_matrix = self._get_similarity_matrix(embeddings)
        
        # Get keyword stuffing penalties
        quality_penalties = self._detect_keyword_stuffing(texts)
        
        # Calculate originality with content quality consideration
        mean_similarity = similarity_matrix.mean(dim=1)
        std_similarity = similarity_matrix.std(dim=1)
        
        originality_scores = torch.exp(-mean_similarity * 2) * (1 + std_similarity)
        
        # Calculate uniqueness with stronger penalties
        similar_posts = (similarity_matrix > self.similarity_threshold).sum(dim=1).float()
        uniqueness_scores = torch.exp(-similar_posts * 0.8)
        
        # Apply quality penalties
        originality_scores = originality_scores * quality_penalties
        uniqueness_scores = uniqueness_scores * quality_penalties
        
        return (
            torch.clamp(originality_scores, 0, 1),
            torch.clamp(uniqueness_scores, 0, 1)
        )

    def calculate_score(self, text: str) -> float:
        """Calculate score for a single text"""
        if not text or not text.strip():
            return 0.0
        return self.calculate_scores([text])[0]

    def calculate_scores(self, texts: List[str], progress_bar: Optional[tqdm] = None) -> List[float]:
        """Calculate semantic scores with quality content emphasis"""
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
                
                orig_scores, uniq_scores = self._calculate_component_scores(embeddings, texts)
                
                # Combine scores with weighted components
                combined_scores = (
                    self.weights['originality'] * orig_scores +
                    self.weights['uniqueness'] * uniq_scores
                ).cpu().numpy()
                
                # Apply stronger non-linear scaling for quality emphasis
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