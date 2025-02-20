import pytest
from neurons.miner import AgentMiner
from fiber.logging_utils import get_logger

logger = get_logger(__name__)


@pytest.mark.asyncio
async def test_miner_e2e():
    return
    # Initialize a real miner instance
    miner = AgentMiner()
