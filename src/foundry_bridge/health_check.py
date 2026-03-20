#!/usr/bin/env python3
"""Health check script for the transcriber service.

Verifies that the transcriber can establish a WebSocket connection to the bridge
and receive a hello_ack response.

Exit codes:
  0: Healthy - successfully connected and received hello_ack
  1: Unhealthy - failed to connect or invalid response
"""

import asyncio
import json
import logging
import os
import sys
from typing import Optional

from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException


LOG_LEVEL = os.environ.get("LOG_LEVEL", "WARNING")
logging.basicConfig(level=LOG_LEVEL, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


async def check_health(uri: str, timeout: float = 5.0) -> bool:
    """Check if the bridge is healthy.

    Args:
        uri: WebSocket URI of the bridge (e.g., 'ws://bridge:8765')
        timeout: Timeout in seconds for the connection attempt

    Returns:
        True if the bridge is healthy, False otherwise
    """
    try:
        logger.debug(f"Connecting to bridge at {uri}")
        async with asyncio.timeout(timeout):
            async with connect(uri, max_size=None) as ws:
                logger.debug("Connected to bridge, sending hello")
                await ws.send(
                    json.dumps({
                        "type": "hello",
                        "role": "subscriber",
                        "name": "health-check",
                    })
                )

                logger.debug("Waiting for hello_ack")
                response_text = await ws.recv()
                response = json.loads(response_text)

                if response.get("type") == "hello_ack":
                    logger.debug("Received hello_ack, bridge is healthy")
                    return True
                else:
                    logger.warning(f"Unexpected response: {response}")
                    return False

    except asyncio.TimeoutError:
        logger.warning(f"Connection timed out after {timeout}s")
        return False
    except WebSocketException as e:
        logger.warning(f"WebSocket error: {e}")
        return False
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Response parsing error: {e}")
        return False
    except Exception as e:
        logger.warning(f"Unexpected error: {e}")
        return False


def main() -> int:
    """Run the health check."""
    bridge_uri = os.environ.get("BRIDGE_URI", "ws://localhost:8765")
    logger.debug(f"Health check for bridge at {bridge_uri}")

    try:
        is_healthy = asyncio.run(check_health(bridge_uri))
        if is_healthy:
            print("OK")
            return 0
        else:
            print("FAILED")
            return 1
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print("FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
