"""Test module for queue management functionality.

This test module verifies the queue generation and management for X API operations.
It provides test type definitions and queue generation test cases.
"""

from typing import TypedDict
from typing import Optional, Dict
from protocol.x.queue import RequestQueue
from fiber.logging_utils import get_logger
from interfaces.types import (
    RegisteredAgentResponse,
)

logger = get_logger(__name__)


class Tweet(TypedDict):
    """Test type definition for Tweet data structure.

    Test Attributes:
        user_id (str): Test X user ID
        tweet_id (str): Test tweet identifier
        url (str): Test URL
        timestamp (str): Test timestamp
        full_text (str): Test text content
    """

    user_id: str
    tweet_id: str
    url: str
    timestamp: str
    full_text: str


class RegisteredAgent(TypedDict):
    """Test type definition for registered agent information.

    Test Attributes:
        hotkey (str): Test hotkey identifier
        uid (int): Test unique identifier
        subnet_id (int): Test subnet ID
        version (str): Test version string
        isActive (bool): Test active status
        verification_tweet (Optional[Tweet]): Test tweet data
    """

    hotkey: str
    uid: int
    subnet_id: int
    version: str
    isActive: bool
    verification_tweet: Optional[Tweet]


def generate_queue(agents: Dict[str, RegisteredAgentResponse]):
    """Test function for generating request queues.

    Tests creation of RequestQueue instance and population with test search requests.
    Verifies queue initialization and request addition for test agents.

    Args:
        agents (Dict[str, RegisteredAgentResponse]): Test dictionary of agents

    Returns:
        RequestQueue: Test queue instance for verification
    """
    queue = RequestQueue()

    print(agents)

    for agent in agents.values():
        print("AGENT:", agent)
        logger.info(f"Adding request to the queue for id {agent.UID}")

        # TODO: Replace this with the agent username and correct metadata
        queue.add_request(
            request_type="search",
            request_data={"query": f"to: {agent.Username}", "metadata": agent},
            priority=1,
        )
        queue.add_request(
            request_type="search",
            request_data={"query": f"from: {agent.Username}", "metadata": agent},
            priority=1,
        )
    queue.start()
    return queue
