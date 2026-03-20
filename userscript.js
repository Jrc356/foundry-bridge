// ==UserScript==
// @name         Foundry LiveKit Audio Bridge
// @namespace    jon/foundry-livekit-audio
// @version      0.2.0
// @description  Capture per-participant LiveKit audio from Foundry and stream PCM16 to an ingestion bridge
// @match        https://*.forge-vtt.com/*
// @match        https://*.forge-vtt.net/*
// @match        http://localhost:30000/*
// @run-at       document-idle
// @grant        none
// ==/UserScript==

(() => {
  "use strict";

  const CONFIG = {
    WS_URL: "ws://127.0.0.1:8765",
    SAMPLE_RATE: 48000,
    BUFFER_SIZE: 4096,
    UI_Z_INDEX: 999999,
    AUTO_RECONNECT_MS: 3000,
    POLL_MS: 1000,
  };

  // Logging prefix for easy searching in console/UI logs
  const LOG_SEARCH_PREFIX = "[FAB]"; // searchable short tag
  const LOG_DISPLAY_TAG = "[FoundryAudioBridge]"; // human-readable tag

  let audioCtx = null;
  let ws = null;
  let syncTimer = null;
  let wsReconnectTimer = null;

  const activeParticipants = new Map();

  function log(...args) {
    console.log(LOG_DISPLAY_TAG, ...args);
    appendLog(`${LOG_SEARCH_PREFIX} ${args.map(String).join(" ")}`);
  }

  function logWarn(...args) {
    console.warn(LOG_DISPLAY_TAG, ...args);
    appendLog(`WARN ${LOG_SEARCH_PREFIX} ${args.map(String).join(" ")}`);
  }

  function logError(...args) {
    console.error(LOG_DISPLAY_TAG, ...args);
    appendLog(`ERROR ${LOG_SEARCH_PREFIX} ${args.map(String).join(" ")}`);
  }

  function appendLog(msg) {
    if (!ui.log) return;
    const line = document.createElement("div");
    line.textContent = `${new Date().toLocaleTimeString()} ${msg}`;
    ui.log.prepend(line);
    while (ui.log.childNodes.length > 50) {
      ui.log.removeChild(ui.log.lastChild);
    }
  }

  function getLiveKitClient() {
    try {
      return window.game?.webrtc?.client?._liveKitClient ?? null;
    } catch {
      return null;
    }
  }

  function getParticipantsMap() {
    const lk = getLiveKitClient();
    return lk?.liveKitParticipants ?? null;
  }

  function getParticipantName(participant) {
    return participant?.name || participant?.identity || participant?.sid || "unknown";
  }

  function getParticipantAudioPublications(participant) {
    if (!participant?.audioTracks?.values) return [];
    return [...participant.audioTracks.values()];
  }

  function getMediaStreamTrackFromPublication(pub) {
    const mst =
      pub?.track?.mediaStreamTrack ??
      pub?.track?._mediaStreamTrack ??
      pub?.mediaStreamTrack ??
      null;

    if (!mst) return null;
    if (mst.kind !== "audio") return null;
    if (mst.readyState !== "live") return null;
    return mst;
  }

  function float32ToPCM16(float32Array) {
    const out = new Int16Array(float32Array.length);
    for (let i = 0; i < float32Array.length; i++) {
      const s = Math.max(-1, Math.min(1, float32Array[i]));
      out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    return out;
  }

  function sendJson(obj) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(obj));
    }
  }

  function sendBinary(buffer) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(buffer);
    }
  }

  function sendAudioFrame(participantId, name, pcm16) {
    sendJson({
      type: "audio",
      participantId,
      name,
      sampleRate: audioCtx.sampleRate,
      channels: 1,
      samples: pcm16.length,
      ts: Date.now(),
    });
    sendBinary(pcm16.buffer);
  }

  async function ensureAudioContext() {
    if (!audioCtx) {
      audioCtx = new AudioContext({ sampleRate: CONFIG.SAMPLE_RATE });
    }
    if (audioCtx.state !== "running") {
      await audioCtx.resume();
    }
    return audioCtx;
  }

  function connectWebSocket() {
    clearTimeout(wsReconnectTimer);

    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    updateStatus("Connecting WS...");
    ws = new WebSocket(ui.wsUrl.value.trim());
    ws.binaryType = "arraybuffer";

    ws.onopen = () => {
      updateStatus("WS connected");
      sendJson({
        type: "hello",
        role: "ingest",
        source: "foundry-livekit-userscript",
        userAgent: navigator.userAgent,
        sessionHref: location.href,
      });
      if (ui.autoStart.checked && !bridgeState.running) {
        startCapture().catch(err => logError("start error", err));
      }
    };

    ws.onclose = () => {
      updateStatus("WS disconnected");
      if (bridgeState.wantRunning) {
        wsReconnectTimer = setTimeout(connectWebSocket, CONFIG.AUTO_RECONNECT_MS);
      }
    };

    ws.onerror = (err) => {
      logError("WS error", err);
    };

    ws.onmessage = (event) => {
      log("Server:", typeof event.data === "string" ? event.data : "[binary]");
    };
  }

  function disconnectWebSocket() {
    clearTimeout(wsReconnectTimer);
    if (ws) {
      try { ws.close(); } catch (e) { logWarn("Error closing ws", e); }
      ws = null;
    }
    updateStatus("WS disconnected");
  }

  function attachParticipant(participantId, participant) {
    if (activeParticipants.has(participantId)) return;

    const name = getParticipantName(participant);
    const pubs = getParticipantAudioPublications(participant);
    if (!pubs.length) return;

    const mst = pubs.map(getMediaStreamTrackFromPublication).find(Boolean);
    if (!mst) return;

    const stream = new MediaStream([mst]);
    const source = audioCtx.createMediaStreamSource(stream);
    const processor = audioCtx.createScriptProcessor(CONFIG.BUFFER_SIZE, 1, 1);

    processor.onaudioprocess = (event) => {
      if (!bridgeState.running) return;
      if (!ws || ws.readyState !== WebSocket.OPEN) return;

      const input = event.inputBuffer.getChannelData(0);
      const pcm16 = float32ToPCM16(input);
      sendAudioFrame(participantId, name, pcm16);
    };

    source.connect(processor);
    processor.connect(audioCtx.destination);

    activeParticipants.set(participantId, {
      participantId,
      name,
      mst,
      stream,
      source,
      processor,
    });

    renderParticipants();
    sendJson({ type: "participant_attached", participantId, name, ts: Date.now() });
    log(`Attached ${name} (${participantId})`);
  }

  function detachParticipant(participantId) {
    const state = activeParticipants.get(participantId);
    if (!state) return;

    try { state.processor.disconnect(); } catch (e) { logWarn("Error disconnecting processor", e); }
    try { state.source.disconnect(); } catch (e) { logWarn("Error disconnecting source", e); }

    activeParticipants.delete(participantId);
    renderParticipants();
    sendJson({
      type: "participant_detached",
      participantId,
      name: state.name,
      ts: Date.now(),
    });
    log(`Detached ${state.name} (${participantId})`);
  }

  function syncParticipants() {
    const map = getParticipantsMap();
    if (!map) {
      renderParticipants();
      return;
    }

    const currentIds = new Set();

    for (const [participantId, participant] of map.entries()) {
      currentIds.add(participantId);
      attachParticipant(participantId, participant);
    }

    for (const participantId of [...activeParticipants.keys()]) {
      if (!currentIds.has(participantId)) {
        detachParticipant(participantId);
      }
    }

    renderParticipants();
  }

  const bridgeState = {
    running: false,
    wantRunning: false,
  };

  async function startCapture() {
    bridgeState.wantRunning = true;

    if (!ws || ws.readyState !== WebSocket.OPEN) {
      connectWebSocket();
      return;
    }

    await ensureAudioContext();

    if (bridgeState.running) return;

    bridgeState.running = true;
    updateStatus("Capturing");

    clearInterval(syncTimer);
    syncTimer = setInterval(syncParticipants, CONFIG.POLL_MS);
    syncParticipants();

    sendJson({
      type: "capture_started",
      ts: Date.now(),
      sampleRate: audioCtx.sampleRate,
      bufferSize: CONFIG.BUFFER_SIZE,
    });

    log("Capture started");
  }

  function stopCapture() {
    bridgeState.wantRunning = false;
    bridgeState.running = false;

    clearInterval(syncTimer);
    syncTimer = null;

    for (const participantId of [...activeParticipants.keys()]) {
      detachParticipant(participantId);
    }

    sendJson({ type: "capture_stopped", ts: Date.now() });
    updateStatus("Stopped");
    log("Capture stopped");
  }

  function renderParticipants() {
    if (!ui.participants) return;

    ui.participants.innerHTML = "";
    const map = getParticipantsMap();

    if (!map || map.size === 0) {
      const empty = document.createElement("div");
      empty.textContent = "No LiveKit participants";
      ui.participants.appendChild(empty);
      return;
    }

    for (const [participantId, participant] of map.entries()) {
      const row = document.createElement("div");
      row.style.marginBottom = "4px";

      const pubs = getParticipantAudioPublications(participant);
      const attached = activeParticipants.has(participantId);
      const name = getParticipantName(participant);
      const speaking = !!participant?.isSpeaking;
      const audioLevel = participant?.audioLevel ?? 0;

      row.textContent =
        `${name} | pubs=${pubs.length} | attached=${attached} | speaking=${speaking} | level=${audioLevel}`;
      ui.participants.appendChild(row);
    }
  }

  function updateStatus(text) {
    if (ui.status) ui.status.textContent = text;
  }

  const ui = {};

  function buildUI() {
    const panel = document.createElement("div");
    panel.style.position = "fixed";
    panel.style.top = "12px";
    panel.style.right = "12px";
    panel.style.width = "360px";
    panel.style.background = "rgba(20,20,20,0.95)";
    panel.style.color = "#fff";
    panel.style.padding = "10px";
    panel.style.border = "1px solid #555";
    panel.style.borderRadius = "8px";
    panel.style.zIndex = String(CONFIG.UI_Z_INDEX);
    panel.style.font = "12px sans-serif";
    panel.style.boxShadow = "0 4px 12px rgba(0,0,0,0.35)";

    panel.innerHTML = `
      <div id="fab-header" style="font-weight:bold; margin-bottom:8px; cursor:move; -webkit-user-select:none; user-select:none;">
        <span style="display:flex; align-items:center; justify-content:space-between; gap:8px;">
          <span>Foundry LiveKit Audio Bridge</span>
          <button id="fab-toggle" style="background:transparent; border:1px solid #666; color:#fff; padding:2px 6px; border-radius:4px; cursor:pointer;">▾</button>
        </span>
      </div>
      <div id="fab-body">
      <div style="margin-bottom:6px;">
        <label>WS URL</label>
        <input id="fab-ws" type="text" style="width:100%; box-sizing:border-box; color: #ffffff; background:#222; border:1px solid #444;" value="${CONFIG.WS_URL}">
      </div>
      <div style="display:flex; gap:6px; margin-bottom:6px;">
        <button id="fab-connect">Connect</button>
        <button id="fab-start">Start</button>
        <button id="fab-stop">Stop</button>
      </div>
      <div style="margin-bottom:6px;">
        <label><input id="fab-auto" type="checkbox" checked> Auto-start when WS connects</label>
      </div>
      <div style="margin-bottom:6px;">Status: <span id="fab-status">Idle</span></div>
      <div style="margin-bottom:6px; max-height:120px; overflow:auto; border:1px solid #444; padding:6px;" id="fab-participants"></div>
      <div style="max-height:140px; overflow:auto; border:1px solid #444; padding:6px;" id="fab-log"></div>
      </div>
    `;

    document.body.appendChild(panel);

    ui.panel = panel;
    ui.wsUrl = panel.querySelector("#fab-ws");
    ui.autoStart = panel.querySelector("#fab-auto");
    ui.status = panel.querySelector("#fab-status");
    ui.participants = panel.querySelector("#fab-participants");
    ui.log = panel.querySelector("#fab-log");

    ui.body = panel.querySelector('#fab-body');
    ui.toggleBtn = panel.querySelector('#fab-toggle');

    function setCollapsed(collapsed) {
      if (collapsed) {
        ui.body.style.display = 'none';
        ui.toggleBtn.textContent = '▸';
      } else {
        ui.body.style.display = '';
        ui.toggleBtn.textContent = '▾';
      }
      try { localStorage.setItem('fab-collapsed', JSON.stringify(!!collapsed)); } catch (e) {}
    }

    try {
      const raw = localStorage.getItem('fab-collapsed');
      const collapsed = raw ? JSON.parse(raw) : false;
      setCollapsed(collapsed);
    } catch (e) { setCollapsed(false); }

    ui.toggleBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const newVal = ui.body.style.display !== 'none';
      setCollapsed(newVal);
    });

    // Make the panel draggable via the header (mouse + touch)
    // Load saved position if present, otherwise initialize left so we can reposition
    try {
      const saved = localStorage.getItem('fab-position');
      if (saved) {
        const pos = JSON.parse(saved);
        if (typeof pos.left === 'number') panel.style.left = pos.left + 'px';
        if (typeof pos.top === 'number') panel.style.top = pos.top + 'px';
        panel.style.right = 'auto';
      } else {
        panel.style.left = (window.innerWidth - panel.offsetWidth - 12) + "px";
        panel.style.right = "auto";
      }
    } catch (e) {
      panel.style.left = (window.innerWidth - panel.offsetWidth - 12) + "px";
      panel.style.right = "auto";
    }

    let dragState = { dragging: false, offsetX: 0, offsetY: 0 };

    const headerEl = panel.querySelector('#fab-header');

    function onMouseMove(e) {
      if (!dragState.dragging) return;
      let left = e.clientX - dragState.offsetX;
      let top = e.clientY - dragState.offsetY;
      left = Math.max(0, Math.min(window.innerWidth - panel.offsetWidth, left));
      top = Math.max(0, Math.min(window.innerHeight - panel.offsetHeight, top));
      panel.style.left = left + 'px';
      panel.style.top = top + 'px';
    }

    function savePosition() {
      try {
        const left = parseInt(panel.style.left, 10) || 0;
        const top = parseInt(panel.style.top, 10) || 0;
        localStorage.setItem('fab-position', JSON.stringify({ left, top }));
      } catch (e) {}
    }

    function onMouseUp() {
      dragState.dragging = false;
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
      document.body.style.userSelect = '';
      savePosition();
    }

    headerEl.addEventListener('mousedown', (e) => {
      e.preventDefault();
      dragState.dragging = true;
      const rect = panel.getBoundingClientRect();
      dragState.offsetX = e.clientX - rect.left;
      dragState.offsetY = e.clientY - rect.top;
      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup', onMouseUp);
      document.body.style.userSelect = 'none';
    });

    // Touch support
    function onTouchMove(e) {
      if (!dragState.dragging) return;
      const t = e.touches[0];
      let left = t.clientX - dragState.offsetX;
      let top = t.clientY - dragState.offsetY;
      left = Math.max(0, Math.min(window.innerWidth - panel.offsetWidth, left));
      top = Math.max(0, Math.min(window.innerHeight - panel.offsetHeight, top));
      panel.style.left = left + 'px';
      panel.style.top = top + 'px';
    }

    function onTouchEnd() {
      dragState.dragging = false;
      document.removeEventListener('touchmove', onTouchMove);
      document.removeEventListener('touchend', onTouchEnd);
      savePosition();
    }

    // Keep panel within viewport on resize and persist
    window.addEventListener('resize', () => {
      const left = Math.max(0, Math.min(window.innerWidth - panel.offsetWidth, parseInt(panel.style.left, 10) || 0));
      const top = Math.max(0, Math.min(window.innerHeight - panel.offsetHeight, parseInt(panel.style.top, 10) || 0));
      panel.style.left = left + 'px';
      panel.style.top = top + 'px';
      savePosition();
    });

    headerEl.addEventListener('touchstart', (e) => {
      const t = e.touches[0];
      dragState.dragging = true;
      const rect = panel.getBoundingClientRect();
      dragState.offsetX = t.clientX - rect.left;
      dragState.offsetY = t.clientY - rect.top;
      document.addEventListener('touchmove', onTouchMove, { passive: false });
      document.addEventListener('touchend', onTouchEnd);
    });

    panel.querySelector("#fab-connect").onclick = () => connectWebSocket();
    panel.querySelector("#fab-start").onclick = () => startCapture().catch(err => logError("Start failed", err));
    panel.querySelector("#fab-stop").onclick = () => stopCapture();
  }

  function waitForFoundry() {
    const timer = setInterval(() => {
      if (document.body && window.game?.webrtc?.client) {
        clearInterval(timer);
        buildUI();
        renderParticipants();
        log("UI ready");
      }
    }, 500);
  }

  waitForFoundry();

  window.__foundryAudioBridge = {
    startCapture,
    stopCapture,
    connectWebSocket,
    disconnectWebSocket,
    syncParticipants,
  };
})();
