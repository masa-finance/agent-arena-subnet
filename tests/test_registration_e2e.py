import pytest
from loguru import logger


@pytest.fixture(autouse=True)
def setup_logging():
    """Configure logging for all tests"""
    logger.remove()  # Remove default handler
    logger.add(
        sink=lambda msg: print(msg),
        level="DEBUG",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
    )


def test_registration():
    pass
