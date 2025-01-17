from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional
from tqdm import tqdm
from time import time

class ProgressStages(str, Enum):
    """Enum for different stages of the scoring process"""
    INITIALIZATION = "Initialization"
    FILTERING = "Filtering Posts"
    SEMANTIC = "Semantic Analysis"
    ENGAGEMENT = "Engagement Scoring"
    FEATURE_IMPORTANCE = "Feature Importance"
    SCORING = "Scoring"
    NORMALIZATION = "Score Normalization"
    COMPLETE = "Complete"

    @staticmethod
    def get_scoring_status(stage: str, **kwargs: Any) -> Dict[str, str]:
        """Format status message with additional info"""
        status = {"stage": stage}
        status.update({k: str(v) for k, v in kwargs.items()})
        return status

    @staticmethod
    def get_semantic_status(current: int, total: int, rate: Optional[float] = None) -> Dict[str, str]:
        """Format semantic scoring progress status with processing rate"""
        status = {
            "stage": ProgressStages.SEMANTIC,
            "progress": f"{current}/{total}"
        }
        if rate is not None:
            status["rate"] = f"{rate:.2f} agents/s"
        return status

@dataclass
class ProgressBarConfig:
    """Base configuration for progress bars"""
    desc: str
    total: int
    initial_status: Dict[str, Any]
    disable: bool = False
    leave: bool = True
    
    def create_progress_bar(self) -> tqdm:
        """Create a configured progress bar"""
        bar = tqdm(
            total=self.total,
            desc=self.desc,
            initial=0,
            disable=self.disable,
            leave=self.leave,
            dynamic_ncols=True
        )
        if self.initial_status:
            bar.set_postfix(**self.initial_status, refresh=True)
        return bar

@dataclass
class ScoringProgressConfig(ProgressBarConfig):
    """Configuration for agent scoring progress"""
    def __init__(self, total_agents: int):
        super().__init__(
            desc="Scoring",
            total=total_agents,
            initial_status={},
            leave=True
        )

@dataclass
class ShapProgressConfig(ProgressBarConfig):
    """Configuration for SHAP value calculation progress"""
    def __init__(self, total_samples: int):
        super().__init__(
            desc="SHAP Analysis",
            total=total_samples,
            initial_status={"stage": ProgressStages.FEATURE_IMPORTANCE},
            leave=True
        ) 