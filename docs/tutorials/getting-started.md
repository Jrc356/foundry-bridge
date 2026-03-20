# Build your first foundry-bridge setup

In this tutorial, we will install foundry-bridge, start the bridge server, connect a subscriber that prints incoming audio metadata, install the userscript into a Foundry VTT session, and watch audio frames arrive in real time.

By the end, we will have a working pipeline: audio captured from a Foundry VTT browser tab flowing through the bridge and being received by a subscriber process on your machine.

## Prerequisites

- Python 3.10 or newer (`python --version`)
- [`uv`](https://github.com/astral-sh/uv) installed (`uv --version`)
- A Foundry VTT instance you can open in a browser (local or hosted on forge-vtt.com)
- A userscript manager extension: [Tampermonkey](https://www.tampermonkey.net/) or [Violentmonkey](https://violentmonkey.github.io/)
- At least one other participant in a Foundry VTT voice session (or use two browser tabs logged in as different users)

## Step 1: Clone the repository and install dependencies

First, clone the repository and move into it:

```bash
git clone https://github.com/your-org/foundry-bridge.git
cd foundry-bridge
```

Now install the Python dependencies:

```bash
uv sync
```

> You should see `uv` resolve and install packages, ending with a line like `Installed N packages`.

## Step 2: Start the bridge server

```bash
uv run foundry-bridge
```

> You should see log output similar to:
> ```
> 2026-03-20 12:00:00 INFO Starting bridge on ws://0.0.0.0:8765
> 2026-03-20 12:00:00 INFO Health check on http://0.0.0.0:8766/health
> ```
>
> The bridge is now listening for ingest connections (from the userscript) and subscriber connections (from downstream consumers) on port `8765`.

Leave this terminal running and open a second terminal for the next step.

## Step 3: Start the example subscriber

In your second terminal, from the same project directory:

```bash
uv run foundry-bridge-example
```

> You should see:
> ```
> 2026-03-20 12:00:05 INFO [debug-consumer] Connecting to bridge at ws://127.0.0.1:8765
> 2026-03-20 12:00:05 INFO [debug-consumer] Connected to bridge
> ```
>
> The example subscriber is now connected and waiting. It will log every audio frame and lifecycle event it receives.

## Step 4: Install the userscript

Open your userscript manager's dashboard (click its browser toolbar icon and choose "Dashboard" or "Manage scripts").

1. Create a new script (Tampermonkey: "+" icon; Violentmonkey: "New Script" button).
2. Delete all placeholder code in the editor.
3. Paste the entire contents of `userscript.js` from this repository.
4. Save the script (Ctrl+S or the Save button).

> Notice that the script is now listed as enabled in the dashboard. The matched URLs include `http://localhost:30000/*` for local Foundry VTT instances and `https://*.forge-vtt.com/*` for hosted instances.

## Step 5: Open Foundry VTT and connect to the bridge

Navigate to your Foundry VTT instance in the browser. You should see a small control panel in the top-right corner of the page labelled **Foundry Audio Bridge**.

1. In the **Bridge URL** field, confirm the value is `ws://127.0.0.1:8765` (this is the default).
2. Click **Connect**.

> You should see the panel show a "Connected" status. In your bridge server terminal, a new log line will appear:
> ```
> INFO Ingest client connected: ...
> ```

## Step 6: Start audio capture

In the Foundry VTT control panel:

1. Join a voice channel with at least one other participant (or open a second browser tab as a different user and join the same channel).
2. Click **Start Capture**.

> In your example subscriber terminal, you should start seeing log lines like:
> ```
> INFO Received audio frame from Alice (participant=user_abc123, sampleRate=48000, samples=4096, bytes=8192)
> INFO Received audio frame from Bob (participant=user_def456, sampleRate=48000, samples=4096, bytes=8192)
> ```
>
> Each line represents one 4096-sample PCM16 chunk (~85 ms of audio) captured from a participant and delivered through the bridge.

## What you've built

You now have a working foundry-bridge pipeline: the userscript captures per-participant audio from a live Foundry VTT voice session, sends it over WebSocket to the bridge server, and the bridge fans it out to all connected subscribers. The example subscriber confirms end-to-end delivery by logging every frame's metadata.

## Next steps

- [How to install the userscript](../how-to/install-the-userscript.md) — full details on userscript managers and URL matching
- [How to set up live transcription with Deepgram](../how-to/set-up-transcription.md) — replace the example subscriber with a real-time speech-to-text pipeline
- [How to write a custom subscriber](../how-to/write-a-custom-subscriber.md) — build your own audio consumer
- [How to deploy with Docker Compose](../how-to/deploy-with-docker.md) — run the full stack in containers
