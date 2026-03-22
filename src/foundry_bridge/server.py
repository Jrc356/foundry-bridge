import asyncio
import json
import logging
import signal
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

import uvicorn
from websockets.asyncio.server import ServerConnection, serve

from foundry_bridge import note_taker, transcriber
from foundry_bridge.api import app as fastapi_app
from foundry_bridge.db import get_or_create_game

logger = logging.getLogger(__name__)

HOST = "0.0.0.0"
WS_PORT = int(__import__("os").environ.get("WS_PORT", "8765"))
HTTP_PORT = int(__import__("os").environ.get("HTTP_PORT", "8766"))
API_PORT = int(__import__("os").environ.get("API_PORT", "8767"))

# Connection timeout: close if no messages received in 30 seconds
CONNECTION_TIMEOUT_SECS = 30


@dataclass
class ConnectionState:
    ws: ServerConnection
    client_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    last_audio_header: Optional[dict] = None
    game_id: Optional[int] = None
    last_activity_time: float = field(default_factory=time.time)  # Track idle time


connection_states: dict[ServerConnection, ConnectionState] = {}

_ws_server = None


async def safe_send_json(ws: ServerConnection, payload: dict) -> bool:
    try:
        await ws.send(json.dumps(payload))
        return True
    except Exception:
        return False


async def register_connection(ws: ServerConnection) -> ConnectionState:
    state = ConnectionState(ws=ws)
    connection_states[ws] = state
    return state


async def unregister_connection(ws: ServerConnection) -> None:
    state = connection_states.pop(ws, None)
    if state:
        await transcriber.handle_event({
            "type": "participant_detached",
            "participantId": state.client_id,
        })


async def handle_json_message(state: ConnectionState, data: dict) -> None:
    state.last_activity_time = time.time()  # Update activity tracking
    msg_type = data.get("type")
    logger.debug("Received message type=%r from client %s", msg_type, state.client_id)
    
    if msg_type == "audio":
        state.last_audio_header = data
        return
    
    if msg_type == "game_identify":
        hostname = data.get("hostname", "")
        world_id = data.get("world_id", "")
        name = data.get("name", hostname)
        if hostname and world_id:
            # World-switch: destroy existing SpeakerWorker before changing game_id
            if state.game_id is not None:
                await transcriber.handle_event({
                    "type": "participant_detached",
                    "participantId": state.client_id,
                })
            game = await get_or_create_game(hostname=hostname, world_id=world_id, name=name)
            state.game_id = game.id
            await safe_send_json(state.ws, {"type": "game_identify_ack", "game_id": state.game_id})
            logger.info("Game identified: %s/%s (id=%d)", hostname, world_id, game.id)
        else:
            logger.warning("game_identify missing hostname or world_id: %r", data)
            await safe_send_json(state.ws, {
                "type": "game_identify_nack",
                "reason": "hostname and world_id are required",
            })
        return  # do not pass game_identify to transcriber
    
    # Validate that game_id is set before processing other events
    if state.game_id is None:
        logger.warning(
            "Dropping %s event: game_id not set (client=%s). Send game_identify first.",
            msg_type,
            state.client_id,
        )
        await safe_send_json(state.ws, {
            "type": "error",
            "message": "game_id not set; send game_identify first",
        })
        return
    
    # Validate participant_attached messages
    if msg_type == "participant_attached":
        participant_id = data.get("participantId")
        name = data.get("name") or data.get("label")
        if not participant_id or not name:
            logger.warning(
                "Invalid participant_attached message (client=%s): participantId=%s name=%s",
                state.client_id,
                participant_id,
                name,
            )
            await safe_send_json(state.ws, {
                "type": "error",
                "message": "participant_attached missing participantId or name",
            })
            return
        logger.info(
            "Participant attached: client=%s participantId=%s name=%s game_id=%s",
            state.client_id,
            participant_id,
            name,
            state.game_id,
        )
    
    await transcriber.handle_event(data)


async def handle_binary_message(state: ConnectionState, payload: bytes) -> None:
    state.last_activity_time = time.time()  # Update activity tracking
    header = state.last_audio_header
    if header is None or state.game_id is None:
        logger.warning(
            "Dropping audio frame: last_audio_header=%s game_id=%s",
            header,
            state.game_id,
        )
        return

    _char_name = (
        header.get("characterName")
        or header.get("name")
        or str(header.get("participantId", ""))
    ).strip().lower()
    if not _char_name:
        logger.warning("Audio frame has no character_name fallback; using client_id")
        _char_name = state.client_id

    out_header = {
        **header,
        "character_name": _char_name,
        "participantId": state.client_id,
    }

    logger.debug(
        "Audio frame: client=%s char=%r sample_rate=%s channels=%s bytes=%d",
        state.client_id, _char_name,
        out_header.get("sampleRate", 48000),
        out_header.get("channels", 1),
        len(payload),
    )
    await transcriber.handle_audio_frame(out_header, payload, game_id=state.game_id)


