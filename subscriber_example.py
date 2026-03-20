import asyncio
import json

from websockets.asyncio.client import connect


URI = "ws://127.0.0.1:8765"


async def main():
    async with connect(URI, max_size=None) as ws:
        await ws.send(json.dumps({
            "type": "hello",
            "role": "subscriber",
            "name": "debug-consumer",
        }))

        pending_audio_header = None

        async for message in ws:
            if isinstance(message, str):
                event = json.loads(message)

                if event["type"] == "audio_frame_header":
                    pending_audio_header = event
                else:
                    print("json:", event)
            else:
                if pending_audio_header is None:
                    print("binary with no header", len(message))
                    continue

                header = pending_audio_header
                pending_audio_header = None

                print(
                    "audio:",
                    header["name"],
                    header["participantId"],
                    header["sampleRate"],
                    header["samples"],
                    len(message),
                    "bytes",
                )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
