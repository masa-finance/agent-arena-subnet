from typing import TypedDict
from typing import Optional, Dict
from protocol.x.queue import RequestQueue
from fiber.logging_utils import get_logger

logger = get_logger(__name__)


class Tweet(TypedDict):
    user_id: str
    tweet_id: str
    url: str
    timestamp: str
    full_text: str


class RegisteredAgent(TypedDict):
    hotkey: str
    uid: int
    subnet_id: int
    version: str
    isActive: bool
    verification_tweet: Optional[Tweet]


def generate_queue(agents: Dict[str, RegisteredAgent]):

    queue = RequestQueue()

    for agent in agents.values():
        logger.info(f"Adding request to the queue for id {
                    agent['uid']} - {agent['hotkey']}")

        # TODO: Replace this with the agent username and correct metadata
        queue.add_request(
            request_type='search',
            request_data={'query': 'to: @getmasafi', 'metadata': agent},
            priority=1
        )
        queue.add_request(
            request_type='search',
            request_data={'query': 'from: @getmasafi', 'metadata': agent},
            priority=1
        )
    queue.start()
    return queue