async def handler(ws: ServerConnection) -> None:
    state = await register_connection(ws)
    logger.info("connection opened %s", state.client_id)

    try:
        async for message in ws:
            if isinstance(message, str):
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    logger.warning("Ignoring malformed JSON from %s: %r", state.client_id, message[:200])
                    await safe_send_json(ws, {
                        "type": "error",
                        "message": "invalid JSON",
                    })
                    continue

                await handle_json_message(state, data)
            else:
                await handle_binary_message(state, message)

    except Exception as exc:
        logger.info("connection closed %s (%s)", state.client_id, exc)
    finally:
        await unregister_connection(ws)


async def _monitor_connection_timeouts() -> None:
    """Monitor active connections and close any that have been idle for too long."""
    while True:
        try:
            await asyncio.sleep(10)  # Check every 10 seconds
            now = time.time()
            timed_out = []
            
            for ws, state in list(connection_states.items()):
                idle_time = now - state.last_activity_time
                if idle_time > CONNECTION_TIMEOUT_SECS:
                    timed_out.append((ws, state.client_id, idle_time))
            
            for ws, client_id, idle_time in timed_out:
                logger.warning(
                    "Connection timeout: client=%s idle_time=%.1fs",
                    client_id,
                    idle_time,
                )
                try:
                    await ws.close(code=1000, reason=f"idle timeout ({idle_time:.0f}s)")
                except Exception as e:
                    logger.debug("Error closing timed-out connection %s: %s", client_id, e)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.exception("Error in connection timeout monitor: %s", exc)


async def _handle_health(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    request_line = (await reader.readline()).decode(errors="replace")
    parts = request_line.split(" ")
    method = parts[0] if parts else ""
    path = parts[1] if len(parts) > 1 else ""
    if method != "GET" or path != "/health":
        writer.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
        await writer.drain()
        writer.close()
        return
    body = b'{"status": "ok"}'
    response = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: " + str(len(body)).encode() + b"\r\n"
        b"\r\n" + body
    )
    writer.write(response)
    await writer.drain()
    writer.close()


async def _main() -> None:
    global _ws_server
    logger.info("starting ingestion bridge on ws://%s:%s", HOST, WS_PORT)

    health_server = await asyncio.start_server(_handle_health, HOST, HTTP_PORT)
    logger.info("health check server started on http://%s:%s/health", HOST, HTTP_PORT)

    # Start FastAPI REST + SPA server
    api_config = uvicorn.Config(fastapi_app, host=HOST, port=API_PORT, log_level="warning")
    api_server = uvicorn.Server(api_config)
    api_task = asyncio.create_task(api_server.serve())
    logger.info("API server started on http://%s:%s", HOST, API_PORT)

    await transcriber.init()
    note_taker.start_background_tasks()

    loop = asyncio.get_running_loop()

    async def _handle_signal() -> None:
        logger.info("Shutdown signal received")
        if _ws_server is not None:
            _ws_server.close()
            await _ws_server.wait_closed()
            logger.info("WebSocket server closed")
        api_server.should_exit = True
        await note_taker.stop_background_tasks()
        await transcriber.shutdown()

    loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(_handle_signal()))
    loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(_handle_signal()))

    # Start connection timeout monitor
    timeout_monitor_task = asyncio.create_task(_monitor_connection_timeouts())
    logger.info("Connection timeout monitor started (timeout=%ds)", CONNECTION_TIMEOUT_SECS)

    try:
        async with serve(handler, HOST, WS_PORT, max_size=None) as ws_server:
            _ws_server = ws_server
            logger.info("server ready")
            async with health_server:
                await ws_server.wait_closed()
    finally:
        timeout_monitor_task.cancel()
        try:
            await timeout_monitor_task
        except asyncio.CancelledError:
            logger.debug("Timeout monitor stopped")
        api_task.cancel()
        try:
            await api_task
        except asyncio.CancelledError:
            logger.debug("API server stopped")

    logger.info("server stopped")


def main() -> None:
    from foundry_bridge import setup_logging
    setup_logging()
    asyncio.run(_main())


if __name__ == "__main__":
    main()
