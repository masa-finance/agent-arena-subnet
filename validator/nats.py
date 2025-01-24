import asyncio
import os
import json
from nats.aio.client import Client as NATS
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from neurons.validator import AgentValidator


class MinersNATSPublisher:
    def __init__(self, validator: "AgentValidator"):
        self.nc = NATS()
        self.validator = validator

    async def send_connected_nodes(self):
        # Connect to the NATS server
        await self.nc.connect(os.getenv("TEE_ADDRESS"))

        try:
            # Get connected nodes from the validator
            connected_nodes = self.validator.connected_nodes
            miners_list = (
                [f"{node.address}:{node.port}" for node in connected_nodes.values()]
                if connected_nodes
                else []
            )

            # Create the NATS message in the required format
            nats_message = json.dumps({"Miners": miners_list})

            # Send the JSON message to the TEE_ADDRESS
            channel_name = os.getenv("TEE_NATS_CHANNEL_NAME", "miners")
            await self.nc.publish(channel_name, nats_message.encode())
        finally:
            # Ensure the NATS connection is closed
            await self.nc.close()


# Example usage
async def main():
    # Assuming you have an instance of AgentValidator
    validator = AgentValidator()
    nats_client = TEENATSClient(validator)
    await nats_client.send_connected_nodes()


if __name__ == "__main__":
    asyncio.run(main())
