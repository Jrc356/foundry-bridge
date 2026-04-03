# How to Integrate Foundry VTT Userscript

This guide shows you how to install the userscript bridge and verify that Foundry audio is reaching Foundry Bridge.

## Prerequisites

- Foundry Bridge backend reachable from your browser host
- Tampermonkey (or equivalent userscript manager)
- Access to `userscript.js` from this repository

## Step 1: Install the userscript

- Open your userscript manager dashboard.
- Create a new script.
- Paste the contents of `userscript.js`.
- Save and enable the script.

## Step 2: Set the bridge WebSocket URL

In `userscript.js`, locate the `CONFIG` object near the top of the file and update `WS_URL`.

Example for a local bridge:

```js
WS_URL: "ws://127.0.0.1:8765"
```

If Foundry runs on a different machine from the bridge, set this to an address reachable from the browser running Foundry. The WebSocket port defaults to `8765` — refer to [Environment variables](../reference/environment-variables.md) if you changed `WS_PORT`.

## Step 3: Open your Foundry world and voice session

Join the world and connect to voice chat so participant audio tracks are available.

## Step 4: Verify userscript connection

Open browser developer tools and check console messages tagged with:

- `[FoundryAudioBridge]`
- `[FAB]`

These logs indicate script startup and stream forwarding attempts.

## Step 5: Verify backend receives campaign identity

Check games list:

```bash
curl http://localhost:8767/api/games
```

After successful identification, a game entry with matching host/world metadata should appear.

## Related

- [WebSocket protocol](../reference/websocket-protocol.md)
- [Environment variables](../reference/environment-variables.md)
- [How to troubleshoot common issues](./troubleshoot-common-issues.md)
- [Get started with Foundry Bridge](../getting-started.md)
