from typing import Optional, List, Dict, Any
from cryptography.fernet import Fernet
from dataclasses import dataclass, asdict
from pydantic import BaseModel


@dataclass
class JSONSerializable:
    def to_dict(self):
        return asdict(self)


@dataclass
class VerifiedTweet(JSONSerializable):
    TweetID: str
    URL: str
    Timestamp: str
    FullText: str


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
    ID: int
    HotKey: str
    UID: int
    SubnetID: int
    Version: str
    Emissions: float
    VerificationTweet: Optional[VerifiedTweet]
    Profile: Optional[dict[str, Profile]]


@dataclass
class RegisteredAgentResponse(JSONSerializable):
    ID: int
    HotKey: str
    UID: str
    UserID: str
    SubnetID: int
    Version: str
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
    Name: str
    PinnedTweetIDs: Optional[list[str]]
    TweetsCount: int
    URL: Optional[str]
    Username: str
    Website: Optional[str]
    VerificationTweetID: str
    VerificationTweetURL: str
    VerificationTweetTimestamp: str
    VerificationTweetText: str
    Emissions: float
    Marketcap: int


@dataclass
class ConnectedNode(JSONSerializable):
    address: str
    symmetric_key: str
    symmetric_key_uuid: str
    fernet: Fernet


@dataclass
class Tweet(BaseModel, JSONSerializable):
    ConversationID: Optional[str]
    GIFs: Optional[List[str]]
    Hashtags: Optional[List[str]]
    HTML: Optional[str]
    ID: Optional[str]
    InReplyToStatus: Optional[str]
    InReplyToStatusID: Optional[str]
    IsQuoted: Optional[bool]
    IsPin: Optional[bool]
    IsReply: Optional[bool]
    IsRetweet: Optional[bool]
    IsSelfThread: Optional[bool]
    Likes: Optional[int]
    Name: Optional[str]
    Mentions: Optional[List[Dict[str, Any]]]
    PermanentURL: Optional[str]
    Photos: Optional[List[str]]
    Place: Optional[Dict[str, Any]]
    QuotedStatus: Optional[str]
    QuotedStatusID: Optional[str]
    Replies: Optional[int]
    Retweets: Optional[int]
    RetweetedStatus: Optional[str]
    RetweetedStatusID: Optional[str]
    Text: Optional[str]
    Thread: Optional[str]
    TimeParsed: Optional[str]
    Timestamp: Optional[int]
    URLs: Optional[List[str]]
    UserID: Optional[str]
    Username: Optional[str]
    Videos: Optional[List[str]]
    Views: Optional[int]
    SensitiveContent: Optional[bool]


class RegistrationCallback(BaseModel):
    agent: str
    message: Optional[str] = None
