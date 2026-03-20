import asyncio
import json
import logging
import signal
from dataclasses import dataclass, field
from typing import Optional

from websockets.asyncio.server import ServerConnection, serve


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

HOST = "0.0.0.0"
PORT = 8765
HEALTH_PORT = 8766


@dataclass
class ConnectionState:
    ws: ServerConnection
    role: Optional[str] = None
    client_id: str = ""
    last_audio_header: Optional[dict] = None
    metadata: dict = field(default_factory=dict)


ingest_clients: set[ServerConnection] = set()
subscriber_clients: set[ServerConnection] = set()
connection_states: dict[ServerConnection, ConnectionState] = {}


def make_client_id(ws: ServerConnection) -> str:
    remote = getattr(ws, "remote_address", None)
    return f"{id(ws)}:{remote}"


async def safe_send_json(ws: ServerConnection, payload: dict) -> bool:
    try:
        await ws.send(json.dumps(payload))
        return True
    except Exception:
        return False


async def broadcast_json(payload: dict) -> None:
    if not subscriber_clients:
        return

    dead = []
    message = json.dumps(payload)

    for ws in subscriber_clients:
        try:
            await ws.send(message)
        except Exception:
            dead.append(ws)

    for ws in dead:
        subscriber_clients.discard(ws)
        connection_states.pop(ws, None)


async def broadcast_audio(header: dict, payload: bytes) -> None:
    if not subscriber_clients:
        return

    dead = []
    header_msg = json.dumps(header)

    for ws in subscriber_clients:
        try:
            await ws.send(header_msg)
            await ws.send(payload)
        except Exception:
            dead.append(ws)

    for ws in dead:
        subscriber_clients.discard(ws)
        connection_states.pop(ws, None)


async def register_connection(ws: ServerConnection) -> ConnectionState:
    state = ConnectionState(ws=ws, client_id=make_client_id(ws))
    connection_states[ws] = state
    return state


async def unregister_connection(ws: ServerConnection) -> None:
    state = connection_states.pop(ws, None)
    ingest_clients.discard(ws)
    subscriber_clients.discard(ws)

    if state and state.role == "ingest":
        await broadcast_json({
            "type": "bridge_connection_closed",
            "role": state.role,
            "clientId": state.client_id,
        })


async def handle_json_message(state: ConnectionState, data: dict) -> None:
    msg_type = data.get("type")

    if msg_type == "hello":
        role = data.get("role")
        if role not in {"ingest", "subscriber"}:
            await safe_send_json(state.ws, {
                "type": "error",
                "message": "hello.role must be 'ingest' or 'subscriber'",
            })
            return

        state.role = role
        state.metadata = data

        if role == "ingest":
            ingest_clients.add(state.ws)
        else:
            subscriber_clients.add(state.ws)

        await safe_send_json(state.ws, {
            "type": "hello_ack",
            "role": role,
            "clientId": state.client_id,
        })

        if role == "ingest":
            await broadcast_json({
                "type": "bridge_connection_opened",
                "role": role,
                "clientId": state.client_id,
                "metadata": data,
            })

        logging.info("registered %s client %s", role, state.client_id)
        return

    if state.role == "ingest":
        if msg_type == "audio":
            state.last_audio_header = data
            return

        await broadcast_json({
            "type": "ingest_event",
            "clientId": state.client_id,
            "event": data,
        })
        return

    if state.role == "subscriber":
        await safe_send_json(state.ws, {
            "type": "warning",
            "message": "subscriber messages are ignored except hello",
        })
        return

    await safe_send_json(state.ws, {
        "type": "error",
        "message": "send hello first",
    })


async def handle_binary_message(state: ConnectionState, payload: bytes) -> None:
    if state.role != "ingest":
        await safe_send_json(state.ws, {
            "type": "error",
            "message": "binary messages are only valid for ingest clients",
        })
        return

    header = state.last_audio_header
    if not header or header.get("type") != "audio":
        await safe_send_json(state.ws, {
            "type": "error",
            "message": "binary audio must follow an 'audio' JSON header",
        })
        return

    out_header = {
        "type": "audio_frame_header",
        "clientId": state.client_id,
        "participantId": header.get("participantId"),
        "name": header.get("name"),
        "sampleRate": header.get("sampleRate"),
        "channels": header.get("channels"),
        "samples": header.get("samples"),
        "ts": header.get("ts"),
        "encoding": "pcm_s16le",
        "byteLength": len(payload),
    }

    await broadcast_audio(out_header, payload)


async def handler(ws: ServerConnection) -> None:
    state = await register_connection(ws)
    logging.info("connection opened %s", state.client_id)

    try:
        async for message in ws:
            if isinstance(message, str):
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    await safe_send_json(ws, {
                        "type": "error",
                        "message": "invalid JSON",
                    })
                    continue

                await handle_json_message(state, data)
            else:
                await handle_binary_message(state, message)

    except Exception as exc:
        logging.info("connection closed %s (%s)", state.client_id, exc)
    finally:
        await unregister_connection(ws)


async def health_check_handler(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    """Handle HTTP health check requests."""
    try:
        request_line = await reader.readline()
        request_line = request_line.decode("utf-8").strip()

        if not request_line.startswith("GET /health"):
            writer.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 13\r\n\r\nNot Found\r\n")
            await writer.drain()
            writer.close()
            return

        response_body = json.dumps({"status": "ok"})
        response_body_bytes = response_body.encode("utf-8")
        response = (
            f"HTTP/1.1 200 OK\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(response_body_bytes)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode("utf-8")
        writer.write(response + response_body_bytes)
        await writer.drain()
    except Exception as exc:
        logging.error("health check handler error: %s", exc)
    finally:
        writer.close()
        await writer.wait_closed()


async def _main() -> None:
    logging.info("starting ingestion bridge on ws://%s:%s", HOST, PORT)
    loop = asyncio.get_running_loop()
    stop = loop.create_future()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set_result, None)

    # Start health check HTTP server
    health_server = await asyncio.start_server(
        health_check_handler, HOST, HEALTH_PORT
    )
    logging.info("health check server started on http://%s:%s/health", HOST, HEALTH_PORT)

    async with serve(handler, HOST, PORT, max_size=None) as server:
        logging.info("server ready")
        async with health_server:
            await stop
            logging.info("shutdown signal received, closing connections...")
            server.close()
            await server.wait_closed()

    logging.info("server stopped")


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
