from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional
from tqdm import tqdm

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
    def get_semantic_status(current: int, total: int) -> Dict[str, str]:
        """Format semantic scoring progress status"""
        return {
            "stage": ProgressStages.SEMANTIC,
            "progress": f"{current}/{total}"
        }

@dataclass
class ProgressBarConfig:
    """Configuration for progress bars"""
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
            initial=0,  # Always start at 0
            disable=self.disable,
            leave=self.leave
        )
        # Set the initial status as postfix
        if self.initial_status:
            bar.set_postfix(**self.initial_status)
        return bar 