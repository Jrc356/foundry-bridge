# How to install the userscript

This guide shows you how to install the foundry-bridge userscript into a Foundry VTT browser session using a userscript manager, configure it to connect to your bridge server, and start capturing audio.

## Prerequisites

- A userscript manager extension installed in your browser: [Tampermonkey](https://www.tampermonkey.net/) (Chrome, Firefox, Edge, Safari) or [Violentmonkey](https://violentmonkey.github.io/) (Chrome, Firefox, Edge)
- `userscript.js` from this repository
- A running bridge server (see [How to deploy with Docker Compose](./deploy-with-docker.md) or run `uv run foundry-bridge` locally)

## Step 1: Open the userscript manager dashboard

Click the userscript manager icon in your browser toolbar and choose **Dashboard** (Tampermonkey) or **Manage Scripts** (Violentmonkey).

## Step 2: Create a new script

- **Tampermonkey**: click the **+** tab at the top of the dashboard.
- **Violentmonkey**: click **New Script**.

Delete all placeholder code in the editor.

## Step 3: Paste the userscript

Copy the full contents of `userscript.js` from the repository root and paste it into the editor. Save the script (Ctrl+S or the Save button).

The `@match` directives at the top of the script control which pages it activates on:

| Pattern | Activates on |
|---|---|
| `https://*.forge-vtt.com/*` | Foundry VTT hosted on The Forge |
| `https://*.forge-vtt.net/*` | Foundry VTT hosted on The Forge (alternate domain) |
| `http://localhost:30000/*` | Local Foundry VTT development server |

If your Foundry VTT instance is at a different URL, add an additional `// @match` line in the userscript header before saving.

## Step 4: Open Foundry VTT

Navigate to your Foundry VTT instance. A **Foundry Audio Bridge** control panel will appear in the top-right corner of the page.

## Step 5: Configure the bridge URL

In the **Bridge URL** field, enter the WebSocket address of your bridge server. The default is:

```
ws://127.0.0.1:8765
```

If the bridge is running on a different host or port, adjust accordingly (e.g. `ws://192.168.1.5:8765`).

## Step 6: Connect and start capture

1. Click **Connect**. The panel status will change to "Connected" when the WebSocket handshake completes.
2. Join a Foundry VTT voice channel.
3. Click **Start Capture** to begin streaming audio to the bridge.

To stop, click **Stop Capture** followed by **Disconnect**.

## Troubleshooting

If the panel does not appear, open the browser console (F12) and look for `[FoundryAudioBridge]` log entries. Common causes:

- The page URL does not match any `@match` pattern — verify the URL and add a match rule if needed.
- The userscript manager has the script disabled — check the dashboard.

If the connection fails ("Unable to connect"), verify the bridge server is running and accessible from the browser at the configured URL.

## Related

- [WebSocket protocol reference](../reference/websocket-protocol.md) — details on the messages the userscript sends
- [Configuration reference](../reference/configuration.md) — bridge server port configuration
