from typing import Optional
from cryptography.fernet import Fernet
from dataclasses import dataclass, asdict


@dataclass
class JSONSerializable:
    def to_dict(self):
        return asdict(self)


@dataclass
class VerifiedTweet(JSONSerializable):
    tweet_id: str
    url: str
    timestamp: str
    full_text: str


@dataclass
class Profile(JSONSerializable):
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
class RegisteredAgentRequest(JSONSerializable):
    def __init__(
        self,
        subnet_id: int,
        version: str,
        isActive: bool,
        isNominated: bool,
        nominations: int,
        marketcap: int,
        profile: dict,
        hotkey: Optional[str] = None,
        uid: Optional[str] = None,
        emissions: Optional[int] = None,
        verification_tweet: Optional[str] = None,
    ):
        self.subnet_id = subnet_id
        self.version = version
        self.isActive = isActive
        self.isNominated = isNominated
        self.nominations = nominations
        self.marketcap = marketcap
        self.profile = profile
        self.hotkey = hotkey
        self.uid = uid
        self.emissions = emissions
        self.verification_tweet = verification_tweet


@dataclass
class RegisteredAgentResponse(JSONSerializable):
    ID: int
    HotKey: str
    UID: str
    UserID: str
    SubnetID: int
    Version: str
    IsActive: bool
    CreatedAt: str
    UpdatedAt: str
    Avatar: Optional[str]
    Banner: Optional[str]
    Biography: Optional[str]
    Birthday: Optional[str]
    FollowersCount: int
    FollowingCount: int
    FriendsCount: int
    IsPrivate: bool
    IsVerified: bool
    Joined: str
    LikesCount: int
    ListedCount: int
    Location: Optional[str]
    Name: Optional[str]
    PinnedTweetIDs: list[str]
    TweetsCount: int
    Emissions: float
    URL: Optional[str]
    Username: Optional[str]
    Website: Optional[str]
    VerificationTweetID: str
    VerificationTweetURL: str
    VerificationTweetTimestamp: str
    VerificationTweetText: str


@dataclass
class ConnectedNode(JSONSerializable):
    address: str
    symmetric_key: str
    symmetric_key_uuid: str
    fernet: Fernet
