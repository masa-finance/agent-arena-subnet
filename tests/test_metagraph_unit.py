import pytest
from unittest.mock import MagicMock
from neurons.validator import AgentValidator


@pytest.fixture
def mock_validator():
    # Create a mock Validator instance
    mock_validator = MagicMock(spec=AgentValidator)
    mock_validator.metagraph = MagicMock()
    mock_validator.substrate = MagicMock()
    mock_validator.node_manager = MagicMock()
    mock_validator.substrate.url = "wss://test.finney.opentensor.ai:443"
    return mock_validator


def test_sync_substrate(mock_validator):
    # Test sync_substrate method
    mock_validator.sync_substrate()
    mock_validator.substrate = mock_validator.substrate  # Ensure substrate is set


@pytest.mark.asyncio
async def test_sync_metagraph(mock_validator):
    # mock_validator.node_manager.remove_disconnected_nodes = AsyncMock()

    # Test sync_metagraph method
    await mock_validator.sync_metagraph()
    # mock_validator.sync_nodes.assert_called_once()
    # mock_validator.node_manager.remove_disconnected_nodes.assert_awaited_once()
