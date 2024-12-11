from typing import TypedDict, Optional
from cryptography.fernet import Fernet


class VerifiedTweet(TypedDict):
    tweet_id: str
    url: str
    timestamp: str  # Format: 2024-12-10T18:27:16Z
    full_text: str


class RegisteredAgent(TypedDict):
    hotkey: str
    uid: int
    subnet_id: int
    version: str
    isActive: bool
    verification_tweet: Optional[VerifiedTweet]


class RegisteredMiner(TypedDict):
    address: str
    symmetric_key: str
    symmetric_key_uuid: str
    fernet: Fernet
