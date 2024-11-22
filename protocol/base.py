from pydantic import BaseModel
from typing import Optional, List

class TwitterAgentRegistration(BaseModel):
    twitter_handle: str
    agent_uid: int
    agent_hotkey: str
    
class TwitterMetrics(BaseModel):
    impressions: int
    likes: int
    replies: int
    followers: int
    timestamp: float

class TokenMetrics(BaseModel):
    holders: int
    volume_24h: float
    market_cap: float