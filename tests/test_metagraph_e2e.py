import pytest
from neurons.validator import AgentValidator
from fiber.logging_utils import get_logger

logger = get_logger(__name__)


@pytest.mark.asyncio
async def test_metagraph_e2e():
    return
    # Initialize a real Validator instance
    validator = AgentValidator()
    # await validator.start()
    # Run the sync_metagraph method
    await validator.sync_metagraph()

    # Verify that nodes are populated
    assert (
        len(validator.metagraph.nodes) > 0
    ), "Nodes should be populated after sync_metagraph"

    logger.info(f"Successfully synced {len(validator.metagraph.nodes)} nodes")
