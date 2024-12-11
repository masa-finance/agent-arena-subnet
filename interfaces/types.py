from typing import Optional
from cryptography.fernet import Fernet
from dataclasses import dataclass


@dataclass
class VerifiedTweet:
    tweet_id: str
    url: str
    timestamp: str  # Format: 2024-12-10T18:27:16Z
    full_text: str


@dataclass
class Profile:
    UserID: str
    Avatar: Optional[str] = None
    Banner: Optional[str] = None
    Biography: Optional[str] = None
    Birthday: Optional[str] = None
    FollowersCount: Optional[int] = None
    FollowingCount: Optional[int] = None
    FriendsCount: Optional[int] = None
    IsPrivate: Optional[bool] = None
    IsVerified: Optional[bool] = None
    Joined: Optional[str] = None
    LikesCount: Optional[int] = None
    ListedCount: Optional[int] = None
    Location: Optional[str] = None
    Name: Optional[str] = None
    PinnedTweetIDs: Optional[list[str]] = None
    TweetsCount: Optional[int] = None
    URL: Optional[str] = None
    Username: Optional[str] = None
    Website: Optional[str] = None
    Sensitive: Optional[bool] = None
    Following: Optional[bool] = None
    FollowedBy: Optional[bool] = None


@dataclass
class RegisteredAgent:
    hotkey: str
    uid: int
    subnet_id: int
    version: str
    isActive: bool
    verification_tweet: VerifiedTweet
    profile: Optional[dict[str, Profile]]


@dataclass
class RegisteredMiner:
    address: str
    symmetric_key: str
    symmetric_key_uuid: str
    fernet: Fernet
